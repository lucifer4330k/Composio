"""Per-app LangGraph workflow: research -> extract -> registry -> validate -> finalize.

The graph is compiled once and invoked concurrently for many apps (bounded by a semaphore in main.py).
Each node is a small, testable function over a typed state dict."""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from ..agents.extract import confidence, derive_buildability, extract
from ..agents.research import research_app
from ..agents.validate import validate_record
from ..models.schema import AppRecord, Evidence, SourceType, Tri
from ..tools.http import Fetcher
from ..tools.registries import composio_toolkit, for_product, github_search_repos, mcp_registry


class AppState(TypedDict, total=False):
    app: dict
    research: dict
    record: AppRecord
    registry: dict
    issues: list[str]


def build_graph(fetcher: Fetcher, use_search: bool = True):
    async def n_research(s: AppState) -> AppState:
        return {"research": await research_app(s["app"], fetcher, use_search=use_search)}

    async def n_extract(s: AppState) -> AppState:
        return {"record": extract(s["app"], s["research"])}

    async def n_registry(s: AppState) -> AppState:
        app, rec = s["app"], s["record"]
        now = rec.evidence[0].retrieved_at if rec.evidence else ""
        ck = await composio_toolkit(fetcher, app["app_name"])
        mcp = await mcp_registry(fetcher, app["app_name"], app["official_hosts"])
        gh_orgs = [h.split("/", 1)[1] for h in app["official_hosts"] if h.startswith("github.com/")]
        gh_hits = []
        for org in gh_orgs[:2]:
            gh_hits += [r for r in await github_search_repos(f"mcp in:name org:{org}")
                        if "mcp" in r["full_name"].lower() and not r["archived"] and for_product(app["app_name"], r["full_name"])]
        mcp["official"] = [m for m in mcp["official"] if for_product(app["app_name"], m["name"])]
        # Composio toolkit (separate fact; never implies an official MCP)
        rec.existing_composio_toolkit = Tri(ck["status"])
        if ck["status"] == "yes":
            rec.composio_toolkit_identifier = ck["slug"] + ("" if ck["match"] == "exact" else f" ({ck['match']})")
            rec.evidence.append(Evidence(field="existing_composio_toolkit", claim=f"Composio toolkit '{ck['slug']}' ({ck['match']} match)", url=ck["url"],
                                         source_type=SourceType.COMPOSIO_REGISTRY, excerpt=ck.get("title", ""), retrieved_at=now, stage="registry"))
        # Official MCP: registry namespace owned by vendor, vendor GitHub org repo, or vendor docs (from extract)
        if mcp["official"]:
            m = mcp["official"][0]
            rec.official_mcp_status = Tri.YES
            rec.official_mcp_url = rec.official_mcp_url or m["repo"] or m["website"] or f"https://registry.modelcontextprotocol.io/v0/servers?search={m['name']}"
            rec.evidence.append(Evidence(field="official_mcp_status", claim=f"MCP Registry entry '{m['name']}' under vendor namespace", url=f"https://registry.modelcontextprotocol.io/v0/servers?search={m['name'].split('/')[-1]}",
                                         source_type=SourceType.MCP_REGISTRY, excerpt=m["description"], retrieved_at=now, stage="registry"))
        if gh_hits:
            g = max(gh_hits, key=lambda r: r["stars"])
            rec.official_mcp_status = Tri.YES
            rec.official_mcp_url = rec.official_mcp_url or g["url"]
            rec.evidence.append(Evidence(field="official_mcp_status", claim=f"MCP repo in vendor GitHub org: {g['full_name']}", url=g["url"],
                                         source_type=SourceType.OFFICIAL_GITHUB, excerpt=g["description"], retrieved_at=now, stage="registry"))
        if mcp["community"]:
            rec.community_mcp_status = Tri.YES
            rec.community_mcp_examples = [c["name"] for c in mcp["community"][:5]]
            c = mcp["community"][0]
            rec.evidence.append(Evidence(field="community_mcp_status", claim=f"{len(mcp['community'])} non-vendor MCP Registry entries, e.g. {c['name']}",
                                         url=c["repo"] or f"https://registry.modelcontextprotocol.io/v0/servers?search={c['name'].split('/')[-1]}",
                                         source_type=SourceType.MCP_REGISTRY, excerpt=c["description"], retrieved_at=now, stage="registry"))
        return {"record": rec, "registry": {"composio": ck, "mcp_registry": mcp, "github_mcp": gh_hits}}

    async def n_validate(s: AppState) -> AppState:
        rec = s["record"]
        derive_buildability(rec)
        issues = validate_record(rec, s["app"])
        rec.verification_status = "auto_validated" if not issues else "unverified"
        rec.errors += [f"validation: {i}" for i in issues]
        confidence(rec)
        return {"record": rec, "issues": issues}

    g = StateGraph(AppState)
    for name, fn in (("research", n_research), ("extract", n_extract), ("registry", n_registry), ("validate", n_validate)):
        g.add_node(name, fn)
    g.set_entry_point("research")
    g.add_edge("research", "extract")
    g.add_edge("extract", "registry")
    g.add_edge("registry", "validate")
    g.add_edge("validate", END)
    return g.compile()


def serialize(state: dict[str, Any]) -> dict:
    r = state["research"]
    return {
        "record": state["record"].model_dump(mode="json"),
        "used_urls": [p.final_url for p in r["official_pages"]],
        "third_party_urls": [p.final_url for p in r["third_party"]][:10],
        "search_results": r["search_results"][:16],
        "research_log": r["log"][:30],
        "registry": state.get("registry", {}),
        "issues": state.get("issues", []),
    }
