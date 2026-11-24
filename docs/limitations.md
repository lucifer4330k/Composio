# Limitations and retrospective

## Limitations

- **No LLM key.** Extraction is rule-based. Rules read standard auth vocabulary well and access policy (often prose on
  pricing pages) poorly. The review stage exists to close that gap; it was done by an AI reviewer (Claude Code) with a
  browser, not by a person.
- **Search.** The published run used Tavily (free tier; results cached in `cache/search/`, so re-runs spend no
  credits). Without a key the pipeline falls back to DuckDuckGo Lite and Bing HTML, which were weak: DuckDuckGo started
  answering HTTP 202 (bot wall) mid-run, and Bing returned off-topic results for many queries. Composio's own search
  toolkit could not replace it: executing `COMPOSIO_SEARCH` returned HTTP 410 (toolkit version retired). A missing
  search result is never read as "does not exist".
- **Access policy is the weakest field.** On hold-out B, developer access was right 5/9. Rules read auth vocabulary
  well but misread pricing-page prose (Gorgias trial read as partner/sales, SE Ranking paid plan read as free).
- **Rendering fallback is rate-limited.** JS-only docs (Salesforce, Lark, Xero…) are read through the keyless Jina
  Reader at ~20 requests/min, serialized. This made the full run slow (~1 app/min) and some pages still failed.
- **Gated documentation.** Partner/enterprise docs (e.g. DealCloud credentials, Otter's Enterprise API, PitchBook,
  fanbasis' password-protected v3 docs) cannot be read without an account. Those records say restricted/unknown.
- **Composio coverage** comes from the full SDK catalog (`toolkits.list`, fetched once per run) matched by slug
  candidates, then by exact display name. Toolkits with zero tools are ignored (slug `amazon` has 0 tools and its page
  redirects away). Provider MCP toolkits (`*_mcp`, e.g. `otter_ai_mcp`) count as coverage and are labelled
  `provider_mcp`; parent-platform matches (LinkedIn Ads → LinkedIn) are labelled too. A Composio toolkit is never read
  as the vendor's own MCP server. Without a key the pipeline falls back to public toolkit pages by slug.
- **Vendor MCP "unknown"** means it was not found in the MCP Registry, the vendor GitHub org or the pages read.
  Vendors also announce MCP servers in blog posts we did not crawl.
- **Ambiguous identities.** Paygent Connect could not be tied to one product. fanbasis rebranded to Commas
  (fanbasis.com redirects); the identity check correctly refused commas.com until a reviewer confirmed it.
- **Sampled accuracy.** Accuracy is measured on 20 + 10 apps, not 100. Small samples: read percentages as ranges.
  Hold-out B: 35/47 field checks correct (74.5%).
- **Review coverage.** The review covers 40 records (113 field values, each with a source URL; 8 of them are one-line descriptions added after audit B, see `post_audit_changes` in `data/audit_holdout.json`). Records that were
  disputed but not reviewed keep their automated values and their `disputed` status in the dataset.
- **Known wrong value kept on purpose.** Salesforce Commerce Cloud is in hold-out B, so the review did not touch it; its
  record still says self-serve and available, while the audit found a licensed-realm requirement.
- **API breadth** is a proxy (count of API-reference links on pages read), not an endpoint count.
- **Point in time.** Vendor policies change. Use `python -m src.main recheck --ids N` to refresh an app.

## Retrospective

- The first identity rule allowed any `github.com/<org>` prefix to match longer org names (`github.com/meta` would
  match `github.com/metabase`). A unit test now pins whole-segment matching.
- Composio slug `amazon` 308-redirects to a category page whose title still ends in "| Composio". The first version
  would have counted that as a toolkit. The check now requires the final URL to stay on `/toolkits/<slug>`, and the
  verify stage re-runs the registry check and logs any change as a correction.
- Marketing pages poisoned access signals ("Start for free" on a product homepage became "free API access"). Fix:
  access phrases only count within 250 characters of API/developer vocabulary; product-marketing pages are capped at 2.
- Audit sample A showed auth over-reporting ("Basic" from plan names, "JWT"/"HMAC" from webhook signing) and
  marketplace app-review language read as an access gate (Intercom). Rules v2 keeps secondary auth methods only when
  they appear on an auth-focused page, and splits "approval before any production call" from "marketplace listing review".
  Sample B was held out of this tuning so the final accuracy is not measured on data the rules were fitted to.
- The audit itself was wrong twice. Audit A first recorded "no Composio toolkit" for NotebookLM and Otter AI because the
  auditor only tried slugs `notebooklm`, `otter` and `otter_ai` (all 404). The SDK catalog listed `notebook_lm` and
  `otter_ai_mcp`, and both public pages return 200. Both truths were corrected in `data/audit.json`, with a note on each.
  The lesson: slug guessing undercounts coverage, for the agent and for a reviewer alike.
- The vendor-MCP rule over-credited 66 apps at first: any official page mentioning "MCP" counted, and a vendor GitHub org
  repo counted for every product of that vendor (Zoho's Analytics MCP credited Zoho CRM and Zoho Cliq). Now doc mentions
  count only on MCP-specific pages, and a repo or registry entry must name the product or be the vendor's single
  general MCP server (`for_product`).
- With Tavily the agent read more pages, and auth over-reporting came back: `JWT` matched feature-flag JSON embedded
  in rendered docs pages (Notion, Attio), and `Basic` matched the OAuth token-exchange step (Notion). Matches inside
  serialized JSON, and Basic near `oauth/token` / `client_id`, are now skipped (test `test_auth_ignores_json_blobs_*`).
- Running 6 apps at once made 33 apps time out in the render queue; the verify pass once hung at 52/100 on one fetch.
  Verify now has a per-app timeout (`verify_timeout_s`); research is run at concurrency 3.
