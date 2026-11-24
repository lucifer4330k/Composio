# Architecture

```
data/apps_input.json  (100 apps from the brief + curated official hosts / seed URLs)
        │
        ▼   LangGraph StateGraph, one invocation per app, N in parallel (asyncio semaphore)
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ research     │──▶│ extract      │──▶│ registry     │──▶│ validate     │──▶ checkpoint (data/research_raw.json)
│ seeds, hint, │   │ regex rules  │   │ MCP Registry │   │ schema,      │      after every app
│ search, link │   │ over official│   │ GitHub orgs  │   │ identity,    │
│ mining       │   │ pages only   │   │ Composio     │   │ contradiction│
└──────┬───────┘   └──────────────┘   └──────────────┘   └──────────────┘
       │ Fetcher: cache · retries+jitter · per-host limit · JS-render fallback
        ▼
verify  (src/agents/verify.py)  independent pass: new queries, pass-1 URLs excluded,
        │                       same extractor on disjoint pages → agree / conflict / filled
        │                       + Composio registry re-check
        ▼
review  (data/review_adjudications.json → src/analysis/consolidate.py)
        │   field overrides with reason + source URL; before/after kept as Correction records
        ▼
data/research_verified.json ──▶ insights (src/analysis/insights.py) ──▶ data/insights.json
        │                                                                    │
        └──────────────▶ report (src/reporting/build_report.py) ◀────────────┘
                         output/index.html (self-contained), results.json/csv, verification_report.md
```

## Modules

| Path | Responsibility |
|---|---|
| `src/models/schema.py` | Pydantic models and enums. Unknown is an explicit value. |
| `src/tools/http.py` | Cached async fetcher, retries, JS-render fallback. |
| `src/tools/search.py` | Tavily when a key is set (disk-cached in `cache/search/`); keyless DuckDuckGo Lite → Bing otherwise. |
| `src/tools/registries.py` | MCP Registry, Composio toolkit lookup, GitHub repo search. |
| `src/agents/research.py` | Candidate discovery, identity check (`is_official`). |
| `src/agents/extract.py` | Evidence-anchored extraction, buildability rules, confidence rubric. |
| `src/agents/validate.py` | Record and dataset checks. |
| `src/agents/verify.py` | Independent second pass and comparison. |
| `src/workflows/graph.py` | LangGraph wiring. |
| `src/analysis/consolidate.py` | Applies verification + review, scores stages against audits. |
| `src/analysis/insights.py` | Statistics with denominators, headlines, opportunity ranking. |
| `src/reporting/` | HTML template + builder. |
| `src/main.py` | CLI, checkpoint/resume, progress, run metadata. |

## Design choices

- **Deterministic extraction.** No LLM key was available. Rules are reproducible and every positive claim is traceable
  to an excerpt. An LLM would improve access-policy reading; it would slot in between `extract` and `validate`
  as an adjudicator whose output still has to cite an excerpt that exists on a fetched page.
- **Official-host identity check** is the main defence against the failure seen in a reference repo (an unrelated
  "MERMAID" API attributed to Mermaid CLI). It is a hard filter, not a score.
- **Three separate coverage facts:** vendor MCP, community MCP, Composio toolkit. Composio pages are titled
  "X MCP Server | Composio", which is exactly why the code never reads Composio presence as vendor MCP.
