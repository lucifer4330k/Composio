"""Build data/apps_input.json — the trusted input dataset.

Source of the list: the 10 tables in the official Notion brief
(https://composio.notion.site/AI-Product-Ops-Intern-The-take-home-assignment-391f261a6dfe80e9946bee899d3a3762),
extracted from the page's block data on 2026-11-23. `hint` is copied verbatim from the brief.

`official` = host (or host/path prefix) that counts as the vendor's own property. Used for identity checks:
evidence from any other host can never be "official" evidence for that app.
`seeds` = human-curated documentation entry points (the one place a human helped the agent up front).
The agent still has to fetch them successfully; dead seeds are logged and discovery falls back to search.
"""
import json
from pathlib import Path

C = ["CRM and Sales", "Support and Helpdesk", "Communications and Messaging",
     "Marketing, Ads, Email and Social", "Ecommerce", "Data, SEO and Scraping",
     "Developer, Infra and Data platforms", "Productivity and Project Management",
     "Finance and Fintech", "AI, Research and Media-native"]

# (name, hint verbatim from brief, official hosts/prefixes, seed docs URLs)
APPS = [
    ("Salesforce", "salesforce.com", ["salesforce.com", "force.com", "github.com/salesforce", "github.com/salesforcecli"], ["https://developer.salesforce.com/docs/apis"]),
    ("HubSpot", "hubspot.com", ["hubspot.com", "github.com/HubSpot", "github.com/hubspot"], ["https://developers.hubspot.com/docs/api/overview"]),
    ("Pipedrive", "pipedrive.com", ["pipedrive.com", "github.com/pipedrive"], ["https://developers.pipedrive.com/docs/api/v1"]),
    ("Attio", "attio.com", ["attio.com", "github.com/attio"], ["https://docs.attio.com/"]),
    ("Twenty", "twenty.com (open-source CRM)", ["twenty.com", "github.com/twentyhq"], ["https://twenty.com/developers"]),
    ("Podio", "podio.com", ["podio.com", "github.com/podio"], ["https://developers.podio.com/"]),
    ("Zoho CRM", "zoho.com/crm", ["zoho.com", "github.com/zoho"], ["https://www.zoho.com/crm/developer/docs/api/v8/"]),
    ("Close", "close.com", ["close.com", "github.com/closeio"], ["https://developer.close.com/"]),
    ("Copper", "copper.com", ["copper.com"], ["https://developer.copper.com/"]),
    ("DealCloud", "api.docs.dealcloud.com", ["dealcloud.com", "intapp.com"], ["https://api.docs.dealcloud.com/"]),
    ("Zendesk", "zendesk.com", ["zendesk.com", "github.com/zendesk"], ["https://developer.zendesk.com/api-reference/"]),
    ("Intercom", "intercom.com", ["intercom.com", "github.com/intercom"], ["https://developers.intercom.com/docs"]),
    ("Freshdesk", "freshdesk.com", ["freshdesk.com", "freshworks.com", "github.com/freshworks"], ["https://developers.freshdesk.com/api/"]),
    ("Front", "front.com", ["front.com", "frontapp.com", "github.com/frontapp"], ["https://dev.frontapp.com/reference/introduction"]),
    ("Pylon", "usepylon.com", ["usepylon.com"], ["https://docs.usepylon.com/pylon-docs/developer/api"]),
    ("LiveAgent", "liveagent.com", ["liveagent.com", "qualityunit.com"], []),
    ("Plain", "plain.com", ["plain.com", "github.com/team-plain"], ["https://www.plain.com/docs"]),
    ("Help Scout", "helpscout.com", ["helpscout.com", "helpscout.net", "github.com/helpscout"], ["https://developer.helpscout.com/"]),
    ("Gorgias", "gorgias.com", ["gorgias.com"], ["https://developers.gorgias.com/"]),
    ("Gladly", "gladly.com", ["gladly.com"], ["https://developer.gladly.com/"]),
    ("Slack", "slack.com", ["slack.com", "slack.dev", "github.com/slackapi"], ["https://api.slack.com/"]),
    ("Twilio", "twilio.com", ["twilio.com", "github.com/twilio", "github.com/twilio-labs"], ["https://www.twilio.com/docs/usage/api"]),
    ("Zoho Cliq", "zoho.com/cliq", ["zoho.com", "github.com/zoho"], ["https://www.zoho.com/cliq/help/restapi/v2/"]),
    ("Lark (Larksuite)", "open.larksuite.com", ["larksuite.com", "feishu.cn", "github.com/larksuite"], ["https://open.larksuite.com/document/"]),
    ("Pumble", "pumble.com", ["pumble.com", "cake.com"], []),
    ("Discord", "discord.com", ["discord.com", "github.com/discord"], ["https://discord.com/developers/docs/intro"]),
    ("Telegram", "core.telegram.org", ["telegram.org"], ["https://core.telegram.org/bots/api", "https://core.telegram.org/api"]),
    ("WhatsApp Business", "developers.facebook.com/docs/whatsapp", ["developers.facebook.com/docs/whatsapp", "whatsapp.com", "business.whatsapp.com", "github.com/WhatsApp"], ["https://developers.facebook.com/docs/whatsapp/cloud-api"]),
    ("Aircall", "aircall.io", ["aircall.io", "github.com/aircall"], ["https://developer.aircall.io/api-references/"]),
    ("Vonage", "developer.vonage.com", ["vonage.com", "github.com/Vonage"], ["https://developer.vonage.com/en/api"]),
    ("Google Ads", "developers.google.com/google-ads", ["developers.google.com/google-ads", "ads.google.com", "support.google.com/google-ads", "github.com/googleads"], ["https://developers.google.com/google-ads/api/docs/start"]),
    ("Meta Ads", "developers.facebook.com/docs/marketing-apis", ["developers.facebook.com/docs/marketing-api", "developers.facebook.com/docs/marketing-apis", "facebook.com/business", "github.com/facebook"], ["https://developers.facebook.com/docs/marketing-apis"]),
    ("LinkedIn Ads", "learn.microsoft.com/linkedin/marketing", ["learn.microsoft.com/en-us/linkedin", "learn.microsoft.com/linkedin", "linkedin.com", "github.com/linkedin"], ["https://learn.microsoft.com/en-us/linkedin/marketing/"]),
    ("GoHighLevel", "highlevel.stoplight.io", ["highlevel.stoplight.io", "gohighlevel.com", "leadconnectorhq.com", "github.com/GoHighLevel"], ["https://highlevel.stoplight.io/", "https://marketplace.gohighlevel.com/docs/"]),
    ("Mailchimp", "mailchimp.com/developer", ["mailchimp.com", "github.com/mailchimp"], ["https://mailchimp.com/developer/"]),
    ("Klaviyo", "developers.klaviyo.com", ["klaviyo.com", "github.com/klaviyo"], ["https://developers.klaviyo.com/en"]),
    ("systeme.io", "systeme.io (funnel builder)", ["systeme.io"], []),
    ("Pinterest", "developers.pinterest.com", ["pinterest.com", "github.com/pinterest"], ["https://developers.pinterest.com/docs/"]),
    ("Threads (Meta)", "developers.facebook.com/docs/threads", ["developers.facebook.com/docs/threads", "threads.net", "threads.com"], ["https://developers.facebook.com/docs/threads"]),
    ("SendGrid", "sendgrid.com", ["sendgrid.com", "twilio.com/docs/sendgrid", "github.com/sendgrid"], ["https://www.twilio.com/docs/sendgrid/api-reference"]),
    ("Shopify", "shopify.dev", ["shopify.dev", "shopify.com", "github.com/Shopify"], ["https://shopify.dev/docs/api"]),
    ("WooCommerce", "woocommerce.com/document/woocommerce-rest-api", ["woocommerce.com", "woocommerce.github.io", "github.com/woocommerce"], ["https://woocommerce.com/document/woocommerce-rest-api/", "https://woocommerce.github.io/woocommerce-rest-api-docs/"]),
    ("BigCommerce", "developer.bigcommerce.com", ["bigcommerce.com", "github.com/bigcommerce"], ["https://developer.bigcommerce.com/docs/start"]),
    ("Salesforce Commerce Cloud", "developer.salesforce.com/docs/commerce", ["developer.salesforce.com/docs/commerce", "salesforce.com", "github.com/SalesforceCommerceCloud"], ["https://developer.salesforce.com/docs/commerce/commerce-api/overview"]),
    ("Magento (Adobe Commerce)", "developer.adobe.com/commerce", ["developer.adobe.com/commerce", "business.adobe.com", "experienceleague.adobe.com", "github.com/magento"], ["https://developer.adobe.com/commerce/webapi/"]),
    ("Squarespace", "developers.squarespace.com", ["squarespace.com"], ["https://developers.squarespace.com/commerce-apis/overview"]),
    ("Ecwid", "api-docs.ecwid.com", ["ecwid.com", "lightspeedhq.com", "github.com/Ecwid"], ["https://api-docs.ecwid.com/"]),
    ("Gumroad", "gumroad.com/api", ["gumroad.com", "github.com/antiwork"], ["https://gumroad.com/api"]),
    ("Amazon Selling Partner", "developer-docs.amazon.com/sp-api", ["developer-docs.amazon.com/sp-api", "developer-docs.amazon.com", "sellercentral.amazon.com", "github.com/amzn"], ["https://developer-docs.amazon.com/sp-api/"]),
    ("fanbasis", "fanbasis.com", ["fanbasis.com"], []),
    ("DataForSEO", "docs.dataforseo.com", ["dataforseo.com", "github.com/dataforseo"], ["https://docs.dataforseo.com/v3/"]),
    ("SE Ranking", "seranking.com/api", ["seranking.com"], ["https://seranking.com/api/"]),
    ("Ahrefs", "ahrefs.com/api", ["ahrefs.com", "github.com/ahrefs"], ["https://ahrefs.com/api", "https://docs.ahrefs.com/"]),
    ("MrScraper", "docs.mrscraper.com", ["mrscraper.com"], ["https://docs.mrscraper.com/"]),
    ("Apify", "docs.apify.com", ["apify.com", "github.com/apify"], ["https://docs.apify.com/api/v2"]),
    ("Firecrawl", "firecrawl.dev", ["firecrawl.dev", "github.com/mendableai", "github.com/firecrawl"], ["https://docs.firecrawl.dev/"]),
    ("Bright Data", "brightdata.com", ["brightdata.com", "github.com/brightdata", "github.com/luminati-io"], ["https://docs.brightdata.com/"]),
    ("Sherlock", "github.com/sherlock-project/sherlock", ["github.com/sherlock-project", "sherlockproject.xyz"], ["https://github.com/sherlock-project/sherlock"]),
    ("Waterfall.io", "waterfall.io (contact/company intel)", ["waterfall.io"], []),
    ("Clay", "clay.com", ["clay.com"], []),
    ("GitHub", "docs.github.com/rest", ["github.com", "docs.github.com"], ["https://docs.github.com/en/rest"]),
    ("Vercel", "vercel.com/docs/rest-api", ["vercel.com", "github.com/vercel"], ["https://vercel.com/docs/rest-api"]),
    ("Netlify", "docs.netlify.com/api", ["netlify.com", "github.com/netlify"], ["https://docs.netlify.com/api/get-started/"]),
    ("Cloudflare", "developers.cloudflare.com/api", ["cloudflare.com", "github.com/cloudflare"], ["https://developers.cloudflare.com/api/"]),
    ("Supabase", "supabase.com/docs", ["supabase.com", "github.com/supabase", "github.com/supabase-community"], ["https://supabase.com/docs/reference/api/introduction"]),
    ("Neo4j", "neo4j.com/docs/api", ["neo4j.com", "github.com/neo4j", "github.com/neo4j-contrib"], ["https://neo4j.com/docs/api/"]),
    ("Snowflake", "docs.snowflake.com", ["snowflake.com", "github.com/Snowflake-Labs", "github.com/snowflakedb"], ["https://docs.snowflake.com/en/developer-guide/sql-api/index"]),
    ("MongoDB Atlas", "mongodb.com/docs/atlas/api", ["mongodb.com", "github.com/mongodb", "github.com/mongodb-js"], ["https://www.mongodb.com/docs/atlas/api/"]),
    ("Datadog", "docs.datadoghq.com/api", ["datadoghq.com", "github.com/DataDog"], ["https://docs.datadoghq.com/api/latest/"]),
    ("Sentry", "docs.sentry.io/api", ["sentry.io", "github.com/getsentry"], ["https://docs.sentry.io/api/"]),
    ("Notion", "developers.notion.com", ["notion.com", "notion.so", "github.com/makenotion"], ["https://developers.notion.com/"]),
    ("Airtable", "airtable.com/developers", ["airtable.com", "github.com/Airtable"], ["https://airtable.com/developers/web/api/introduction"]),
    ("Linear", "developers.linear.app", ["linear.app", "github.com/linear"], ["https://linear.app/developers"]),
    ("Jira", "developer.atlassian.com", ["atlassian.com", "github.com/atlassian"], ["https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/"]),
    ("Asana", "developers.asana.com", ["asana.com", "github.com/Asana"], ["https://developers.asana.com/docs"]),
    ("Monday.com", "developer.monday.com", ["monday.com", "github.com/mondaycom"], ["https://developer.monday.com/api-reference/"]),
    ("ClickUp", "clickup.com/api", ["clickup.com", "github.com/clickup"], ["https://developer.clickup.com/"]),
    ("Coda", "coda.io/developers", ["coda.io", "github.com/coda"], ["https://coda.io/developers/apis/v1"]),
    ("Smartsheet", "smartsheet.com/developers", ["smartsheet.com", "github.com/smartsheet", "github.com/smartsheet-platform"], ["https://developers.smartsheet.com/"]),
    ("Harvest", "harvestapp.com (help.getharvest.com/api-v2)", ["harvestapp.com", "getharvest.com", "github.com/harvesthq"], ["https://help.getharvest.com/api-v2/"]),
    ("Stripe", "stripe.com/docs/api", ["stripe.com", "github.com/stripe"], ["https://docs.stripe.com/api"]),
    ("Plaid", "plaid.com/docs", ["plaid.com", "github.com/plaid"], ["https://plaid.com/docs/"]),
    ("Binance", "binance-docs.github.io", ["binance.com", "binance-docs.github.io", "github.com/binance"], ["https://developers.binance.com/docs/binance-spot-api-docs"]),
    ("Paygent Connect", "paygent (NMI-powered)", [], []),
    ("iPayX", "ipayx.ai/docs", ["ipayx.ai"], ["https://ipayx.ai/docs"]),
    ("QuickBooks", "developer.intuit.com", ["intuit.com", "github.com/intuit"], ["https://developer.intuit.com/app/developer/qbo/docs/get-started"]),
    ("Xero", "developer.xero.com", ["xero.com", "github.com/XeroAPI"], ["https://developer.xero.com/documentation/"]),
    ("Brex", "developer.brex.com", ["brex.com", "github.com/brexhq"], ["https://developer.brex.com/"]),
    ("Ramp", "docs.ramp.com", ["ramp.com", "github.com/ramp-public"], ["https://docs.ramp.com/"]),
    ("PitchBook", "pitchbook.com (research API)", ["pitchbook.com"], []),
    ("NotebookLM", "cloud.google.com/gemini (Enterprise API)", ["cloud.google.com", "notebooklm.google", "notebooklm.google.com", "support.google.com/notebooklm", "blog.google"], []),
    ("Otter AI", "help.otter.ai (MCP server)", ["otter.ai"], ["https://help.otter.ai/"]),
    ("Fathom", "fathom.video", ["fathom.video", "fathom.ai"], []),
    ("Consensus", "consensus.app (OAuth requested)", ["consensus.app"], []),
    ("Reducto", "reducto.ai (document parsing)", ["reducto.ai", "github.com/reductoai"], ["https://docs.reducto.ai/"]),
    ("Devin", "docs.devin.ai (MCP)", ["devin.ai", "cognition.ai", "github.com/CognitionAI"], ["https://docs.devin.ai/"]),
    ("higgsfield", "higgsfield.ai/cli (content suite)", ["higgsfield.ai", "github.com/higgsfield-ai"], ["https://higgsfield.ai/cli"]),
    ("Mermaid CLI", "github.com/mermaid-js/mermaid-cli", ["github.com/mermaid-js", "mermaid.js.org", "mermaid.ai"], ["https://github.com/mermaid-js/mermaid-cli"]),
    ("YouTube Transcript", "transcriptapi.com", ["transcriptapi.com"], ["https://transcriptapi.com/"]),
    ("Grain", "grain.com (meeting notes)", ["grain.com", "grain.co"], []),
]

# Disambiguation notes for names that collide with unrelated products (a failure mode seen in the reference repos).
NOTES = {
    "Close": "The CRM at close.com (Close.io), not the generic word.",
    "Front": "Front customer-communication platform (front.com / frontapp.com).",
    "Plain": "Plain support platform at plain.com, not the adjective.",
    "Twenty": "Open-source CRM twenty.com (twentyhq).",
    "Copper": "Copper CRM (copper.com), formerly ProsperWorks.",
    "Sherlock": "sherlock-project OSINT username search CLI, not other 'Sherlock' products.",
    "Mermaid CLI": "mermaid-js diagram renderer CLI, NOT the MERMAID coral-reef data platform.",
    "Paygent Connect": "Brief hint says 'NMI-powered'. Identity is ambiguous (Paygent is also a Japanese PSP); no official domain is assumed.",
    "Clay": "Clay data-enrichment platform clay.com.",
    "Grain": "Grain meeting-notes app grain.com.",
    "Consensus": "Consensus AI academic search consensus.app.",
    "Devin": "Devin AI software engineer by Cognition (devin.ai).",
    "Plaid": "Plaid fintech (plaid.com).",
    "Square": "",
}


def main() -> None:
    rows = []
    for i, (name, hint, official, seeds) in enumerate(APPS):
        rows.append({
            "id": i + 1,
            "app_name": name,
            "category": C[i // 10],
            "hint": hint,
            "official_hosts": official,
            "seed_urls": seeds,
            "disambiguation": NOTES.get(name, ""),
        })
    assert len(rows) == 100 and len({r["app_name"] for r in rows}) == 100
    out = Path(__file__).resolve().parents[1] / "data" / "apps_input.json"
    out.write_text(json.dumps({
        "source": "https://composio.notion.site/AI-Product-Ops-Intern-The-take-home-assignment-391f261a6dfe80e9946bee899d3a3762",
        "extracted_at": "2026-11-23",
        "note": "app_name, category and hint are verbatim from the brief tables. official_hosts and seed_urls are human-curated helpers.",
        "apps": rows,
    }, indent=2), encoding="utf-8")
    print(f"wrote {len(rows)} apps -> {out}")


if __name__ == "__main__":
    main()
