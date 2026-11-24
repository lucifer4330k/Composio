"""Registry lookups: official MCP Registry, Composio toolkit registry, GitHub.

Official-vs-community MCP rule (deterministic, no LLM):
  official  = registry namespace is the vendor's verified domain (com.notion/* <-> notion.com),
              or io.github.<org>/* / repository under a vendor GitHub org listed in official_hosts.
  community = any other registry entry whose name matches the app.
Composio toolkit presence is a third, separate fact and never implies an official MCP.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from .http import Fetcher

MCP_REGISTRY = "https://registry.modelcontextprotocol.io/v0/servers"

# slug aliases where Composio's slug is not derivable from the display name (checked manually on composio.dev)
COMPOSIO_ALIASES = {
    "Meta Ads": ["metaads", "facebook"], "Google Ads": ["googleads"], "LinkedIn Ads": ["linkedin"],
    "Lark (Larksuite)": ["lark", "larksuite"], "Threads (Meta)": ["threads"], "Magento (Adobe Commerce)": ["magento", "adobe_commerce"],
    "Monday.com": ["monday"], "WhatsApp Business": ["whatsapp"], "Amazon Selling Partner": ["amazon_selling_partner", "amazon"],
    "MongoDB Atlas": ["mongodb", "mongodb_atlas"], "Otter AI": ["otter", "otter_ai"], "Zoho CRM": ["zoho", "zoho_crm"],
    "Zoho Cliq": ["zoho_cliq", "cliq"], "Salesforce Commerce Cloud": ["salesforce_commerce_cloud", "salesforce_commerce"],
    "Help Scout": ["help_scout", "helpscout"], "SE Ranking": ["se_ranking", "seranking"], "Bright Data": ["brightdata", "bright_data"],
    "Waterfall.io": ["waterfall"], "systeme.io": ["systeme_io", "systeme"], "Mermaid CLI": ["mermaid", "mermaid_cli"],
    "YouTube Transcript": ["youtube_transcript", "transcriptapi", "youtube"], "Paygent Connect": ["paygent", "paygent_connect"],
    "Close": ["close"], "Front": ["front"], "Plain": ["plain"], "Twenty": ["twenty"], "Devin": ["devin"],
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def slug_candidates(name: str) -> list[str]:
    base = re.sub(r"\(.*?\)", "", name).strip()
    c = COMPOSIO_ALIASES.get(name, []) + [norm(base), re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")]
    return list(dict.fromkeys(x for x in c if x))


CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "composio_catalog.json"
_catalog: list[dict] | None = None
_catalog_lock = asyncio.Lock()


def _fetch_catalog() -> dict:
    """Full Composio toolkit catalog through the official Python SDK (needs COMPOSIO_API_KEY)."""
    from composio import Composio
    client, items, cursor = Composio(), [], None
    while True:
        page = client.toolkits.list(limit=1000, cursor=cursor).model_dump(mode="json")
        items += page["items"]
        cursor = page.get("next_cursor")
        if not cursor or not page["items"]:
            break
    keep = ("slug", "name", "app", "type", "toolkit_type", "no_auth", "auth_schemes")
    slim = [{**{k: t.get(k) for k in keep}, "tools_count": (t.get("meta") or {}).get("tools_count"),
             "triggers_count": (t.get("meta") or {}).get("triggers_count")} for t in items]
    return {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "composio Python SDK toolkits.list",
            "count": len(slim), "items": slim}


async def composio_catalog() -> list[dict] | None:
    """Catalog fetched once per run (saved to data/ as evidence); None without a key or on SDK failure."""
    global _catalog
    if not os.getenv("COMPOSIO_API_KEY"):
        return None
    async with _catalog_lock:
        if _catalog is None:
            try:
                data = await asyncio.to_thread(_fetch_catalog)
            except Exception as e:  # SDK/network/auth failure -> public-page fallback, never a silent "no"
                print(f"[composio] SDK catalog unavailable ({type(e).__name__}); falling back to public toolkit pages")
                _catalog = []
                return None
            CATALOG_PATH.write_text(json.dumps(data, indent=1), encoding="utf-8")
            _catalog = data["items"]
        return _catalog or None


def _catalog_lookup(name: str, items: list[dict]) -> dict:
    # a toolkit with zero tools (e.g. slug `amazon`, whose public page redirects away) is not usable coverage
    items = [t for t in items if t.get("tools_count") is None or t["tools_count"] > 0]
    by_slug = {t["slug"]: t for t in items}
    hit = next((by_slug[s] for s in slug_candidates(name) if s in by_slug), None)
    if not hit:  # exact display-name match catches toolkits under an unexpected slug
        a = norm(re.sub(r"\(.*?\)", "", name))
        hit = next((t for t in items if a and a in (norm(t.get("name") or ""), norm(t.get("app") or ""))), None)
    if not hit:
        return {"status": "no", "slug": None, "match": None, "url": None, "source": "composio_sdk_catalog",
                "tried": slug_candidates(name), "catalog_size": len(items)}
    siblings = sorted(t["slug"] for t in items if t.get("app") and t.get("app") == hit.get("app") and t["slug"] != hit["slug"])
    match = "provider_mcp" if hit.get("toolkit_type") == "mcp" else _match(name, hit.get("name") or hit["slug"])
    return {"status": "yes", "slug": hit["slug"], "match": match,
            "url": f"https://composio.dev/toolkits/{hit['slug']}", "source": "composio_sdk_catalog",
            "tools_count": hit.get("tools_count"), "auth_schemes": hit.get("auth_schemes"), "toolkit_type": hit.get("type"), "siblings": siblings,
            "title": f"Composio SDK catalog: {hit.get('name')} (slug {hit['slug']}, {hit.get('type')}, {hit.get('tools_count')} tools, auth {hit.get('auth_schemes')})"}


async def composio_toolkit(fetcher: Fetcher, name: str) -> dict:
    """Return {status: yes|no|unknown, slug, match, url, source}. Uses the full SDK catalog when COMPOSIO_API_KEY is set,
    otherwise the public toolkit pages by slug."""
    items = await composio_catalog()
    if items:
        return _catalog_lookup(name, items)
    any_ok = False
    for slug in slug_candidates(name):
        url = f"https://composio.dev/toolkits/{slug}"
        p = await fetcher.get(url)
        # require the page to still be the toolkit page: some slugs redirect to category pages (e.g. /toolkits/amazon)
        if p.status == 200 and "| Composio" in p.title and p.final_url.rstrip("/").endswith(f"/toolkits/{slug}"):
            title_name = p.title.split(" MCP Server")[0]
            return {"status": "yes", "slug": slug, "match": _match(name, title_name), "url": url, "source": "composio.dev public toolkit page",
                    "title": p.title}
        if p.status == 404:
            any_ok = True
    # every candidate slug returned a clean 404 -> a credible (not absolute) negative
    return {"status": "no" if any_ok else "unknown", "slug": None, "match": None, "url": None, "source": "composio.dev public toolkit page",
            "tried": slug_candidates(name)}


def _match(app: str, toolkit_name: str) -> str:
    a, t = norm(re.sub(r"\(.*?\)", "", app)), norm(toolkit_name)
    if a == t:
        return "exact"
    if t and (a.startswith(t) or t in a):
        return "parent_platform"   # e.g. LinkedIn Ads -> LinkedIn toolkit
    return "alias"


def for_product(app: str, full_name: str) -> bool:
    """An MCP repo/registry entry under a vendor namespace belongs to this app when the namespace is the product itself
    (supabase/mcp, twilio-labs/mcp) or, for multi-product vendors, the repo names the product
    (zoho/analytics-mcp-server is Zoho Analytics, not Zoho CRM or Zoho Cliq)."""
    product = norm(re.sub(r"\(.*?\)", "", app))
    owner, _, repo = full_name.lower().removeprefix("io.github.").partition("/")
    o = norm(owner.split(".")[-1])          # reverse-domain namespace "com.notion" -> "notion"
    o = re.sub(r"(labs|js|hq|inc|dev|ai)$", "", o) or o   # mongodb-js -> mongodb
    if product in o:                        # supabase/mcp, twilio-labs/mcp, larksuite/lark-openapi-mcp
        return True
    rest = product[len(o):] if product.startswith(o) else product   # "Zoho CRM" under zoho -> "crm"
    leftover = re.sub(r"mcp|server|tools?|official", "", norm(repo).replace(o, ""))
    return leftover == "" or (bool(rest) and rest in leftover)      # generic vendor MCP, or names this product


def _reverse_domain_hosts(namespace: str) -> str:
    # "com.notion" -> "notion.com"
    return ".".join(reversed(namespace.split(".")))


async def mcp_registry(fetcher: Fetcher, name: str, official_hosts: list[str]) -> dict:
    terms = {norm(re.sub(r"\(.*?\)", "", name))}
    first = re.sub(r"\(.*?\)", "", name).split()[0].lower()
    if len(first) > 3:
        terms.add(norm(first))
    entries: dict[str, dict] = {}
    for term in terms:
        url = f"{MCP_REGISTRY}?search={quote(term)}&limit=100&version=latest"
        p = await fetcher.get(url, raw=True)
        try:
            data = json.loads(p.text) if p.text else {}
        except json.JSONDecodeError:
            continue
        for s in data.get("servers", []):
            srv = s.get("server", {})
            entries[srv.get("name", "")] = srv
    gh_orgs = {h.split("/", 1)[1].lower() for h in official_hosts if h.startswith("github.com/")}
    domains = {h.split("/")[0].lower() for h in official_hosts if not h.startswith("github.com")}
    official, community = [], []
    for nm, srv in entries.items():
        ns = nm.split("/")[0].lower()
        repo = ((srv.get("repository") or {}).get("url") or "").lower()
        repo_org = repo.split("github.com/")[1].split("/")[0] if "github.com/" in repo else ""
        is_official = (
            any(_reverse_domain_hosts(ns).endswith(d) or d.endswith(_reverse_domain_hosts(ns)) for d in domains if "." in ns and not ns.startswith("io.github"))
            or (ns.startswith("io.github.") and ns.split(".", 2)[2] in gh_orgs)
            or (repo_org and repo_org in gh_orgs)
        )
        # only count entries whose name actually contains the app term (registry search is a substring match)
        if not any(t in norm(nm) for t in terms):
            continue
        item = {"name": nm, "repo": repo, "website": srv.get("websiteUrl"), "description": (srv.get("description") or "")[:160]}
        (official if is_official else community).append(item)
    return {"official": official, "community": community, "registry_url": MCP_REGISTRY, "terms": sorted(terms)}


async def github_search_repos(query: str) -> list[dict]:
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=30, headers=headers) as c:
            r = await c.get("https://api.github.com/search/repositories", params={"q": query, "per_page": 15})
            if r.status_code != 200:
                return []
            return [{"full_name": i["full_name"], "url": i["html_url"], "stars": i["stargazers_count"], "description": (i.get("description") or "")[:160],
                     "archived": i.get("archived")} for i in r.json().get("items", [])]
    except httpx.HTTPError:
        return []
