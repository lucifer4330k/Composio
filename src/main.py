"""CLI entry point.

  python -m src.main research [--ids 1,2,3] [--limit N] [--concurrency 4] [--force] [--no-search]
  python -m src.main verify   [--ids ...]                 # independent automated pass on all/selected records
  python -m src.main review                               # apply data/review_adjudications.json (audited corrections)
  python -m src.main insights                             # statistics + opportunity ranking -> data/insights.json
  python -m src.main report                               # output/index.html, results.json/csv, verification_report.md
  python -m src.main all                                  # everything above, resumable
  python -m src.main recheck --ids 81                     # re-research one app (ignores checkpoint + page cache)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import time
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT, CACHE = ROOT / "data", ROOT / "output", ROOT / "cache"
RAW = DATA / "research_raw.json"
VERIFIED = DATA / "research_verified.json"
VLOG = DATA / "verification_log.json"
CONFIG = json.loads((ROOT / "config" / "settings.json").read_text())


def load_apps() -> list[dict]:
    return json.loads((DATA / "apps_input.json").read_text(encoding="utf-8"))["apps"]


def load_json(p: Path, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save_json(p: Path, obj) -> None:
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)  # atomic: an interrupted run never leaves a half-written checkpoint


def select(apps: list[dict], args) -> list[dict]:
    if getattr(args, "ids", None):
        want = {int(x) for x in args.ids.split(",")}
        apps = [a for a in apps if a["id"] in want]
    if getattr(args, "limit", None):
        apps = apps[: args.limit]
    return apps


def pending(apps: list[dict], state: dict, force: bool = False) -> list[dict]:
    """Checkpoint resume: only apps without a saved record (unless forced)."""
    return [a for a in apps if force or str(a["id"]) not in state["apps"]]


async def cmd_research(args) -> None:
    from .tools.http import Fetcher
    from .workflows.graph import build_graph, serialize

    apps = select(load_apps(), args)
    state = load_json(RAW, {"meta": {}, "apps": {}})
    todo = pending(apps, state, args.force)
    print(f"[research] total={len(apps)} already_done={len(apps) - len(todo)} pending={len(todo)} concurrency={args.concurrency}")
    fetcher = Fetcher(CACHE / "pages", per_host=CONFIG["per_host_concurrency"], retries=CONFIG["http_retries"], use_cache=not args.no_cache)
    graph = build_graph(fetcher, use_search=not args.no_search)
    sem, lock = asyncio.Semaphore(args.concurrency), asyncio.Lock()
    done = failed = 0
    t0 = time.time()

    async def run(app):
        nonlocal done, failed
        async with sem:
            try:
                out = await asyncio.wait_for(graph.ainvoke({"app": app}), timeout=CONFIG["per_app_timeout_s"])
                entry = serialize(out)
            except Exception as e:  # partial-failure tolerance: keep a record with the error, never crash the batch
                failed += 1
                from .models.schema import AppRecord
                entry = {"record": AppRecord(id=app["id"], app_name=app["app_name"], category=app["category"],
                                             errors=[f"pipeline error: {type(e).__name__}: {str(e)[:200]}"]).model_dump(mode="json"),
                         "used_urls": [], "issues": ["pipeline error"]}
            async with lock:
                state["apps"][str(app["id"])] = entry
                state["meta"] = run_meta(args)
                save_json(RAW, state)  # checkpoint after every app
                done += 1
                r = entry["record"]
                print(f"  [{done}/{len(todo)}] #{app['id']:>3} {app['app_name']:<26} pages={r['pages_fetched']:>2} api={r['public_api_status']:<11} "
                      f"access={r['developer_access']:<17} auth={','.join(r['authentication_methods'][:3]) or '-':<30} "
                      f"composio={r['existing_composio_toolkit']:<7} ({time.time() - t0:.0f}s)", flush=True)

    await asyncio.gather(*(run(a) for a in todo))
    await fetcher.close()
    print(f"[research] finished: ok={done - failed} failed={failed} pending={sum(str(a['id']) not in state['apps'] for a in apps)} http={fetcher.stats}")


def run_meta(args) -> dict:
    import os
    return {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": platform.python_version(),
        "packages": {p: version(p) for p in ("langgraph", "pydantic", "httpx", "beautifulsoup4")},
        "extraction": "deterministic regex rules over official pages (src/agents/extract.py)",
        "llm_provider": os.getenv("LLM_PROVIDER") or "none (no LLM key configured; deterministic extraction)",
        "search_provider": "tavily" if os.getenv("TAVILY_API_KEY") else "duckduckgo-lite (keyless)",
        "composio_registry": "composio Python SDK catalog (toolkits.list)" if os.getenv("COMPOSIO_API_KEY") else "composio.dev public toolkit pages",
        "config": CONFIG,
        "args": {k: v for k, v in vars(args).items() if k != "func"},
    }


async def cmd_verify(args) -> None:
    from .agents.extract import confidence, derive_buildability
    from .agents.verify import apply_verification, compare, independent_pass
    from .models.schema import AppRecord, Correction, Evidence, SourceType, Tri
    from .tools.http import Fetcher
    from .tools.registries import composio_toolkit

    apps = {a["id"]: a for a in select(load_apps(), args)}
    state = load_json(RAW, {"apps": {}})
    vlog = load_json(VLOG, {"automated": {}})
    fetcher = Fetcher(CACHE / "pages", per_host=CONFIG["per_host_concurrency"])
    sem, lock = asyncio.Semaphore(args.concurrency), asyncio.Lock()
    todo = [i for i in apps if str(i) in state["apps"] and (args.force or str(i) not in vlog["automated"])]
    print(f"[verify] independent pass on {len(todo)} records")
    n = 0

    async def run(i):
        nonlocal n
        async with sem:
            entry = state["apps"][str(i)]
            rec = AppRecord(**entry["record"])
            try:
                ind = await asyncio.wait_for(independent_pass(apps[i], rec, set(entry.get("used_urls", [])), fetcher),
                                             timeout=CONFIG["verify_timeout_s"])
                res = compare(rec, ind)
                apply_verification(rec, ind, res)
            except TimeoutError:  # a hung fetch must not stall the batch; pass-1 values stay, flagged for review
                res = {"status": "verify_timeout", "checks": {}}
            # registry re-check: catches transient failures and slug redirects (e.g. /toolkits/amazon -> category page)
            ck = await composio_toolkit(fetcher, rec.app_name)
            if ck["status"] != rec.existing_composio_toolkit.value:
                rec.corrections.append(Correction(field="existing_composio_toolkit", before=rec.existing_composio_toolkit.value, after=ck["status"],
                                                  reason=f"registry re-check ({ck['source']}) disagreed with pass 1", stage="verify", evidence_url=ck["url"]))
                rec.existing_composio_toolkit = Tri(ck["status"])
                rec.composio_toolkit_identifier = (ck["slug"] + ("" if ck["match"] == "exact" else f" ({ck['match']})")) if ck["slug"] else None
                rec.evidence = [e for e in rec.evidence if e.field != "existing_composio_toolkit"]
                if ck["status"] == "yes":
                    rec.evidence.append(Evidence(field="existing_composio_toolkit", claim=f"Composio toolkit '{ck['slug']}' ({ck['match']} match)", url=ck["url"],
                                                 source_type=SourceType.COMPOSIO_REGISTRY, excerpt=ck.get("title", ""), retrieved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), stage="verify"))
            res["checks"]["existing_composio_toolkit"] = "agree" if not rec.corrections or rec.corrections[-1].field != "existing_composio_toolkit" else "corrected"
            derive_buildability(rec)
            confidence(rec)
            async with lock:
                entry["record_after_verify"] = rec.model_dump(mode="json")
                vlog["automated"][str(i)] = res
                save_json(RAW, state)
                save_json(VLOG, vlog)
                n += 1
                print(f"  [{n}/{len(todo)}] #{i:>3} {rec.app_name:<26} {res['status']:<24} {res.get('checks')}", flush=True)

    await asyncio.gather(*(run(i) for i in todo))
    await fetcher.close()


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("research", "verify", "recheck", "review", "insights", "report", "all"):
        p = sub.add_parser(name)
        p.add_argument("--ids")
        p.add_argument("--limit", type=int)
        p.add_argument("--concurrency", type=int, default=CONFIG["concurrency"])
        p.add_argument("--force", action="store_true")
        p.add_argument("--no-search", action="store_true")
        p.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()
    if args.cmd == "recheck":
        args.force, args.no_cache = True, True
        args.cmd = "research"
    if args.cmd in ("research", "all"):
        asyncio.run(cmd_research(args))
    if args.cmd in ("verify", "all"):
        asyncio.run(cmd_verify(args))
    if args.cmd in ("review", "all"):
        from .analysis.consolidate import consolidate
        consolidate(ROOT)
    if args.cmd in ("insights", "all"):
        from .analysis.insights import run_insights
        run_insights(ROOT)
    if args.cmd in ("report", "all"):
        from .reporting.build_report import build
        build(ROOT)


if __name__ == "__main__":
    sys.exit(main())
