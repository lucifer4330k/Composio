# Verification report

Records: 100. Generated from data/verification_log.json.

## Audit sample (A)

Apps: 20 — Attio, DealCloud, Intercom, Freshdesk, Slack, Zoho Cliq, Lark (Larksuite), Amazon Selling Partner, DataForSEO, Supabase, Notion, Linear, Asana, Xero, Paygent Connect, fanbasis, iPayX, Otter AI, Consensus, NotebookLM

Method: 14 apps drawn with random.Random(20261123) from the 94 non-high-risk apps, plus 6 a-priori high-risk apps (ambiguous identity or brief-flagged hints). Each field checked against the vendor's live docs, opened fresh (not the pipeline cache). A field is left out when the auditor could not establish the truth.

| Stage | Correct | Wrong | Unknown | Checked | Accuracy |
|---|---|---|---|---|---|
| rules_v1 | 44 | 13 | 37 | 94 | 46.8% |
| pass1 | 66 | 18 | 10 | 94 | 70.2% |
| after_auto_verify | 67 | 19 | 8 | 94 | 71.3% |
| final | 94 | 0 | 0 | 94 | 100.0% |

Per-field (final stage):

| Field | Correct | Wrong | Unknown | n |
|---|---|---|---|---|
| public_api_status | 20 | 0 | 0 | 20 |
| authentication_methods | 19 | 0 | 0 | 19 |
| developer_access | 20 | 0 | 0 | 20 |
| official_mcp_status | 15 | 0 | 0 | 15 |
| existing_composio_toolkit | 20 | 0 | 0 | 20 |

Misses at pass 1:

- DealCloud: wrong on field, got `available` expected `restricted`
- Freshdesk: wrong on field, got `restricted` expected `available`
- Lark (Larksuite): unknown on field, got `unknown` expected `available`
- Linear: wrong on field, got `restricted` expected `available`
- fanbasis: unknown on field, got `unknown` expected `available`
- Otter AI: wrong on field, got `available` expected `restricted`
- Attio: wrong on field, got `['API key', 'Basic', 'Bearer/access token', 'OAuth2']` expected `['OAuth2', 'API key']`
- Freshdesk: wrong on field, got `['API key', 'OAuth2']` expected `['API key']`
- Zoho Cliq: wrong on field, got `['API key', 'Bearer/access token', 'OAuth2']` expected `['OAuth2']`
- Lark (Larksuite): wrong on field, got `['OAuth2']` expected `['OAuth2', 'Bearer/access token']`
- Amazon Selling Partner: unknown on field, got `[]` expected `['OAuth2']`
- DataForSEO: wrong on field, got `['API key', 'Basic', 'Bearer/access token']` expected `['Basic']`
- Notion: wrong on field, got `['API key', 'Basic', 'Bearer/access token', 'JWT', 'OAuth2']` expected `['OAuth2', 'Bearer/access token']`
- fanbasis: unknown on field, got `[]` expected `['API key']`
- NotebookLM: wrong on field, got `['API key', 'Basic', 'Bearer/access token', 'JWT', 'OAuth2']` expected `['OAuth2']`
- Freshdesk: wrong on field, got `partner_or_sales` expected `self_serve_trial`
- Zoho Cliq: unknown on field, got `unknown` expected `self_serve_free`
- Lark (Larksuite): wrong on field, got `partner_or_sales` expected `self_serve_free`
- Amazon Selling Partner: wrong on field, got `self_serve_free` expected `approval_required`
- Linear: wrong on field, got `partner_or_sales` expected `self_serve_free`
- Xero: wrong on field, got `approval_required` expected `self_serve_free`
- fanbasis: unknown on field, got `unknown` expected `self_serve_free`
- Otter AI: wrong on field, got `self_serve_free` expected `partner_or_sales`
- NotebookLM: wrong on field, got `self_serve_free` expected `paid_plan`
- Attio: unknown on field, got `unknown` expected `yes`
- Slack: unknown on field, got `unknown` expected `yes`
- Asana: unknown on field, got `unknown` expected `yes`
- fanbasis: unknown on field, got `unknown` expected `yes`

## Hold-out sample (B)

Apps: 10 — Zoho CRM, Close, Copper, Gorgias, WooCommerce, Salesforce Commerce Cloud, SE Ranking, MrScraper, Neo4j, Airtable

Method: 10 apps drawn with random.Random(20261123) and set aside before any extractor tuning or review. Audited only after data/review_adjudications.json was frozen (sha256 192487032ff3692eddf2aefa529f3350a0fbde123875021fbec3324e79244d44); no pipeline rule or review value was changed afterwards. A field is left out when the auditor could not establish the truth (GitHub blocked the reader for the Salesforce Commerce Cloud MCP check). 2026-11-24, after this audit: one-line descriptions were added to the review for 8 apps outside sample B (product_description is not an audited field), and blockers are now reconciled with the final access value. No audited field and no sample-B record changed. Review file sha256 after the change: a783f2316dec16464e59ff77d5d99c07a6f676ece36db758ca475d98c2d11f89.

| Stage | Correct | Wrong | Unknown | Checked | Accuracy |
|---|---|---|---|---|---|
| rules_v1 | 28 | 10 | 9 | 47 | 59.6% |
| pass1 | 35 | 10 | 2 | 47 | 74.5% |
| after_auto_verify | 35 | 10 | 2 | 47 | 74.5% |
| final | 35 | 10 | 2 | 47 | 74.5% |

Per-field (final stage):

| Field | Correct | Wrong | Unknown | n |
|---|---|---|---|---|
| public_api_status | 7 | 3 | 0 | 10 |
| authentication_methods | 7 | 3 | 0 | 10 |
| developer_access | 5 | 4 | 0 | 9 |
| official_mcp_status | 6 | 0 | 2 | 8 |
| existing_composio_toolkit | 10 | 0 | 0 | 10 |

Misses at pass 1:

- Gorgias: wrong on field, got `restricted` expected `available`
- WooCommerce: wrong on field, got `restricted` expected `available`
- Salesforce Commerce Cloud: wrong on field, got `available` expected `restricted`
- MrScraper: wrong on field, got `['API key', 'Bearer/access token', 'OAuth2']` expected `['Bearer/access token']`
- Neo4j: wrong on field, got `['Basic', 'Bearer/access token', 'JWT']` expected `['Basic']`
- Airtable: wrong on field, got `['API key', 'Bearer/access token', 'OAuth2']` expected `['Bearer/access token', 'OAuth2']`
- Gorgias: wrong on field, got `partner_or_sales` expected `self_serve_trial`
- WooCommerce: wrong on field, got `partner_or_sales` expected `self_serve_free`
- Salesforce Commerce Cloud: wrong on field, got `self_serve_free` expected `partner_or_sales`
- SE Ranking: wrong on field, got `self_serve_free` expected `paid_plan`
- Copper: unknown on field, got `unknown` expected `yes`
- WooCommerce: unknown on field, got `unknown` expected `yes`

## Automated independent pass (all records)

Records: 100

- agree: 61
- disputed: 21
- no_independent_evidence: 12
- partial: 6

## Corrections (73)

| App | Field | Before | After | Stage | Reason |
|---|---|---|---|---|---|
| Attio | authentication_methods | ['OAuth2', 'API key', 'Bearer/access token', 'Basic'] | ['OAuth2', 'API key'] | review | audit sample A: OAuth 2.0 auth-code flow or a workspace API key |
| Attio | official_mcp_status | unknown | yes | review | audit sample A: checked against the live vendor page |
| DealCloud | public_api_status | available | restricted | review | audit sample A: docs public; credentials only for DealCloud (Intapp) customers |
| DealCloud | authentication_methods | ['API key', 'OAuth2'] | ['OAuth2', 'API key'] | review | audit sample A: OAuth2 client-credentials using client_id + apiKey |
| Zendesk | developer_access | self_serve_free | self_serve_trial | review | development uses a Zendesk trial or a sponsored account |
| Intercom | authentication_methods | ['OAuth2', 'API key', 'Bearer/access token', 'HMAC/signed request'] | ['OAuth2', 'Bearer/access token'] | review | audit sample A: checked against the live vendor page |
| Freshdesk | public_api_status | restricted | available | review | audit sample A: checked against the live vendor page |
| Freshdesk | authentication_methods | ['API key', 'OAuth2'] | ['API key'] | review | audit sample A: personal API key sent as HTTP Basic username |
| Freshdesk | developer_access | partner_or_sales | self_serve_trial | review | audit sample A: trial accounts get 50 calls/min |
| Pylon | developer_access | unknown | paid_plan | verify | pass 1 found no access signal; independent pass did |
| Slack | authentication_methods | ['Bearer/access token', 'OAuth2'] | ['OAuth2'] | review | audit sample A: checked against the live vendor page |
| Slack | official_mcp_status | unknown | yes | review | audit sample A: checked against the live vendor page |
| Zoho Cliq | developer_access | unknown | self_serve_free | verify | pass 1 found no access signal; independent pass did |
| Zoho Cliq | authentication_methods | ['OAuth2', 'Bearer/access token', 'API key'] | ['OAuth2'] | review | audit sample A: REST API follows OAuth 2.0 only |
| Lark (Larksuite) | public_api_status | unknown | available | review | audit sample A: checked against the live vendor page |
| Lark (Larksuite) | authentication_methods | ['OAuth2'] | ['OAuth2', 'Bearer/access token'] | review | audit sample A: App ID + App Secret -> tenant_access_token; OAuth 2.0 for user_access_token |
| Lark (Larksuite) | developer_access | partner_or_sales | self_serve_free | review | audit sample A: create an app in the open platform console |
| Lark (Larksuite) | product_description |  | Lark (Larksuite): team collaboration suite (messaging, docs, calendar) with the Lark Developer open platform. | review | official homepage could not be read by the pipeline; description from the vendor's docs page |
| Discord | developer_access | approval_required | self_serve_free | review | anyone can create an app and bot token in the developer portal; verification applies only to larger bots |
| Discord | authentication_methods | ['OAuth2', 'Bearer/access token', 'JWT'] | ['OAuth2', 'Bearer/access token'] | review | OAuth2 for user auth, bot token for bot calls; the JWT hit was page noise |
| Telegram | developer_access | unknown | self_serve_free | review | bot token from BotFather, no approval |
| Telegram | authentication_methods | ['OAuth2'] | ['Bearer/access token'] | review | bot token sent in the request URL; the OAuth2 hit is not Bot API auth |
| WhatsApp Business | public_api_status | restricted | available | review | Cloud API get-started: create a Meta app, generate an access token, send a test message |
| WhatsApp Business | developer_access | partner_or_sales | self_serve_free | review | test messages need only a Meta developer account and a temporary access token (production needs business verification) |
| WhatsApp Business | authentication_methods | [] | ['Bearer/access token'] | review | access token in the Authorization header |
| WhatsApp Business | product_description |  | WhatsApp Business Platform: Cloud API for businesses to send and receive WhatsApp messages. | review | official homepage could not be read by the pipeline; description from the vendor's docs page |
| Meta Ads | authentication_methods | [] | ['OAuth2'] | review | Marketing API uses Facebook Login access tokens (OAuth2) |
| Meta Ads | developer_access | unknown | approval_required | review | apps request permissions through App Review; Full Access needs a usage threshold |
| Meta Ads | product_description |  | Meta Ads: Marketing API for creating and managing ads and reporting on Facebook and Instagram. | review | official homepage could not be read by the pipeline; description from the vendor's docs page |
| Threads (Meta) | authentication_methods | [] | ['OAuth2'] | review | Threads API uses OAuth user access tokens |
| Threads (Meta) | developer_access | unknown | approval_required | review | permissions for users without an app role must pass App Review |
| Threads (Meta) | product_description |  | Threads (Meta): API for publishing posts and reading replies and insights on Threads. | review | official homepage could not be read by the pipeline; description from the vendor's docs page |
| Gumroad | developer_access | unknown | self_serve_free | review | register an OAuth application yourself |
| Amazon Selling Partner | authentication_methods | [] | ['API key', 'Bearer/access token', 'OAuth2'] | verify | pass 1 found no auth evidence; independent pass did |
| Amazon Selling Partner | authentication_methods | ['API key', 'Bearer/access token', 'OAuth2'] | ['OAuth2'] | review | audit sample A: Login with Amazon (LWA) OAuth |
| Amazon Selling Partner | developer_access | self_serve_free | approval_required | review | audit sample A: Amazon evaluates the Developer Profile and may grant or deny access |
| fanbasis | public_api_status | unknown | available | review | audit sample A: fanbasis.com redirects to commas.com: 'FanBasis is now Commas' |
| fanbasis | authentication_methods | [] | ['API key'] | review | audit sample A: API key from dashboard Account -> API Keys |
| fanbasis | developer_access | unknown | self_serve_free | review | audit sample A: self-serve account + sandbox environment |
| fanbasis | official_mcp_status | unknown | yes | review | audit sample A: docs have an MCP section |
| fanbasis | product_description |  | fanbasis (now Commas): API to collect payments and manage subscriptions; docs at apidocs.fan. | review | official homepage could not be read by the pipeline; description from the vendor's docs page |
| DataForSEO | authentication_methods | ['API key', 'Basic', 'Bearer/access token'] | ['Basic'] | review | audit sample A: Basic authentication is the only way; API login/password from dashboard |
| DataForSEO | developer_access | self_serve_free | self_serve_trial | review | audit sample A: free account, then pay-as-you-go |
| Ahrefs | developer_access | approval_required | paid_plan | review | API is available on eligible paid plans; other plans get limited free test queries |
| Sherlock | developer_access | unknown | not_applicable | review | no API credentials exist; installed locally |
| Supabase | authentication_methods | ['API key', 'JWT', 'OAuth2', 'Bearer/access token'] | ['API key'] | review | audit sample A: checked against the live vendor page |
| Snowflake | product_description |  | Snowflake: cloud data platform for warehousing, SQL analytics and data sharing. | review | official homepage could not be read by the pipeline; description from the vendor's docs page |
| Notion | authentication_methods | ['Bearer/access token', 'OAuth2', 'JWT', 'Basic', 'API key'] | ['OAuth2', 'Bearer/access token'] | review | audit sample A: internal integration token / PAT, or OAuth 2.0 for public integrations |
| Linear | public_api_status | restricted | available | review | audit sample A: checked against the live vendor page |
| Linear | authentication_methods | ['OAuth2', 'API key', 'Bearer/access token'] | ['OAuth2', 'API key'] | review | audit sample A: checked against the live vendor page |
| Linear | developer_access | partner_or_sales | self_serve_free | review | audit sample A: checked against the live vendor page |
| Jira | developer_access | partner_or_sales | self_serve_free | review | Jira has a free plan (up to 10 users); OAuth apps are created in the self-serve developer console |
| Jira | authentication_methods | ['Bearer/access token', 'Basic', 'OAuth2', 'JWT', 'API key'] | ['OAuth2', 'Basic'] | review | OAuth 2.0 (3LO) apps, or HTTP Basic with account email + API token; JWT/API-key/Bearer hits were not separate methods |
| Asana | authentication_methods | ['Bearer/access token', 'OAuth2', 'API key'] | ['OAuth2', 'Bearer/access token'] | review | audit sample A: OAuth, personal access tokens; OIDC on top of OAuth |
| Asana | official_mcp_status | unknown | yes | review | audit sample A: checked against the live vendor page |
| Coda | authentication_methods | [] | ['API key', 'Basic', 'Bearer/access token', 'HMAC/signed request', 'OAuth2'] | verify | pass 1 found no auth evidence; independent pass did |
| Coda | public_api_status | unknown | available | review | documented REST API v1 |
| Coda | developer_access | unknown | self_serve_free | review | API available to all users free of charge, in free and paid workspaces |
| Coda | authentication_methods | ['API key', 'Basic', 'Bearer/access token', 'HMAC/signed request', 'OAuth2'] | ['Bearer/access token'] | review | API token as Bearer header |
| iPayX | authentication_methods | ['API key', 'Bearer/access token'] | ['API key'] | review | audit sample A: Authorization: Bearer ipx_live_... |
| iPayX | product_description |  | iPayX Protocol: FINTRAC-registered FX forensic audit layer with developer docs. | review | official homepage could not be read by the pipeline; description from the vendor's docs page |
| Xero | developer_access | approval_required | self_serve_free | review | audit sample A: free developer account with demo company |
| PitchBook | product_description |  | PitchBook: private-market data provider; the brief lists its research API (pricing page blocked automated reading). | review | official homepage could not be read by the pipeline; description from the vendor's docs page |
| NotebookLM | authentication_methods | ['OAuth2', 'JWT', 'API key', 'Basic', 'Bearer/access token'] | ['OAuth2'] | review | audit sample A: Google Cloud user access token |
| NotebookLM | developer_access | self_serve_free | paid_plan | review | audit sample A: requires an active NotebookLM Enterprise license |
| Otter AI | public_api_status | available | restricted | review | audit sample A: Public API for Enterprise customers; contact account manager |
| Otter AI | authentication_methods | ['API key', 'Bearer/access token'] | ['API key'] | review | audit sample A: checked against the live vendor page |
| Otter AI | developer_access | self_serve_free | partner_or_sales | review | audit sample A: checked against the live vendor page |
| Consensus | authentication_methods | ['API key', 'Bearer/access token', 'OAuth2'] | ['API key'] | review | audit sample A: x-api-key header |
| Mermaid CLI | public_api_status | available | unavailable | review | Mermaid CLI is an open-source command-line renderer (mmdc); no hosted API |
| Mermaid CLI | developer_access | self_serve_free | not_applicable | review | no API credentials exist; installed locally |
| Mermaid CLI | authentication_methods | ['Bearer/access token', 'API key'] | [] | review | no auth: local tool |
| Mermaid CLI | api_types | ['CLI', 'REST', 'Webhooks', 'SDK'] | ['CLI'] | review | local command-line tool |

## Open validation issues

- #4: validation: evidence: official MCP claimed without URL
- #21: validation: evidence: official MCP claimed without URL
- #31: validation: identity: official_website support.google.com is not an official host for Google Ads
- #33: validation: identity: official_website learn.microsoft.com is not an official host for LinkedIn Ads
- #38: validation: identity: official_website github.com is not an official host for Pinterest
- #40: validation: identity: official_website www.twilio.com is not an official host for SendGrid
- #45: validation: identity: official_website developer.adobe.com is not an official host for Magento (Adobe Commerce)
- #49: validation: identity: official_website github.com is not an official host for Amazon Selling Partner
- #50: validation: evidence: official MCP claimed without URL; validation: evidence: API available but no docs URL; validation: identity: evidence marked official from foreign host apidocs.fan
- #58: validation: identity: official_website github.com is not an official host for Sherlock
- #75: validation: evidence: official MCP claimed without URL
- #83: validation: identity: official_website github.com is not an official host for Binance
- #98: validation: identity: official_website github.com is not an official host for Mermaid CLI

## Spot-check checklist

- [ ] Open 10 random rows; click each evidence link; confirm the excerpt is on the page and supports the claim.
- [ ] Re-check every 'needs_access' verdict against the vendor pricing / partner page.
- [ ] Confirm identity for fanbasis, Paygent Connect, iPayX, Waterfall.io, Sherlock, Mermaid CLI.
- [ ] Spot-check 5 'official MCP = yes' rows: is the server published by the vendor?
- [ ] Spot-check 5 Composio toolkit matches on composio.dev/toolkits.
