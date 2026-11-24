"""Audit helper used by the reviewer: fetch a docs page fresh (no pipeline cache) via the Jina reader and print
keyword-in-context lines, so an audit decision is made from the live page, not from the agent's evidence.
Usage: python scripts/audit_peek.py URL [regex]"""
import re
import sys

import httpx

url = sys.argv[1]
rx = re.compile(sys.argv[2] if len(sys.argv) > 2 else r"oauth|api key|api token|personal access|bearer|basic auth|free|plan|partner|approv|sandbox|mcp", re.I)
r = httpx.get("https://r.jina.ai/" + url, timeout=90, headers={"X-Return-Format": "text"})
text = re.sub(r"\s+", " ", r.text)
print(f"[{r.status_code}] {url} chars={len(text)}")
seen = 0
for m in rx.finditer(text):
    if seen >= int(sys.argv[3]) if len(sys.argv) > 3 else seen >= 14:
        break
    print("  …" + text[max(0, m.start() - 110): m.end() + 110].replace("\n", " ") + "…")
    seen += 1
