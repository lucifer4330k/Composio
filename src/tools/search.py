"""Web search. Keyless default: DuckDuckGo Lite HTML. Optional: Tavily when TAVILY_API_KEY is set.
Search results are only *candidates*: a URL becomes evidence only after it is fetched and identity-checked."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from .http import Fetcher

_ddg_lock = asyncio.Lock()


SEARCH_CACHE = Path(__file__).resolve().parents[2] / "cache" / "search"


def search_cache_path(query: str, k: int) -> Path:
    return SEARCH_CACHE / (hashlib.sha1(f"tavily|{k}|{query}".encode()).hexdigest() + ".json")


async def search(fetcher: Fetcher, query: str, k: int = 8) -> list[dict]:
    key = os.getenv("TAVILY_API_KEY")
    if key:
        path = search_cache_path(query, k)
        if fetcher.use_cache and path.exists():  # re-runs are reproducible and spend no Tavily credits
            return json.loads(path.read_text(encoding="utf-8"))
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post("https://api.tavily.com/search", json={"api_key": key, "query": query, "max_results": k})
                r.raise_for_status()
                res = [{"url": x["url"], "title": x.get("title", ""), "snippet": x.get("content", "")[:300]} for x in r.json().get("results", [])]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(res), encoding="utf-8")
            return res
        except httpx.HTTPError as e:
            print(f"[search] tavily failed ({type(e).__name__}); falling back to keyless search", flush=True)
    res = await ddg_lite(fetcher, query, k)
    return res or await bing(fetcher, query, k)  # DDG answers 202 (bot wall) when throttled


async def bing(fetcher: Fetcher, query: str, k: int = 8) -> list[dict]:
    url = "https://www.bing.com/search?setlang=en&cc=US&q=" + query.replace(" ", "+")
    async with _ddg_lock:
        page = await fetcher.get(url, raw=True)
        await asyncio.sleep(1.0)
    out, seen = [], set()
    for blk in page.text.split('class="b_algo"')[1:]:
        h2 = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not h2:
            continue
        href = h2.group(1).replace("&amp;", "&")
        if "bing.com/ck/a" in href:  # tracking redirect: real URL is base64url in u=a1...
            u = parse_qs(urlparse(href).query).get("u", [""])[0]
            try:
                href = base64.urlsafe_b64decode(u[2:] + "=" * (-len(u[2:]) % 4)).decode()
            except (ValueError, UnicodeDecodeError):
                continue
        if href.startswith("http") and href not in seen:
            seen.add(href)
            out.append({"url": href, "title": re.sub("<.*?>", "", h2.group(2)).strip(), "snippet": "", "engine": "bing"})
        if len(out) >= k:
            break
    return out


async def ddg_lite(fetcher: Fetcher, query: str, k: int = 8) -> list[dict]:
    url = "https://lite.duckduckgo.com/lite/?q=" + httpx.QueryParams({"q": query})["q"].replace(" ", "+")
    async with _ddg_lock:  # serialize: DDG throttles parallel automated queries
        page = await fetcher.get(url, raw=True)
        if page.status != 200:
            fetcher._key(url + "#raw").unlink(missing_ok=True)  # never cache a bot-wall response
            return []
        await asyncio.sleep(1.5)
    out, seen = [], set()
    for m in re.finditer(r'href="(//duckduckgo\.com/l/\?uddg=[^"]+|https?://[^"]+)"[^>]*class=.result-link.[^>]*>(.*?)</a>', page.text):
        href, title = m.group(1), re.sub("<.*?>", "", m.group(2))
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse("https:" + href).query).get("uddg", [""])[0])
        if href and href not in seen and "duckduckgo.com" not in href:
            seen.add(href)
            out.append({"url": href, "title": title.strip(), "snippet": ""})
        if len(out) >= k:
            break
    return out
