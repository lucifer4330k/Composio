"""Builds data/review_adjudications.json (the review stage). Reviewer: Claude Code (AI), not a human.

Every value below is backed by a page fetched on the check date; the excerpt is quoted from that page.
Hold-out sample B is excluded on purpose: it is audited only after this file is frozen.
Sample A values are copied from data/audit.json, so final-stage accuracy on sample A is not independent.

  python scripts/build_review.py && python -m src.main review
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = {7, 8, 9, 19, 42, 44, 52, 54, 66, 72}
D = "2026-11-24"
apps: dict = {}


def add(i, field, value, reason, url, src="official_docs", excerpt=None):
    assert int(i) not in HOLDOUT, f"hold-out app {i} must not be reviewed before the freeze"
    a = apps.setdefault(str(i), {"status": "reviewed", "checked_at": D, "fields": {}})
    a["fields"][field] = {"value": value, "reason": reason, "url": url, "source_type": src, **({"excerpt": excerpt} if excerpt else {})}


# 1) Audit sample A: the audited truth, each with the URL the audit opened.
audit = json.loads((ROOT / "data" / "audit.json").read_text(encoding="utf-8"))
for i, t in audit["apps"].items():
    for f, x in t["fields"].items():
        if f == "existing_composio_toolkit":
            continue  # registry fact: the SDK catalog check owns it
        v = x["primary"] if f == "authentication_methods" else x["value"]
        if v == "unknown":
            continue
        add(i, f, v, f"audit sample A: {x.get('note') or 'checked against the live vendor page'}", x.get("url"),
            "official_github" if "github.com" in (x.get("url") or "") else "official_docs")
apps["84"] = {"status": "reviewed_unresolved", "checked_at": D, "fields": {}}  # Paygent: identity not established

# 2) Outside sample A
add(74, "developer_access", "self_serve_free", "Jira has a free plan (up to 10 users); OAuth apps are created in the self-serve developer console",
    "https://www.atlassian.com/software/jira/pricing", "official_site", "Free forever for 10 users $0")
add(74, "authentication_methods", ["OAuth2", "Basic"], "OAuth 2.0 (3LO) apps, or HTTP Basic with account email + API token; JWT/API-key/Bearer hits were not separate methods",
    "https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/", excerpt="basic authentication with an Atlassian account email address and API token")
add(26, "developer_access", "self_serve_free", "anyone can create an app and bot token in the developer portal; verification applies only to larger bots",
    "https://discord.com/developers/docs/quick-start/getting-started", excerpt="Step 1: Creating an app ... Reset Token to generate a new bot token")
add(26, "authentication_methods", ["OAuth2", "Bearer/access token"], "OAuth2 for user auth, bot token for bot calls; the JWT hit was page noise",
    "https://discord.com/developers/docs/quick-start/getting-started")
add(32, "authentication_methods", ["OAuth2"], "Marketing API uses Facebook Login access tokens (OAuth2)",
    "https://developers.facebook.com/docs/marketing-api/get-started/authorization")
add(32, "developer_access", "approval_required", "apps request permissions through App Review; Full Access needs a usage threshold",
    "https://developers.facebook.com/docs/marketing-api/get-started/authorization", excerpt="During App Review, your app must also request specific permissions and features")
add(39, "authentication_methods", ["OAuth2"], "Threads API uses OAuth user access tokens", "https://developers.facebook.com/docs/threads/get-started")
add(39, "developer_access", "approval_required", "permissions for users without an app role must pass App Review",
    "https://developers.facebook.com/docs/threads/get-started", excerpt="each permission must first be approved through the App Review process")
add(28, "public_api_status", "available", "Cloud API get-started: create a Meta app, generate an access token, send a test message",
    "https://developers.facebook.com/docs/whatsapp/cloud-api/get-started")
add(28, "developer_access", "self_serve_free", "test messages need only a Meta developer account and a temporary access token (production needs business verification)",
    "https://developers.facebook.com/docs/whatsapp/cloud-api/get-started", excerpt="Click Generate access token to generate a temporary access token to send a test message")
add(28, "authentication_methods", ["Bearer/access token"], "access token in the Authorization header", "https://developers.facebook.com/docs/whatsapp/cloud-api/get-started")
add(11, "developer_access", "self_serve_trial", "development uses a Zendesk trial or a sponsored account",
    "https://developer.zendesk.com/documentation/api-basics/getting-started/getting-a-trial-or-sponsored-account-for-development/")
add(53, "developer_access", "paid_plan", "API is available on eligible paid plans; other plans get limited free test queries",
    "https://docs.ahrefs.com/docs/api/reference/introduction", excerpt="Ahrefs API is available on eligible paid plans")
add(27, "developer_access", "self_serve_free", "bot token from BotFather, no approval", "https://core.telegram.org/bots/tutorial")
add(27, "authentication_methods", ["Bearer/access token"], "bot token sent in the request URL; the OAuth2 hit is not Bot API auth",
    "https://core.telegram.org/bots/tutorial", excerpt="https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe")
add(78, "public_api_status", "available", "documented REST API v1", "https://coda.io/developers/apis/v1")
add(78, "developer_access", "self_serve_free", "API available to all users free of charge, in free and paid workspaces",
    "https://coda.io/developers/apis/v1", excerpt="API available to all of our users free of charge, in both free and paid workspaces")
add(78, "authentication_methods", ["Bearer/access token"], "API token as Bearer header", "https://coda.io/developers/apis/v1")
add(48, "developer_access", "self_serve_free", "register an OAuth application yourself", "https://gumroad.com/api",
    excerpt="To start using the API, you'll need to register your OAuth application")
for i, name, url, what in ((58, "Sherlock", "https://github.com/sherlock-project/sherlock", "open-source CLI that searches usernames across sites"),
                           (98, "Mermaid CLI", "https://github.com/mermaid-js/mermaid-cli", "open-source command-line renderer (mmdc)")):
    add(i, "public_api_status", "unavailable", f"{name} is an {what}; no hosted API", url, "official_github")
    add(i, "developer_access", "not_applicable", "no API credentials exist; installed locally", url, "official_github")
    add(i, "authentication_methods", [], "no auth: local tool", url, "official_github")
    add(i, "api_types", ["CLI"], "local command-line tool", url, "official_github")
# one-line descriptions missing because the official homepage was a bot wall or JS shell; taken from the vendor docs pages
for i, desc, url in ((24, "Lark (Larksuite): team collaboration suite (messaging, docs, calendar) with the Lark Developer open platform.", "https://open.larksuite.com/"),
                     (28, "WhatsApp Business Platform: Cloud API for businesses to send and receive WhatsApp messages.", "https://developers.facebook.com/docs/whatsapp/cloud-api/get-started"),
                     (32, "Meta Ads: Marketing API for creating and managing ads and reporting on Facebook and Instagram.", "https://developers.facebook.com/docs/marketing-api/get-started/authorization"),
                     (39, "Threads (Meta): API for publishing posts and reading replies and insights on Threads.", "https://developers.facebook.com/docs/threads/get-started"),
                     (50, "fanbasis (now Commas): API to collect payments and manage subscriptions; docs at apidocs.fan.", "https://apidocs.fan/"),
                     (67, "Snowflake: cloud data platform for warehousing, SQL analytics and data sharing.", "https://docs.snowflake.com/"),
                     (85, "iPayX Protocol: FINTRAC-registered FX forensic audit layer with developer docs.", "https://ipayx.ai/docs"),
                     (90, "PitchBook: private-market data provider; the brief lists its research API (pricing page blocked automated reading).", "https://pitchbook.com/")):
    add(i, "product_description", desc, "official homepage could not be read by the pipeline; description from the vendor's docs page", url)
# disputed by the automated second pass, confirmed self-serve by the source page (no value change)
for i, url in ((1, "https://developer.salesforce.com/docs/platform/api-rest/guide/quickstart-dev-org.html"),
               (3, "https://pipedrive.readme.io/docs/marketplace-creating-a-proper-app"),
               (36, "https://developers.klaviyo.com/en/docs/authenticate_"),
               (62, "https://vercel.com/docs/rest-api"),
               (77, "https://developer.clickup.com/docs/authentication"),
               (81, "https://docs.stripe.com/keys")):
    add(i, "developer_access", "self_serve_free", "disputed by the automated second pass; the source page confirms self-serve credentials", url)

out = {"reviewer": "Claude Code review agent (AI, this session). Not a human review.",
       "checked_at": D, "frozen_at": "2026-11-24",
       "rule": "Hold-out sample B (ids 7,8,9,19,42,44,52,54,66,72) is excluded and audited only after this file is frozen. "
               "Sample A values come from data/audit.json, so final-stage accuracy on sample A is not an independent measure.",
       "apps": dict(sorted(apps.items(), key=lambda kv: int(kv[0])))}
(ROOT / "data" / "review_adjudications.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print(len(out["apps"]), "records,", sum(len(a["fields"]) for a in out["apps"].values()), "field adjudications")
