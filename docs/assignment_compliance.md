# Assignment compliance

Brief: https://composio.notion.site/AI-Product-Ops-Intern-The-take-home-assignment-391f261a6dfe80e9946bee899d3a3762
(read in full on 2026-11-23, including the ten app tables, which only appear in the page's block data).

| Brief requirement | Where | Status |
|---|---|---|
| Use the given list of 100 apps | `data/apps_input.json` (verbatim names, categories, hints; IDs 1–100) | done |
| Category + one-line description | `category` (brief), `product_description` (official meta description) | done; descriptions missing where no official page was read |
| Auth method(s) | `authentication_methods` + evidence | done; unknown where no evidence |
| Self-serve vs gated | `developer_access`, `approval_required`, `integration_blockers` | done |
| API surface (REST/GraphQL, breadth, existing MCP) | `public_api_status`, `api_types`, `api_surface_breadth`, `official_mcp_*`, `community_mcp_*` | done (breadth is a proxy) |
| Buildability verdict + main blocker | `toolkit_buildability` + reason + blockers (rule-derived) | done |
| Evidence URL per answer | `evidence[]` per field with excerpt | done |
| Find the patterns, insight over raw table | report "What the data says" + category matrix + opportunities; `data/insights.json` | done |
| Do it with an agent; say where a human was needed | `src/` pipeline; report "The agent" lists human inputs | done |
| Use Composio's own SDK/MCP | Composio Python SDK (`composio` 0.34.0): full toolkit catalog via `toolkits.list` (1,865 toolkits, saved to `data/composio_catalog.json`) for the registry check; `scripts/composio_first_call.py` connects GitHub through a session Connect Link and runs `GITHUB_GET_THE_AUTHENTICATED_USER` | done; public toolkit pages remain the fallback when no key is set |
| Verify accuracy on a sample, hits and misses shown | samples A (20) and B (10, hold-out, 74.5% = 35/47), misses table, 73 logged corrections | done (AI reviewer, not human) |
| Show accuracy moving from first pass to higher | stage columns: rules v1 → rules v2 → + independent pass → + review (A: 46.8% → 70.2% → 71.3%; B: 59.6% → 74.5%) | done |
| Human checks | `data/human_check.csv` (sample C: 10 random apps outside A and B, 50 rows); shown on the page once filled | sheet ready; to be filled by a person |
| Single self-explanatory HTML page | `output/index.html` | done |
| Live link | https://lucifer4330k.github.io/Composio/ (GitHub Pages, serves `output/index.html` from `main`) | done |
| Source repo + README | this folder; README with run instructions | done; not pushed to a remote |
| Say where the agent was wrong or an app defeated you | report verification + limitations sections | done |
