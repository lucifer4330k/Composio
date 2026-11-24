# Methodology

## Input
`data/apps_input.json` holds the 100 apps exactly as listed in the brief's ten tables (name, category, hint),
extracted from the Notion page's block data on 2026-11-23. IDs 1–100 follow the brief's numbering.
Two human-curated helper fields were added:

- `official_hosts` – hosts (or host/path prefixes such as `github.com/stripe`) that count as the vendor's own property.
- `seed_urls` – documentation entry points for apps where they were known. 15 apps had no seed and were found by search.

`Paygent Connect` has no official host: its identity could not be pinned down (see limitations).

## Per-app research (LangGraph: research → extract → registry → validate)

1. **Research.** Fetch seeds, the brief hint, the homepage; run two web searches (Tavily when
   `TAVILY_API_KEY` is set, cached on disk; keyless DuckDuckGo Lite / Bing otherwise)
   (`<app> API documentation authentication`, `<app> API access pricing developer`); then follow the highest-scoring
   links (auth, OAuth, API key, getting started, reference, access, MCP…) from docs pages for two rounds. Max 14 pages.
2. **Fetch.** `httpx` with disk cache, per-host concurrency 2, 3 retries with exponential backoff + jitter on
   429/5xx/timeouts. Pages that look like JS shells or bot walls (< 2,500 chars, challenge titles, 403/503) are re-read
   through the Jina Reader. Failures are returned as data, never raised.
3. **Identity check.** A page is evidence only if its final URL is on one of the app's official hosts. Third-party pages
   are logged but never support a vendor claim.
4. **Extract (deterministic).** Regexes over official pages. Each hit becomes an `Evidence` item with field, claim, URL,
   source type, excerpt (±150 chars) and retrieval time. No hit = `unknown`.
   Access signals only count when an API/developer word is within 250 characters, so a marketing "Start for free"
   button does not become "free API access". Matches inside serialized JSON (script state in rendered docs) are
   ignored, and HTTP Basic is ignored when it only authenticates the OAuth client at the token endpoint.
   Vendor-MCP mentions count only on MCP-specific pages (URL path or title contains "mcp"/"model context protocol").
5. **Registries.** MCP Registry search (official = namespace is the vendor's reversed domain, or `io.github.<vendor-org>`,
   or repo under a vendor GitHub org), GitHub search for MCP repos in vendor orgs, and the Composio toolkit catalog
   (Python SDK `toolkits.list`; public toolkit pages by slug without a key). A vendor repo or registry entry counts for an
   app only if it names that product or is the vendor's single general MCP server (`for_product`), so Zoho's Analytics
   MCP is not credited to Zoho CRM.
6. **Validate.** Schema, identity of docs/evidence hosts, evidence completeness, contradictions (e.g. gated access but
   "ready"). Dataset level: duplicates, invented or missing IDs, docs URLs shared across apps.

## Buildability (derived, never generated)

| Verdict | Rule |
|---|---|
| ready | public API available + self-serve (free or trial) + at least one documented auth method |
| needs_access | API exists but access is paid-plan, approval, partner/sales, or API status is restricted |
| limited | no hosted API, but a CLI/library exists (wrap as a local tool) |
| not_buildable | no programmatic surface found |
| unknown | API or access not established from evidence |

## Confidence rubric (0–1)

| Component | Points |
|---|---|
| official docs URL found | 0.20 |
| auth claim backed by evidence | 0.20 |
| access claim backed by evidence (not unknown) | 0.20 |
| API-status evidence | 0.10 |
| registry checks completed (Composio + MCP) | 0.10 |
| verification: auto-verified or audited 0.20 / validated only 0.05 / disputed −0.15 | |

high ≥ 0.75, medium ≥ 0.5, low otherwise. It measures *how much evidence backs the record*, not the probability it is right.

## Opportunity score (ranking only)

`API (available 3, restricted 1) + access (free 3, trial 2, paid/approval 1, partner 0, unknown 0.5) + auth simplicity
(key/token 3, key+OAuth 2.5, OAuth 2, other 1) + breadth (broad 2, moderate 1.5, narrow/unknown 1) − 0.5 if the vendor
already ships an MCP`, multiplied by `0.6 + 0.4 × confidence`. Max 11. Apps with an existing Composio toolkit are excluded
from "easy wins". The weights are judgement calls; the score orders a list, it does not measure value.
