"""Structured extraction agent (deterministic, evidence-anchored).

Every positive claim must point to a regex hit on an *official* page, and stores the excerpt around the hit.
No hit -> the field stays UNKNOWN. A product having a login page never implies OAuth; a website never implies an API.
An optional LLM adjudicator (src/agents/llm.py) can refine ambiguous fields when an API key is configured; the
default run is fully deterministic so it can be reproduced and audited."""
from __future__ import annotations

import re
import time
from urllib.parse import urlparse

from ..models.schema import (Access, ApiStatus, ApiType, AppRecord, Auth, Buildability, Evidence, SourceType, Tri)
from ..tools.http import Page

AUTH_RX = {
    Auth.OAUTH2: r"\boauth\s?2(?:\.0)?\b|\boauth (?:app|apps|client|flow|token|access token|authorization)\b|authorization code (?:grant|flow)|client[_ ]credentials grant",
    Auth.API_KEY: r"\bapi[\s_-]?keys?\b|\bx-api-key\b|\bapikey\b",
    Auth.BEARER_TOKEN: r"\bpersonal access tokens?\b|\bapi tokens?\b|\bbot tokens?\b|\bprivate app (?:access )?tokens?\b|\bintegration tokens?\b|\baccess tokens? (?:in|as) (?:the )?(?:authorization )?header\b|authorization: bearer",
    Auth.BASIC: r"\bbasic auth(?:entication)?\b|\bhttp basic\b|authorization: basic",
    Auth.JWT: r"\bjwt\b|json web tokens?",
    Auth.HMAC: r"\bhmac\b|\bsigned requests?\b|request signing|signature (?:v4|version 4)|sigv4",
}
TYPE_RX = {
    ApiType.REST: r"\brest(?:ful)?\s?api\b|\brest endpoints?\b|\b(?:GET|POST|PUT|PATCH|DELETE) /[a-z{]|curl (?:-X |--request |https?://)",
    ApiType.GRAPHQL: r"\bgraphql\b",
    ApiType.SOAP: r"\bsoap\b|\bwsdl\b",
    ApiType.WEBHOOKS: r"\bwebhooks?\b",
    ApiType.GRPC: r"\bgrpc\b",
    ApiType.WEBSOCKET: r"\bwebsockets?\b|\bwss://",
    ApiType.SQL: r"\bsql api\b|\bcypher\b",
    ApiType.CLI: r"\bcommand[- ]line (?:tool|interface)\b|\bcli\b",
    ApiType.SDK: r"\bsdks?\b|\bclient librar(?:y|ies)\b",
}
ACCESS_RX = {
    "partner": r"\bpartner program\b|\bbecome an? (?:\w+ )?partner\b|\bcontact (?:our |the )?sales\b|\brequest (?:api )?access\b|\bapply for (?:api )?access\b|"
               r"\bjoin the waitlist\b|\binvite[- ]only\b|\bavailable (?:only )?to enterprise\b|\benterprise customers only\b|\bcontact your account (?:manager|executive)\b|\bpartner portal\b",
    # strong = needed before ANY production call (Google Ads developer token, Amazon developer profile review)
    "approval": r"\bdeveloper token\b|\bmust be approved\b|\bapproval process\b|\bbasic access\b|\bstandard access\b|\badvanced access\b|"
                r"\bgrant or deny\b|\bdeveloper profile review\b|\baccess (?:is|will be) granted\b|\bapply for (?:production|standard) access\b",
    # weak = marketplace / public-listing review; does not block building a private toolkit
    "listing_review": r"\bapp review\b|\bsubmit (?:your app|for review)\b|\bapplication (?:is )?(?:reviewed|approved)\b|\bmarketplace (?:review|listing)\b",
    "paid": r"\b(?:available|only available|included) (?:on|with|in|for) (?:the |our )?(?:\w+ )?(?:professional|business|enterprise|pro|premium|paid|growth|scale|advanced|team|plus) (?:plans?|tiers?|subscriptions?|editions?)\b|"
            r"\brequires? an? (?:paid|active|premium) (?:plan|subscription|account)\b|\bpaid plans? only\b|\bapi (?:units|credits) (?:are|must be) purchased\b|\bpay[- ]as[- ]you[- ]go\b",
    "free": r"\bfree (?:developer|sandbox|plan|tier|account|api key)\b|\bsign up for (?:a )?free\b|\bget (?:your|an|a free) api key\b|\bdeveloper sandbox\b|"
            r"\btest mode\b|\bfree credits\b|\bno credit card\b|\bfree to (?:use|get started)\b|\bcreate a free\b|\bdeveloper (?:account|edition) (?:is )?free\b|\bstart for free\b|"
            r"\b(?:workspaces?|accounts?|sandbox(?:es)?|tiers?|plans?) (?:is|are) free\b|\bfree (?:development|developer|test) (?:workspace|org|store|account)s?\b",
    "trial": r"\bfree trial\b|\btrial account\b",
}
MCP_RX = r"\bmcp server\b|\bmodel context protocol\b|\bremote mcp\b"
MCP_PAGE = re.compile(r"(?<![a-z])mcp(?![a-z])|model[-_ ]context[-_ ]protocol", re.I)
APIREF_URL = re.compile(r"/reference|/api[-/]|/endpoints?/|/resources?/|/rest/|/apis?/|/v\d/", re.I)


def _excerpt(text: str, m: re.Match, width: int = 150) -> str:
    s, e = max(0, m.start() - width), min(len(text), m.end() + width)
    return ("…" if s else "") + text[s:e].strip() + ("…" if e < len(text) else "")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _stype(url: str) -> SourceType:
    host = urlparse(url).netloc
    if "github.com" in host:
        return SourceType.OFFICIAL_GITHUB
    if re.search(r"dev|docs|api|developer", host + urlparse(url).path, re.I):
        return SourceType.OFFICIAL_DOCS
    return SourceType.OFFICIAL_SITE


API_CONTEXT = re.compile(r"\bapis?\b|developer|credential|\btokens?\b|api[- ]?key|integration|\bapps?\b|endpoint|sandbox", re.I)


def _in_api_context(text: str, m: re.Match, width: int = 250) -> bool:
    return bool(API_CONTEXT.search(text[max(0, m.start() - width): m.end() + width]))


JSON_BLOB = re.compile(r'[{,]\s*"[\w-]+"\s*:')
OAUTH_CLIENT_AUTH = re.compile(r"oauth/token|token endpoint|client[_ ]?(?:id|secret)", re.I)


def _noise(text: str, m: re.Match, k) -> bool:
    """Matches that are not documentation prose: serialized JSON/script state embedded in rendered docs
    (Mintlify feature flags produced 'JWT' on Notion/Attio), and HTTP Basic used only to authenticate the
    OAuth client at the token endpoint (not a way to call the API)."""
    if len(JSON_BLOB.findall(text[max(0, m.start() - 40): m.end() + 40])) >= 2:  # tight window: prose next to a blob survives
        return True
    return k == Auth.BASIC and bool(OAUTH_CLIENT_AUTH.search(text[max(0, m.start() - 120): m.end() + 120]))


def scan(pages: list[Page], patterns: dict, field: str, stage: str, label=lambda k: str(getattr(k, "value", k)),
         require_api_context: bool = False) -> tuple[dict, list[Evidence]]:
    """Count hits per pattern across official pages; keep the first excerpt per (pattern, page).
    require_api_context drops matches not near API/developer words, so a marketing 'Start for free' button
    on a product homepage is not mistaken for free API access."""
    hits: dict = {}
    ev: list[Evidence] = []
    for p in pages:
        for k, rx in patterns.items():
            ms = [m for m in re.finditer(rx, p.text, re.I)
                  if not _noise(p.text, m, k) and (not require_api_context or _in_api_context(p.text, m))]
            if ms:
                hits[k] = hits.get(k, 0) + len(ms)
                if sum(1 for e in ev if e.claim.endswith(label(k))) < 2:  # keep max 2 excerpts per claim
                    ev.append(Evidence(field=field, claim=f"{field}: {label(k)}", url=p.final_url, source_type=_stype(p.final_url),
                                       excerpt=_excerpt(p.text, ms[0])[:400], retrieved_at=p.fetched_at or _now(), stage=stage))
    return hits, ev


AUTH_PAGE = re.compile(r"auth|oauth|api[-_ ]?keys?|credential|token|getting[-_ ]started|quick[-_ ]?start|introduction|overview", re.I)
SECONDARY = {Auth.JWT, Auth.HMAC, Auth.BASIC}  # often webhook signing or plan names ("Basic plan"): need an auth page


def select_auth(pages: list[Page], stage: str) -> tuple[list[Auth], list[Evidence]]:
    """Auth methods a toolkit would actually use. A method is kept when it is stated on an auth-focused page
    (URL/title about authentication), or, for primary methods only, when it recurs (>=3 hits) across docs.
    Rule tightened after audit sample A showed 'Basic'/'JWT' noise from plan names and webhook signing."""
    auth_pages = [p for p in pages if AUTH_PAGE.search(p.final_url + " " + p.title)]
    on_auth, ev_auth = scan(auth_pages, AUTH_RX, "authentication_methods", stage)
    anywhere, ev_any = scan(pages, AUTH_RX, "authentication_methods", stage)
    keep = {k for k in on_auth} | {k for k, n in anywhere.items() if n >= 3 and k not in SECONDARY}
    ev = [e for e in ev_auth + ev_any if any(e.claim.endswith(k.value) for k in keep)]
    seen, dedup = set(), []
    for e in ev:
        if (e.claim, e.url) not in seen:
            seen.add((e.claim, e.url))
            dedup.append(e)
    order = sorted(keep, key=lambda k: -(on_auth.get(k, 0) * 3 + anywhere.get(k, 0)))
    return order, dedup


def decide_access(h: dict) -> tuple[Access, Tri, list[str]]:
    """Map access-signal hit counts to one Access value. First-pass heuristic; verification + review refine it."""
    blockers = []
    if h.get("approval", 0) >= 2:
        blockers.append("App review / developer-token approval required before production access")
        return Access.APPROVAL, Tri.YES, blockers
    if h.get("free"):
        if h.get("listing_review"):
            blockers.append("Marketplace listing needs vendor review (private use is self-serve)")
        return Access.SELF_SERVE_FREE, Tri.NO, blockers
    if h.get("listing_review", 0) >= 3 and not h.get("paid") and not h.get("partner"):
        blockers.append("App review / approval before production use")
        return Access.APPROVAL, Tri.YES, blockers
    if h.get("partner", 0) >= 2:
        blockers.append("Partner program / contact-sales gate")
        return Access.PARTNER, Tri.YES, blockers
    if h.get("paid"):
        blockers.append("API access tied to a paid plan")
        return Access.PAID_PLAN, Tri.NO, blockers
    if h.get("trial"):
        return Access.SELF_SERVE_TRIAL, Tri.NO, blockers
    if h.get("partner"):
        blockers.append("Possible partner/sales gate (single weak signal)")
        return Access.PARTNER, Tri.UNKNOWN, blockers
    return Access.UNKNOWN, Tri.UNKNOWN, blockers


def extract(app: dict, research: dict, stage: str = "research") -> AppRecord:
    pages: list[Page] = research["official_pages"]
    rec = AppRecord(id=app["id"], app_name=app["app_name"], category=app["category"], pages_fetched=len(pages))
    rec.errors = [l for l in research["log"] if l.startswith("fetch-fail")][:10]
    if not pages:
        rec.errors.append("no official page could be fetched")
        rec.toolkit_buildability_reason = "No official documentation retrieved; needs manual research."
        return rec

    home = next((p for p in pages if urlparse(p.final_url).path in ("", "/") and p.meta_description), None) or \
        next((p for p in pages if p.meta_description), None)
    if home:
        rec.product_description = home.meta_description[:240]
        rec.official_website = f"{urlparse(home.final_url).scheme}://{urlparse(home.final_url).netloc}"
        rec.evidence.append(Evidence(field="product_description", claim="description from official site meta description", url=home.final_url,
                                     source_type=SourceType.OFFICIAL_SITE, excerpt=home.meta_description[:300], retrieved_at=home.fetched_at, stage=stage))
    docs = [p for p in pages if re.search(r"dev|docs|api|reference", p.final_url, re.I)]
    if docs:
        rec.developer_docs_url = docs[0].final_url

    rec.authentication_methods, ev = select_auth(pages, stage)
    rec.evidence += ev

    type_hits, ev = scan(pages, TYPE_RX, "api_types", stage)
    rec.evidence += ev
    rec.api_types = [k for k in type_hits if not (k == ApiType.CLI and type_hits[k] < 2)]

    acc_hits, ev = scan(pages, ACCESS_RX, "developer_access", stage, label=str, require_api_context=True)
    rec.evidence += ev
    rec.developer_access, rec.approval_required, rec.integration_blockers = decide_access(acc_hits)

    api_ref_links = {h for p in docs for h, _ in p.links if APIREF_URL.search(h)}
    has_http_api = bool(set(rec.api_types) & {ApiType.REST, ApiType.GRAPHQL, ApiType.SOAP, ApiType.GRPC}) or len(api_ref_links) >= 10
    if has_http_api and docs:
        rec.public_api_status = ApiStatus.RESTRICTED if rec.developer_access == Access.PARTNER and acc_hits.get("partner", 0) >= 3 else ApiStatus.AVAILABLE
        rec.evidence.append(Evidence(field="public_api_status", claim=f"public_api_status: {rec.public_api_status.value}", url=docs[0].final_url,
                                     source_type=_stype(docs[0].final_url), excerpt=f"official docs page '{docs[0].title[:120]}' with {len(api_ref_links)} API-reference links",
                                     retrieved_at=docs[0].fetched_at, stage=stage))
    elif ApiType.CLI in rec.api_types and any("github.com" in p.final_url for p in pages):
        rec.public_api_status = ApiStatus.UNAVAILABLE
    n = len(api_ref_links)
    rec.api_surface_breadth = "unknown" if not docs else ("broad" if n >= 60 else "moderate" if n >= 15 else "narrow")

    # Only an MCP-specific official page counts: homepages and marketing copy that merely mention MCP / AI clients
    # produced false "yes" values (66/100 before this rule; e.g. a Salesforce homepage credited to Commerce Cloud).
    mcp_pages = [p for p in pages if MCP_PAGE.search(urlparse(p.final_url).path + " " + p.title)]
    mcp_hits, ev = scan(mcp_pages, {"mcp": MCP_RX}, "official_mcp_status", stage, label=lambda k: "vendor MCP page describes an MCP server")
    if mcp_hits:
        rec.official_mcp_status = Tri.YES
        rec.official_mcp_url = ev[0].url
        rec.evidence += ev
    return rec


def derive_buildability(rec: AppRecord) -> None:
    """Deterministic verdict from the (already verified) fields. Never computed by an LLM."""
    a, s = rec.developer_access, rec.public_api_status
    auth_known = bool(rec.authentication_methods)
    if s == ApiStatus.UNAVAILABLE:
        if ApiType.CLI in rec.api_types:
            rec.toolkit_buildability = Buildability.LIMITED
            rec.toolkit_buildability_reason = "No hosted API; local CLI/library only — could be wrapped as a local tool, not a hosted OAuth/API-key toolkit."
        else:
            rec.toolkit_buildability = Buildability.NOT_BUILDABLE
            rec.toolkit_buildability_reason = "No documented public API found."
    elif s in (ApiStatus.AVAILABLE, ApiStatus.RESTRICTED):
        if a in (Access.SELF_SERVE_FREE, Access.SELF_SERVE_TRIAL) and auth_known and s == ApiStatus.AVAILABLE:
            rec.toolkit_buildability = Buildability.READY
            rec.toolkit_buildability_reason = f"Documented API, self-serve credentials, auth: {', '.join(x.value for x in rec.authentication_methods[:3])}."
        elif a in (Access.PAID_PLAN, Access.APPROVAL, Access.PARTNER) or s == ApiStatus.RESTRICTED:
            rec.toolkit_buildability = Buildability.READY_WITH_ACCESS
            rec.toolkit_buildability_reason = f"API exists but credentials are gated ({a.value.replace('_', ' ')})."
        else:
            rec.toolkit_buildability = Buildability.UNKNOWN
            rec.toolkit_buildability_reason = "API documented but access path or auth not established from evidence."
    else:
        rec.toolkit_buildability = Buildability.UNKNOWN
        rec.toolkit_buildability_reason = rec.toolkit_buildability_reason or "Public API status not established from evidence."
    reconcile_blockers(rec)


GATE_BLOCKERS = {"App review / developer-token approval required before production access", "App review / approval before production use",
                 "Partner program / contact-sales gate", "API access tied to a paid plan", "Possible partner/sales gate (single weak signal)"}
ACCESS_BLOCKER = {Access.PAID_PLAN: "API access tied to a paid plan", Access.APPROVAL: "App review / approval before production use",
                  Access.PARTNER: "Partner program / contact-sales gate"}


def reconcile_blockers(rec: AppRecord) -> None:
    """Blockers must agree with the final access value (review can change it), and every non-ready app names its main blocker."""
    if rec.developer_access in (Access.SELF_SERVE_FREE, Access.SELF_SERVE_TRIAL):
        rec.integration_blockers = [b for b in rec.integration_blockers if b not in GATE_BLOCKERS]
    if rec.toolkit_buildability == Buildability.READY or rec.integration_blockers:
        return
    if rec.toolkit_buildability == Buildability.READY_WITH_ACCESS:
        b = ACCESS_BLOCKER.get(rec.developer_access, "API restricted to customers or partners")
    elif rec.toolkit_buildability == Buildability.LIMITED:
        b = "No hosted API; local CLI or library only"
    elif rec.toolkit_buildability == Buildability.NOT_BUILDABLE:
        b = "No documented public API"
    elif rec.public_api_status == ApiStatus.UNKNOWN:
        b = "No official API documentation found"
    else:
        b = "Access path not documented publicly"
    rec.integration_blockers = [b]


def confidence(rec: AppRecord) -> None:
    """Documented rubric (docs/methodology.md): evidence presence per key field + source quality + verification agreement."""
    fields = {e.field for e in rec.evidence if e.source_type != SourceType.SEARCH_SNIPPET}
    score = 0.0
    score += 0.20 if rec.developer_docs_url else 0
    score += 0.20 if "authentication_methods" in fields else 0
    score += 0.20 if "developer_access" in fields and rec.developer_access != Access.UNKNOWN else 0
    score += 0.10 if "public_api_status" in fields else 0
    score += 0.10 if rec.existing_composio_toolkit != Tri.UNKNOWN and rec.official_mcp_status != Tri.UNKNOWN else 0
    score += 0.20 if rec.verification_status in ("auto_verified", "audited") else 0.05 if rec.verification_status == "auto_validated" else 0
    score -= 0.15 if rec.verification_status == "disputed" else 0
    rec.confidence_score = max(0.0, min(1.0, score))
    rec.confidence_label = "high" if score >= 0.75 else "medium" if score >= 0.5 else "low"
