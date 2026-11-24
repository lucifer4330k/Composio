"""Independent verification agent (automated).

Does NOT ask a model whether its earlier answer was right. It gathers a *disjoint* evidence set
(different search queries, excluding every URL used in pass 1), re-runs the extractor on that evidence only,
and compares field by field. Agreement raises confidence; disagreement marks the record 'disputed' and
queues it for review. Both values are preserved."""
from __future__ import annotations

import re

from ..models.schema import Access, AppRecord, Correction, Evidence
from ..tools.http import Fetcher
from ..tools.search import search
from .extract import ACCESS_RX, AUTH_RX, decide_access, scan
from .research import SKIP, is_official, _score_link

GATED = {Access.PAID_PLAN, Access.APPROVAL, Access.PARTNER}
OPEN = {Access.SELF_SERVE_FREE, Access.SELF_SERVE_TRIAL}


async def independent_pass(app: dict, rec: AppRecord, used_urls: set[str], fetcher: Fetcher, max_pages: int = 6) -> dict:
    name = re.sub(r"\(.*?\)", "", app["app_name"]).strip()
    pages, seen = [], set(used_urls)
    for q in (f"{name} API authentication OAuth API key how to get credentials", f"{name} developer API pricing plan access requirements"):
        for r in await search(fetcher, q, k=10):
            u = r["url"].split("#")[0]
            if u in seen or SKIP.search(u) or not is_official(u, app["official_hosts"]):
                continue
            seen.add(u)
            p = await fetcher.get(u)
            if p.ok and is_official(p.final_url, app["official_hosts"]):
                pages.append(p)
            if len(pages) >= max_pages:
                break
    # if search gave nothing new, follow unseen auth/access links from pass-1 docs page (still disjoint pages)
    if len(pages) < 2 and rec.developer_docs_url:
        base = await fetcher.get(rec.developer_docs_url)
        links = sorted({h: _score_link(h, t) for h, t in base.links if h not in seen and is_official(h, app["official_hosts"])}.items(), key=lambda kv: -kv[1])
        for h, s in links[:4]:
            if s >= 4:
                seen.add(h)
                p = await fetcher.get(h)
                if p.ok:
                    pages.append(p)
    auth_hits, auth_ev = scan(pages, AUTH_RX, "authentication_methods", "verify")
    acc_hits, acc_ev = scan(pages, ACCESS_RX, "developer_access", "verify", label=str, require_api_context=True)
    acc, _, _ = decide_access(acc_hits)
    return {"pages": [p.final_url for p in pages], "auth": set(auth_hits), "access": acc, "evidence": auth_ev + acc_ev}


def compare(rec: AppRecord, ind: dict) -> dict:
    """Field-level agreement between pass 1 and the independent pass. Returns a verification log entry."""
    out = {"id": rec.id, "app": rec.app_name, "independent_pages": ind["pages"], "checks": {}}
    if not ind["pages"]:
        out["status"] = "no_independent_evidence"
        return out
    p1 = set(rec.authentication_methods)
    if p1 and ind["auth"]:
        out["checks"]["authentication_methods"] = "agree" if p1 & ind["auth"] else "conflict"
    elif ind["auth"] and not p1:
        out["checks"]["authentication_methods"] = "filled_by_verify"
    else:
        out["checks"]["authentication_methods"] = "unverifiable"
    a1, a2 = rec.developer_access, ind["access"]
    if a1 == Access.UNKNOWN and a2 != Access.UNKNOWN:
        out["checks"]["developer_access"] = "filled_by_verify"
    elif a2 == Access.UNKNOWN:
        out["checks"]["developer_access"] = "unverifiable"
    elif a1 == a2 or (a1 in GATED and a2 in GATED) or (a1 in OPEN and a2 in OPEN):
        out["checks"]["developer_access"] = "agree"
    else:
        out["checks"]["developer_access"] = "conflict"
    vals = set(out["checks"].values())
    out["status"] = "disputed" if "conflict" in vals else "agree" if "agree" in vals else "partial"
    return out


def apply_verification(rec: AppRecord, ind: dict, result: dict) -> None:
    """Fill unknowns from independent evidence (recorded as corrections); never silently overwrite a conflict."""
    rec.evidence += [Evidence(**e.model_dump()) for e in ind["evidence"]]
    if result["checks"].get("authentication_methods") == "filled_by_verify":
        rec.corrections.append(Correction(field="authentication_methods", before=[], after=sorted(a.value for a in ind["auth"]),
                                          reason="pass 1 found no auth evidence; independent pass did", stage="verify",
                                          evidence_url=ind["pages"][0]))
        rec.authentication_methods = sorted(ind["auth"], key=lambda a: a.value)
    if result["checks"].get("developer_access") == "filled_by_verify":
        rec.corrections.append(Correction(field="developer_access", before=rec.developer_access.value, after=ind["access"].value,
                                          reason="pass 1 found no access signal; independent pass did", stage="verify", evidence_url=ind["pages"][0]))
        rec.developer_access = ind["access"]
    rec.verification_status = {"disputed": "disputed", "agree": "auto_verified"}.get(result["status"], rec.verification_status)
