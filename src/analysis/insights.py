"""Insights agent: every number is computed from data/research_verified.json (never model-estimated).
All percentages carry their denominator; unknowns are counted, not dropped."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

OPEN = {"self_serve_free", "self_serve_trial"}
GATED = {"paid_plan", "approval_required", "partner_or_sales"}

# Opportunity rubric (documented in docs/methodology.md). Higher = easier/more valuable to build next.
W_API = {"available": 3, "restricted": 1, "unavailable": 0, "unknown": 0}
W_ACCESS = {"self_serve_free": 3, "self_serve_trial": 2, "paid_plan": 1, "approval_required": 1, "partner_or_sales": 0, "not_applicable": 0, "unknown": 0.5}
W_BREADTH = {"broad": 2, "moderate": 1.5, "narrow": 1, "unknown": 1}


def auth_simplicity(methods: list[str]) -> float:
    if not methods:
        return 0
    if any(m in ("API key", "Bearer/access token", "Basic") for m in methods):
        return 3 if "OAuth2" not in methods else 2.5   # both: key for builders, OAuth for end users
    if "OAuth2" in methods:
        return 2
    return 1


def opportunity(r: dict) -> dict:
    s = W_API[r["public_api_status"]] + W_ACCESS[r["developer_access"]] + auth_simplicity(r["authentication_methods"]) + W_BREADTH[r["api_surface_breadth"]]
    s -= 0.5 if r["official_mcp_status"] == "yes" else 0   # vendor already serves agents directly
    s *= 0.6 + 0.4 * r["confidence_score"]                  # discount poorly evidenced records
    return {"score": round(s, 2), "max": 11}


def pct(n: int, d: int) -> dict:
    return {"n": n, "of": d, "pct": round(100 * n / d, 1) if d else None}


def run_insights(root: Path) -> dict:
    recs = json.loads((root / "data" / "research_verified.json").read_text(encoding="utf-8"))
    N = len(recs)
    cats = sorted({r["category"] for r in recs}, key=lambda c: min(x["id"] for x in recs if x["category"] == c))

    auth = Counter(m for r in recs for m in r["authentication_methods"])
    no_auth = sum(1 for r in recs if not r["authentication_methods"])
    primary = Counter("OAuth2" if "OAuth2" in r["authentication_methods"] else
                      ("API key / token" if set(r["authentication_methods"]) & {"API key", "Bearer/access token", "Basic"} else
                       ("other" if r["authentication_methods"] else "unknown")) for r in recs)
    access = Counter(r["developer_access"] for r in recs)
    api = Counter(r["public_api_status"] for r in recs)
    build = Counter(r["toolkit_buildability"] for r in recs)
    types = Counter(t for r in recs for t in r["api_types"])
    blockers = Counter(b for r in recs for b in r["integration_blockers"])

    by_cat = {}
    for c in cats:
        rs = [r for r in recs if r["category"] == c]
        by_cat[c] = {
            "n": len(rs),
            "open": sum(r["developer_access"] in OPEN for r in rs),
            "gated": sum(r["developer_access"] in GATED for r in rs),
            "access_unknown": sum(r["developer_access"] in ("unknown", "not_applicable") for r in rs),
            "oauth2": sum("OAuth2" in r["authentication_methods"] for r in rs),
            "api_key_or_token": sum(bool(set(r["authentication_methods"]) & {"API key", "Bearer/access token", "Basic"}) for r in rs),
            "api_available": sum(r["public_api_status"] == "available" for r in rs),
            "official_mcp": sum(r["official_mcp_status"] == "yes" for r in rs),
            "community_mcp": sum(r["community_mcp_status"] == "yes" for r in rs),
            "composio": sum(r["existing_composio_toolkit"] == "yes" for r in rs),
            "ready": sum(r["toolkit_buildability"] == "ready" for r in rs),
            "needs_access": sum(r["toolkit_buildability"] == "needs_access" for r in rs),
            "limited_or_not": sum(r["toolkit_buildability"] in ("limited", "not_buildable") for r in rs),
            "unknown": sum(r["toolkit_buildability"] == "unknown" for r in rs),
            "avg_confidence": round(sum(r["confidence_score"] for r in rs) / len(rs), 2),
        }
    ease = sorted(cats, key=lambda c: (by_cat[c]["ready"] / by_cat[c]["n"], by_cat[c]["open"]), reverse=True)

    opp = []
    for r in recs:
        o = opportunity(r)
        opp.append({"id": r["id"], "app": r["app_name"], "category": r["category"], **o,
                    "composio": r["existing_composio_toolkit"], "composio_id": r["composio_toolkit_identifier"],
                    "official_mcp": r["official_mcp_status"], "buildability": r["toolkit_buildability"],
                    "access": r["developer_access"], "auth": r["authentication_methods"], "confidence": r["confidence_score"],
                    "blockers": r["integration_blockers"], "reason": r["toolkit_buildability_reason"]})
    new_easy = sorted([o for o in opp if o["composio"] != "yes" and o["buildability"] == "ready"], key=lambda o: -o["score"])
    outreach = sorted([o for o in opp if o["buildability"] == "needs_access"], key=lambda o: -o["score"])
    covered = [o for o in opp if o["composio"] == "yes"]

    ins = {
        "n": N,
        "categories": cats,
        "auth_counts": dict(auth.most_common()), "auth_unknown": no_auth,
        "primary_auth": {k: pct(v, N) for k, v in primary.most_common()},
        "access": {k: pct(v, N) for k, v in access.most_common()},
        "access_buckets": {"open": pct(sum(access[k] for k in OPEN), N), "gated": pct(sum(access[k] for k in GATED), N),
                           "unknown_or_na": pct(access["unknown"] + access["not_applicable"], N)},
        "api_status": {k: pct(v, N) for k, v in api.most_common()},
        "api_types": dict(types.most_common()),
        "buildability": {k: pct(v, N) for k, v in build.most_common()},
        "mcp": {"official_yes": pct(sum(r["official_mcp_status"] == "yes" for r in recs), N),
                "community_yes": pct(sum(r["community_mcp_status"] == "yes" for r in recs), N),
                "composio_yes": pct(sum(r["existing_composio_toolkit"] == "yes" for r in recs), N),
                "composio_no": pct(sum(r["existing_composio_toolkit"] == "no" for r in recs), N),
                "official_but_no_composio": [r["app_name"] for r in recs if r["official_mcp_status"] == "yes" and r["existing_composio_toolkit"] != "yes"],
                "composio_but_no_official": pct(sum(r["existing_composio_toolkit"] == "yes" and r["official_mcp_status"] != "yes" for r in recs), N)},
        "blockers": dict(blockers.most_common(12)),
        "by_category": by_cat,
        "category_ease_rank": ease,
        "confidence": {"high": sum(r["confidence_label"] == "high" for r in recs), "medium": sum(r["confidence_label"] == "medium" for r in recs),
                       "low": sum(r["confidence_label"] == "low" for r in recs), "low_apps": [r["app_name"] for r in recs if r["confidence_label"] == "low"]},
        "evidence": {"total_items": sum(len(r["evidence"]) for r in recs),
                     "records_with_auth_evidence": sum(any(e["field"] == "authentication_methods" for e in r["evidence"]) for r in recs),
                     "records_with_access_evidence": sum(any(e["field"] == "developer_access" for e in r["evidence"]) for r in recs),
                     "records_with_docs_url": sum(bool(r["developer_docs_url"]) for r in recs)},
        "opportunities": {"new_easy_wins": new_easy[:12], "needs_outreach": outreach[:12], "already_in_composio": len(covered),
                          "rubric": "score = API(0-3) + access(0-3) + auth simplicity(0-3) + breadth(1-2) - 0.5 if vendor MCP exists; x(0.6+0.4*confidence). Max 11."},
    }
    ins["headlines"] = headlines(ins)
    (root / "data" / "insights.json").write_text(json.dumps(ins, indent=1, ensure_ascii=False), encoding="utf-8")
    print("[insights]", *ins["headlines"], sep="\n  - ")
    return ins


def headlines(i: dict) -> list[str]:
    """Plain-language findings, each generated from the computed numbers (no hand-typed statistics)."""
    N = i["n"]
    pa = i["primary_auth"]
    top_auth = max(pa, key=lambda k: pa[k]["n"])
    ab = i["access_buckets"]
    bc = i["by_category"]
    most_gated = max(bc, key=lambda c: bc[c]["gated"] / bc[c]["n"])
    most_open = max(bc, key=lambda c: bc[c]["open"] / bc[c]["n"])
    top_blocker = next(iter(i["blockers"]), "n/a")
    b = i["buildability"]
    m = i["mcp"]
    out = [
        f"{top_auth} is the most common primary auth method ({pa[top_auth]['n']}/{N} apps). Counting every supported method, "
        f"OAuth2 appears in {i['auth_counts'].get('OAuth2', 0)}/{N} and API keys in {i['auth_counts'].get('API key', 0)}/{N}; many apps offer both.",
        f"{ab['open']['n']}/{N} apps let a developer self-serve credentials; {ab['gated']['n']}/{N} are gated (paid plan, approval or partner/sales); {ab['unknown_or_na']['n']} could not be established or have no API.",
        f"Most self-serve category: {most_open} ({bc[most_open]['open']}/{bc[most_open]['n']}). Most gated: {most_gated} ({bc[most_gated]['gated']}/{bc[most_gated]['n']}).",
        f"Buildable today with self-serve access: {b.get('ready', {}).get('n', 0)}/{N}; needs access/outreach: {b.get('needs_access', {}).get('n', 0)}/{N}; limited or not buildable: "
        f"{b.get('limited', {}).get('n', 0) + b.get('not_buildable', {}).get('n', 0)}/{N}; unresolved: {b.get('unknown', {}).get('n', 0)}/{N}.",
        f"Most common blocker: {top_blocker} ({i['blockers'].get(top_blocker, 0)} apps).",
        f"Composio already has a toolkit for {m['composio_yes']['n']}/{N}; vendors ship an official MCP server for {m['official_yes']['n']}/{N}. "
        f"For {m['composio_but_no_official']['n']} apps Composio has a toolkit but no vendor MCP server was found: a Composio toolkit and a vendor MCP are separate facts.",
    ]
    return out
