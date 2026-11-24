# Agent Toolkit Readiness — Composio AI Product Ops take-home

An evidence-first research agent that looks at the 100 apps from the brief and answers, for each one: what auth it uses,
whether a developer can get credentials alone or has to go through a paid plan / approval / partner gate, what the API
surface is, whether the vendor ships an MCP server, whether Composio already has a toolkit, and whether it could be an
agent toolkit today. Every claim carries the URL and an excerpt of the page that supports it.

**Deliverable:** [`output/index.html`](output/index.html) — one self-contained page (dataset embedded, no server, no keys).
Patterns first, then opportunities, the full 100-app explorer, how the agent works, and how accurate it is.

**Live link:** https://lucifer4330k.github.io/Composio/ (GitHub Pages, served from `output/` on `main`).

<!--RESULTS-->
## Results (run of 2026-11-23/24, all 100 apps)

| | |
|---|---|
| Buildable today with self-serve credentials | **65 / 100** |
| API exists but gated (paid plan, approval, partner/sales) | 26 / 100 |
| No hosted API (local CLI only: Sherlock, Mermaid CLI) | 2 / 100 |
| Unresolved | 7 / 100 |
| Composio already has a toolkit (SDK catalog) | 79 / 100 |
| Vendor ships its own MCP server | 56 / 100 |
| Composio toolkit but no vendor MCP found | 30 / 100 |
| Auth: OAuth2 offered / API key offered | 70 / 62 (many apps offer both) |
| Evidence items (URL + excerpt) | 2,486 |

**Accuracy** is counted per field check (API status, auth, access, vendor MCP, Composio toolkit); "unknown" counts as
not correct.

| Stage | Sample A (20 apps, 94 checks) | Hold-out B (10 apps, 47 checks) |
|---|---|---|
| Rules v1 (first full run) | 46.8% | 59.6% |
| Rules v2 (tuned on A) + Tavily search | 70.2% | 74.5% |
| + independent automated pass | 71.3% | 74.5% |
| + review (final) | 100%, not independent: review used A's audit | **74.5% (35/47)**, the honest number |

B was audited after the review file was frozen (sha256 in `data/audit_holdout.json`). The review never touched B, so
B's final number is what the pipeline achieves on its own. B's weakest field is developer access (5/9): rules still
misread pricing-page prose (Gorgias, WooCommerce, SE Ranking, Salesforce Commerce Cloud). Composio coverage was 10/10.
All verification was done by code or by an AI reviewer (Claude Code); **no human has checked these records**.


## The problem

Before Composio builds a toolkit it needs to know auth, access path, API surface and existing MCP coverage. Doing this by
hand across hundreds of apps does not scale; doing it with an LLM that guesses does not hold up. This project does it
with a pipeline that only states what an official page says, and measures how often that is right.

## Architecture

```
apps_input.json ─▶ research ─▶ fetch ─▶ identity check ─▶ extract ─▶ registries ─▶ validate   (LangGraph, per app)
                                                                                    │ checkpoint per app
independent verification pass (disjoint pages) + Composio re-check ◀────────────────┘
        ▼
review adjudications (logged before/after) ─▶ research_verified.json ─▶ insights ─▶ output/index.html
```

Details: [docs/architecture.md](docs/architecture.md) · rules and rubrics: [docs/methodology.md](docs/methodology.md) ·
verification: [docs/verification.md](docs/verification.md) · limitations and retrospective: [docs/limitations.md](docs/limitations.md) ·
requirement-by-requirement status: [docs/assignment_compliance.md](docs/assignment_compliance.md).

## Stack

Python 3.11+ (run on 3.13) · LangGraph · Pydantic v2 · httpx · BeautifulSoup · pytest. Report: plain HTML/CSS/JS, no build step.
Composio Python SDK (`composio`) for the toolkit catalog and the first live tool call (`scripts/composio_first_call.py`).
External sources: vendor docs, MCP Registry (`registry.modelcontextprotocol.io`), Composio toolkit pages (fallback), GitHub search,
Tavily search (results cached in `cache/search/`; keyless DuckDuckGo Lite / Bing HTML when no key is set), Jina Reader for
JS-rendered docs. No paid service is required; the published run used Tavily's free tier.

## Setup (Windows PowerShell)

```powershell
cd composio-ai-product-ops
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # optional: every key is optional
```

Optional environment variables (see `.env.example`): `TAVILY_API_KEY` (better search), `COMPOSIO_API_KEY`
(full toolkit catalog through the SDK, and `python scripts/composio_first_call.py`, which connects GitHub through a
Connect Link and runs one read-only tool), `GITHUB_TOKEN` (GitHub search for vendor MCP repos; unauthenticated GitHub allows
~10 searches/min, so a full run without it loses results; `$env:GITHUB_TOKEN = (gh auth token)`).

## Run

```powershell
python scripts/make_input.py                         # build data/apps_input.json from the brief's list
python -m src.main research --ids 81,15,58           # small test run: Stripe, Pylon, Sherlock
python -m src.main research --concurrency 3          # all 100; resumable — rerun to continue after a stop
                                                     # (6 caused render-queue timeouts on Windows)
python -m src.main verify                            # independent pass + registry re-check
python scripts/build_review.py                       # regenerate data/review_adjudications.json (sourced review values)
python -m src.main review                            # apply data/review_adjudications.json, score audits
python -m src.main insights
python -m src.main report                            # -> output/index.html, results.json/csv, verification_report.md
python -m src.main all                               # everything above in order
python -m src.main recheck --ids 81                  # re-research one app with a fresh fetch (policy changes)
```

Open the report: double-click `output/index.html`, or `python -m http.server 8765 --directory output` and browse to
`http://localhost:8765`.

To research an extra app, add it to `APPS` in `scripts/make_input.py` (name, hint, official hosts, optional seeds),
regenerate the input and run `research --ids <new id>`; nothing else is re-run.

## Hand check (sample C)

`data/human_check.csv` is a sheet for a person to fill: 10 apps drawn at random from the 70 outside samples A and B
(`python scripts/make_human_check.py`), one row per field (50 rows), with the agent's answer and the link it used.

1. Open the sheet in Excel or any editor.
2. For each row, open `evidence_url` (or the vendor's docs) and set `verdict` to `correct`, `wrong` or `unclear`.
3. When wrong, write the right value in `correct_value`; add `checked_by` and `checked_on` (YYYY-MM-DD).
4. Run `python -m src.main report`. The page then shows a "Hand check (sample C)" block with the score and every miss.

## Tests

```powershell
python -m pytest -q tests
```

Covers schema rejection, identity matching, evidence-anchored extraction (and that marketing copy is ignored), unknown
handling, access precedence, record/dataset validation, fetcher retry + cache + failure handling, checkpoint resume,
Composio name matching and SDK catalog lookup, official-vs-community MCP classification, auth noise filtering (JSON
blobs, OAuth-client Basic), review before/after logging, blockers matching final access, audit scoring and insight counts (17 tests). Fixtures are mock data and labelled as such; they never touch `data/`.

## Data schema (one record per app)

`id, app_name, category` (from the brief) · `product_description, official_website, developer_docs_url` ·
`public_api_status` available | restricted | unavailable | unknown · `authentication_methods` [OAuth2, API key,
Bearer/access token, Basic, JWT, HMAC/signed request, …] · `developer_access` self_serve_free | self_serve_trial |
paid_plan | approval_required | partner_or_sales | not_applicable | unknown · `approval_required` · `api_types` ·
`api_surface_breadth` · `official_mcp_status/url` · `community_mcp_status/examples` · `existing_composio_toolkit` /
`composio_toolkit_identifier` · `toolkit_buildability` ready | needs_access | limited | not_buildable | unknown, with
reason · `integration_blockers` · `confidence_score/label` · `evidence[]` {field, claim, url, source_type, excerpt,
retrieved_at, stage} · `corrections[]` {field, before, after, reason, stage, evidence_url} · `verification_status`.

## Outputs

| File | What |
|---|---|
| `data/apps_input.json` | trusted input (100 apps from the brief) |
| `data/research_raw.json` | per-app checkpoint: pass-1 record, post-verify record, URLs used, search results, logs |
| `data/research_raw_v1.json` | snapshot of the first full run (rules v1), kept to measure the tuning loop |
| `data/verification_log.json` | independent-pass results, corrections, open issues, stage accuracy |
| `data/audit.json`, `data/audit_holdout.json` | browser audits (samples A and B) |
| `data/review_adjudications.json` | reviewer corrections with reasons and sources (built by `scripts/build_review.py`, frozen before audit B) |
| `data/composio_catalog.json` | Composio SDK toolkit catalog used for the coverage check |
| `data/research_verified.json` | final dataset |
| `data/insights.json` | statistics, headlines, opportunity ranking |
| `output/index.html` | the report |
| `output/results.json`, `output/results.csv`, `output/verification_report.md` | downloads |

## Reference repositories

Read for approach, not copied: [SHANKESTI/api-readiness-atlas](https://github.com/SHANKESTI/api-readiness-atlas)
(LangGraph multi-agent layout) and [Harshith322/composio-api-audit](https://github.com/Harshith322/composio-api-audit)
(Tavily + Groq extraction, Composio SDK cross-check, honest error analysis). No data or code from either is reused.
Two lessons taken from them: the first repo's app list differs from the brief in 44 of 100 apps (generic SaaS names
replaced brief-specific ones such as iPayX, fanbasis, Sherlock), so this project re-extracted the list from the Notion
page itself; the second repo documented an identity failure (Mermaid CLI matched to an unrelated "MERMAID" API), which is
why evidence here must come from a curated official host.
