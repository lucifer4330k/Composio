"""Polite cached HTTP fetcher: disk cache, bounded retries with exponential backoff + jitter,
per-host concurrency limit, HTML -> text extraction. Failures are returned, never raised."""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 api-readiness-research/1.0"
RETRY_STATUS = {429, 500, 502, 503, 504}
SHELL_TITLES = re.compile(r"just a moment|access denied|attention required|error|forbidden|enable javascript|404|not found", re.I)
_render_lock = asyncio.Lock()


def _needs_render(p: "Page") -> bool:
    """Heuristic for JS-only shells / bot walls: tiny text, a 403/503, or a challenge-like title."""
    if p.status in (400, 403, 503) or (p.status == 0 and "non-html" not in p.error):
        return True
    return 200 <= p.status < 400 and (len(p.text) < 2500 or bool(SHELL_TITLES.search(p.title)))


@dataclass
class Page:
    url: str
    final_url: str
    status: int
    title: str = ""
    text: str = ""
    links: list[tuple[str, str]] = field(default_factory=list)  # (absolute url, anchor text)
    meta_description: str = ""
    error: str = ""
    fetched_at: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400 and not self.error and len(self.text) > 200


def parse_html(url: str, html: str) -> tuple[str, str, str, list[tuple[str, str]]]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.get_text(" ", strip=True) if soup.title else "")[:200]
    md = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    meta = (md.get("content") or "").strip()[:400] if md else ""
    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"]).split("#")[0]
        if href.startswith("http"):
            links.append((href, a.get_text(" ", strip=True)[:80]))
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return title, meta, text[:120_000], links[:600]


class Fetcher:
    def __init__(self, cache_dir: Path, per_host: int = 2, retries: int = 3, timeout: float = 25.0, use_cache: bool = True, transport=None):
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.retries = retries
        self.use_cache = use_cache
        self._host_sems: dict[str, asyncio.Semaphore] = {}
        self.per_host = per_host
        self.client = httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
                                        follow_redirects=True, timeout=timeout, transport=transport)
        self.stats = {"fetched": 0, "cache_hits": 0, "failed": 0, "retries": 0}

    def _key(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".json")

    def _sem(self, url: str) -> asyncio.Semaphore:
        host = urlparse(url).netloc
        if host not in self._host_sems:
            self._host_sems[host] = asyncio.Semaphore(self.per_host)
        return self._host_sems[host]

    async def get(self, url: str, raw: bool = False) -> Page:
        path = self._key(url + ("#raw" if raw else ""))
        if self.use_cache and path.exists():
            self.stats["cache_hits"] += 1
            return Page(**json.loads(path.read_text(encoding="utf-8")))
        page = await self._fetch(url, raw)
        if not raw and _needs_render(page):
            rendered = await self._render(url)
            if rendered.ok and len(rendered.text) > len(page.text):
                page = rendered
        if 0 < page.status < 400 or page.status in (404, 410):  # don't cache transient/bot-wall failures
            path.write_text(json.dumps(page.__dict__), encoding="utf-8")
        return page

    async def _fetch(self, url: str, raw: bool) -> Page:
        last_err = ""
        async with self._sem(url):
            for attempt in range(self.retries + 1):
                try:
                    r = await self.client.get(url)
                    if r.status_code in RETRY_STATUS and attempt < self.retries:
                        self.stats["retries"] += 1
                        await asyncio.sleep(min(20, (2 ** attempt) + random.random()))
                        continue
                    self.stats["fetched"] += 1
                    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    ctype = r.headers.get("content-type", "")
                    if raw or "json" in ctype or "text/plain" in ctype:
                        return Page(url, str(r.url), r.status_code, text=r.text[:400_000], fetched_at=now)
                    if "html" not in ctype and "xml" not in ctype:
                        return Page(url, str(r.url), r.status_code, error=f"non-html content-type {ctype}", fetched_at=now)
                    title, meta, text, links = parse_html(str(r.url), r.text)
                    return Page(url, str(r.url), r.status_code, title, text, links, meta, fetched_at=now)
                except (httpx.HTTPError, ValueError) as e:  # network/timeouts/decoding
                    last_err = f"{type(e).__name__}: {e}"[:200]
                    if attempt < self.retries:
                        self.stats["retries"] += 1
                        await asyncio.sleep(min(20, (2 ** attempt) + random.random()))
        self.stats["failed"] += 1
        return Page(url, url, 0, error=last_err or "failed", fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    async def _render(self, url: str) -> Page:
        """JS-rendering fallback for SPA / bot-shielded docs via the Jina Reader (keyless, rate-limited -> serialized).
        The page keeps the official URL; only the transport differs."""
        headers = {"X-Return-Format": "markdown"}
        async with _render_lock:
            for attempt in range(3):
                try:
                    r = await self.client.get("https://r.jina.ai/" + url, headers=headers, timeout=60)
                    if r.status_code == 429:
                        await asyncio.sleep(10 * (attempt + 1) + random.random())
                        continue
                    self.stats["rendered"] = self.stats.get("rendered", 0) + 1
                    await asyncio.sleep(3.2)  # stay under keyless ~20 req/min
                    md = r.text
                    title = (re.search(r"^Title: (.*)$", md, re.M) or [None, ""])[1][:200]
                    body = md.split("Markdown Content:", 1)[-1]
                    links = [(urljoin(url, u).split("#")[0], t[:80]) for t, u in re.findall(r"\[([^\]]{0,80})\]\((https?://[^)\s]+)", body)]
                    text = re.sub(r"\s+", " ", re.sub(r"\]\([^)]*\)", "]", body))
                    if r.status_code >= 400 or len(text) < 200:
                        break
                    return Page(url, url, 200, title, text[:120_000], links[:600], "", fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                except httpx.HTTPError:
                    await asyncio.sleep(3)
        return Page(url, url, 0, error="render failed")

    async def close(self):
        await self.client.aclose()
