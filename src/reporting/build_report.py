"""Report generator: writes the self-contained output/index.html plus results.json, results.csv and
verification_report.md. All figures on the page are computed in the browser from the embedded dataset
or come from data/insights.json / verification_log.json — nothing is typed in by hand."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

CSV_FIELDS = ["id", "app_name", "category", "product_description", "official_website", "developer_docs_url", "public_api_status",
              "authentication_methods", "developer_access", "approval_required", "api_types", "api_surface_breadth", "official_mcp_status",
              "official_mcp_url", "community_mcp_status", "existing_composio_toolkit", "composio_toolkit_identifier", "toolkit_buildability",
              "toolkit_buildability_reason", "integration_blockers", "confidence_score", "confidence_label", "verification_status", "evidence_urls"]


def _read(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def human_check(p: Path) -> list[dict]:
    """Rows of the hand-check sheet that a person has filled (verdict set); empty until then."""
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("verdict", "").strip()]
    for r in rows:
        r["verdict"] = r["verdict"].strip().lower()
        if r["verdict"] not in ("correct", "wrong", "unclear"):
            raise SystemExit(f"human_check.csv: verdict must be correct / wrong / unclear, got {r['verdict']!r} ({r['app']}, {r['field']})")
    return rows


def build(root: Path) -> None:
    data, out = root / "data", root / "output"
    out.mkdir(exist_ok=True)
    recs = _read(data / "research_verified.json")
    ins = _read(data / "insights.json")
    vlog = _read(data / "verification_log.json", {})
    raw = _read(data / "research_raw.json", {"meta": {}, "apps": {}})

    # downloads
    (out / "results.json").write_text(json.dumps(recs, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(out / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in recs:
            row = {k: r.get(k) for k in CSV_FIELDS if k != "evidence_urls"}
            for k in ("authentication_methods", "api_types", "integration_blockers"):
                row[k] = "; ".join(row[k])
            row["evidence_urls"] = " ".join(dict.fromkeys(e["url"] for e in r["evidence"]))
            w.writerow(row)
    report_md = verification_markdown(recs, vlog, _read(data / "audit.json"), _read(data / "audit_holdout.json"))
    (out / "verification_report.md").write_text(report_md, encoding="utf-8")

    auto = vlog.get("automated", {})
    payload = {
        "meta": raw.get("meta", {}),
        "records": recs,
        "insights": ins,
        "verification": {
            "accuracy": vlog.get("accuracy"),
            "auto_status": dict(Counter(v["status"] for v in auto.values())),
            "auto_checks": {f: dict(Counter(v["checks"].get(f) for v in auto.values() if v.get("checks", {}).get(f)))
                            for f in ("authentication_methods", "developer_access")},
            "corrections": vlog.get("corrections", []),
            "dataset_issues": vlog.get("dataset_issues", []),
            "record_issues": vlog.get("record_issues", {}),
        },
        "audit": _read(data / "audit.json"),
        "holdout": _read(data / "audit_holdout.json"),
        "review": {k: v for k, v in (_read(data / "review_adjudications.json", {}) or {}).items() if k != "apps"},
        "run_stats": _read(data / "run_stats.json", {}),
        "human_check": human_check(data / "human_check.csv"),
    }
    tpl = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")  # keep the JSON from closing the script tag
    (out / "index.html").write_text(tpl.replace("/*__DATA__*/null", blob), encoding="utf-8")
    print(f"[report] output/index.html ({(out / 'index.html').stat().st_size // 1024} KB), results.json, results.csv, verification_report.md")


def verification_markdown(recs, vlog, audit, holdout) -> str:
    L = ["# Verification report", "", f"Records: {len(recs)}. Generated from data/verification_log.json.", ""]
    acc = vlog.get("accuracy") or {}
    for name, block, src in (("Audit sample (A)", acc.get("audit_sample"), audit), ("Hold-out sample (B)", acc.get("holdout_sample"), holdout)):
        if not block:
            continue
        L += [f"## {name}", "", f"Apps: {len(src['apps'])} — {', '.join(v['app'] for v in src['apps'].values())}", "",
              f"Method: {src.get('method', '')}", "", "| Stage | Correct | Wrong | Unknown | Checked | Accuracy |", "|---|---|---|---|---|---|"]
        for st, s in block.items():
            t = s["total"]
            L.append(f"| {st} | {t['correct']} | {t['wrong']} | {t['unknown']} | {t['n']} | {s['accuracy']:.1%} |")
        L += ["", "Per-field (final stage):", "", "| Field | Correct | Wrong | Unknown | n |", "|---|---|---|---|---|"]
        for f, v in block["final"]["fields"].items():
            L.append(f"| {f} | {v['correct']} | {v['wrong']} | {v['unknown']} | {v['n']} |")
        L += ["", "Misses at pass 1:", ""] + [f"- {m['app']}: {m['result']} on field, got `{m['got']}` expected `{m['expected']}`"
                                                for f in block["pass1"]["fields"].values() for m in f["misses"]] + [""]
    auto = vlog.get("automated", {})
    L += ["## Automated independent pass (all records)", "", f"Records: {len(auto)}", ""]
    for k, v in Counter(x["status"] for x in auto.values()).most_common():
        L.append(f"- {k}: {v}")
    cs = vlog.get("corrections", [])
    L += ["", f"## Corrections ({len(cs)})", "", "| App | Field | Before | After | Stage | Reason |", "|---|---|---|---|---|---|"]
    for c in cs:
        L.append(f"| {c['app']} | {c['field']} | {c['before']} | {c['after']} | {c['stage']} | {c['reason'][:140]} |")
    L += ["", "## Open validation issues", ""] + [f"- #{k}: {'; '.join(v)}" for k, v in (vlog.get("record_issues") or {}).items()] + \
         [f"- dataset: {x}" for x in vlog.get("dataset_issues", [])] or ["- none"]
    L += ["", "## Spot-check checklist", "",
          "- [ ] Open 10 random rows; click each evidence link; confirm the excerpt is on the page and supports the claim.",
          "- [ ] Re-check every 'needs_access' verdict against the vendor pricing / partner page.",
          "- [ ] Confirm identity for fanbasis, Paygent Connect, iPayX, Waterfall.io, Sherlock, Mermaid CLI.",
          "- [ ] Spot-check 5 'official MCP = yes' rows: is the server published by the vendor?",
          "- [ ] Spot-check 5 Composio toolkit matches on composio.dev/toolkits.", ""]
    return "\n".join(L)
