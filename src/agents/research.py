"""Research agent + document fetcher.

Discovers candidate documentation URLs (curated seeds, brief hint, homepage link mining, keyless web search),
fetches them politely, and keeps only pages that pass the identity check (official host of THIS app).
Third-party pages are retained separately and are never used as evidence for vendor claims."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ..tools.http import Fetcher, Page
from ..tools.search import search

KEYWORDS = re.compile(r"auth(?!or)|oauth|api[-_ ]?key|token|getting[-_ ]started|quick[-_ ]?start|introduction|overview|rate[-_ ]limit|api[-_ ]pricing|"
                      r"access(?!ib)|mcp|webhook|graphql|reference|developer|credentials|sandbox|app[-_ ]review|permissions|scopes|\bapi\b", re.I)
DOCSY = re.compile(r"//(?:[^/]*\.)?(?:dev|docs?|developers?|api|developer-docs|learn|help|support)[.-]|/(?:docs?|developers?|api|reference|documentation)\b", re.I)
SKIP = re.compile(r"\.(png|jpe?g|gif|svg|pdf|zip|mp4|webp)$|/(blog|careers|jobs|press|legal|privacy|terms|login|signin|signup|status)\b|changelog", re.I)


def is_official(url: str, official_hosts: list[str]) -> bool:
    p = urlparse(url)
    host = p.netloc.lower().removeprefix("www.")
    hp = (host + p.path).lower()
    for h in official_hosts:
        h = h.lower()
        if "/" in h:  # host/path prefix, e.g. github.com/stripe or developers.facebook.com/docs/whatsapp
            # github org prefixes must match a whole path segment (github.com/meta != github.com/metabase)
            if hp.startswith(h) and (not h.startswith("github.com/") or hp == h or hp.startswith(h + "/")):
                return True
        elif host == h or host.endswith("." + h):
            return True
    return False


def hint_url(hint: str) -> str | None:
    tok = hint.split()[0].strip("()")
    if "." in tok and not tok.startswith("http"):
        return "https://" + tok
    return None


def homepage(official_hosts: list[str]) -> str | None:
    for h in official_hosts:
        if "/" not in h and not h.startswith("github"):
            return "https://" + ("www." + h if h.count(".") == 1 else h)
    return None


def _score_link(url: str, text: str) -> int:
    s = len(KEYWORDS.findall(url)) * 2 + len(KEYWORDS.findall(text))
    if re.search(r"auth|oauth|api[-_ ]?key|credential", url + " " + text, re.I):
        s += 3
    if re.search(r"pricing|plans|access|partner|mcp", url + " " + text, re.I):
        s += 2
    return s


async def research_app(app: dict, fetcher: Fetcher, max_pages: int = 14, use_search: bool = True) -> dict:
    """Returns {'official_pages': [Page], 'third_party': [Page], 'search_results': [...], 'log': [...]}"""
    official_hosts = app["official_hosts"]
    log: list[str] = []
    seen: set[str] = set()
    official: list[Page] = []
    third: list[Page] = []

    async def take(url: str, why: str):
        if url in seen or len(official) >= max_pages or SKIP.search(url):
            return
        seen.add(url)
        p = await fetcher.get(url)
        if not p.ok:
            log.append(f"fetch-fail [{why}] {url} status={p.status} {p.error[:80]}")
            return
        if p.final_url in seen and p.final_url != url:  # redirect landed on a page we already have
            return
        seen.add(p.final_url)
        if official_hosts and is_official(p.final_url, official_hosts):
            official.append(p)
        else:
            third.append(p)
            log.append(f"non-official [{why}] {p.final_url}")

    for u in app.get("seed_urls", []):
        await take(u, "seed")
    hu = hint_url(app["hint"])
    if hu:
        await take(hu, "hint")
    hp = homepage(official_hosts)
    if hp:
        await take(hp, "homepage")

    search_results: list[dict] = []
    if use_search:
        name = re.sub(r"\(.*?\)", "", app["app_name"]).strip()
        for q in (f"{name} API documentation authentication", f"{name} API access pricing developer"):
            res = await search(fetcher, q)
            search_results += [dict(r, query=q) for r in res]
        for r in search_results:
            if official_hosts and is_official(r["url"], official_hosts):
                await take(r["url"], "search")

    # link mining: follow the most relevant official links from pages already fetched
    for _round in range(2):
        cands: dict[str, int] = {}
        # mine docs pages first; marketing pages only when no docs page was found
        sources = [p for p in official if DOCSY.search(p.final_url)] or list(official)
        for p in sources:
            for href, text in p.links:
                if href not in seen and is_official(href, official_hosts) and not SKIP.search(href):
                    cands[href] = max(cands.get(href, 0), _score_link(href, text) + (2 if DOCSY.search(href) else -2))
        picked, marketing = 0, sum(1 for p in official if re.search(r"pricing|partner", p.final_url, re.I))
        for href, s in sorted(cands.items(), key=lambda kv: -kv[1]):
            if picked >= 6 or s < 3:
                break
            if re.search(r"pricing|partner", href, re.I):
                if marketing >= 2:  # cap product-marketing pages; they drown API signals
                    continue
                marketing += 1
            picked += 1
            await take(href, "link")
    return {"official_pages": official, "third_party": third, "search_results": search_results, "log": log}
