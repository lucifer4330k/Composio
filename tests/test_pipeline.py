"""Unit/integration tests. All fixtures here are MOCK data, clearly labelled, and never written into data/."""
import asyncio
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from src.agents.extract import decide_access, derive_buildability, extract, select_auth
from src.agents.research import is_official
from src.agents.validate import validate_dataset, validate_record
from src.analysis.consolidate import apply_review, score
from src.analysis.insights import run_insights
from src.main import pending, save_json
from src.models.schema import Access, ApiStatus, AppRecord, Auth, Buildability, Tri
from src.tools.http import Fetcher, Page
from src.tools.registries import _catalog_lookup, _match, mcp_registry, slug_candidates

MOCK_APP = {"id": 999, "app_name": "MockCRM", "category": "CRM and Sales", "hint": "mockcrm.test",
            "official_hosts": ["mockcrm.test", "github.com/mockcrm"], "seed_urls": []}


def mock_page(url, text, title="MockCRM API", meta=""):
    return Page(url=url, final_url=url, status=200, title=title, text=text, links=[], meta_description=meta, fetched_at="2026-01-01T00:00:00Z")


# ---------- schema ----------
def test_schema_rejects_bad_enum_url_and_confidence():
    with pytest.raises(ValidationError):
        AppRecord(id=1, app_name="x", category="c", public_api_status="maybe")
    with pytest.raises(ValidationError):
        AppRecord(id=1, app_name="x", category="c", developer_docs_url="not a url")
    with pytest.raises(ValidationError):
        AppRecord(id=1, app_name="x", category="c", confidence_score=1.5)


# ---------- identity ----------
def test_identity_github_org_must_match_whole_segment():
    hosts = ["github.com/meta", "facebook.com"]
    assert is_official("https://github.com/meta/llama", hosts)
    assert not is_official("https://github.com/metabase/metabase", hosts)
    assert is_official("https://developers.facebook.com/docs", hosts)
    assert not is_official("https://facebook.com.evil.test/docs", hosts)


# ---------- extraction ----------
def test_extract_evidence_anchored_and_marketing_noise_ignored():
    docs = mock_page("https://docs.mockcrm.test/api/auth",
                     "Authentication. The MockCRM REST API uses OAuth 2.0 authorization code flow. You can also create an API key in settings. "
                     "Create a free developer account to get your API key. " + "GET /v1/contacts returns contacts. " * 30)
    home = mock_page("https://mockcrm.test/", "Grow sales faster. Start for free today. Loved by teams. " * 40, meta="MockCRM is a CRM.")
    rec = extract(MOCK_APP, {"official_pages": [home, docs], "third_party": [], "search_results": [], "log": []})
    assert Auth.OAUTH2 in rec.authentication_methods and Auth.API_KEY in rec.authentication_methods
    assert all(e.url.startswith("https://") and e.excerpt for e in rec.evidence)
    access_ev = [e for e in rec.evidence if e.field == "developer_access"]
    assert access_ev and all("docs.mockcrm.test" in e.url for e in access_ev), "homepage 'Start for free' must not count as API access evidence"
    assert rec.public_api_status == ApiStatus.AVAILABLE and rec.product_description == "MockCRM is a CRM."


def test_no_evidence_means_unknown_not_guess():
    rec = extract(MOCK_APP, {"official_pages": [mock_page("https://mockcrm.test/", "We are a CRM company with a login page. " * 80)],
                             "third_party": [], "search_results": [], "log": []})
    assert rec.authentication_methods == [] and rec.developer_access == Access.UNKNOWN and rec.public_api_status == ApiStatus.UNKNOWN
    derive_buildability(rec)
    assert rec.toolkit_buildability == Buildability.UNKNOWN


def test_access_decision_precedence():
    assert decide_access({"approval": 2, "free": 3})[0] == Access.APPROVAL
    assert decide_access({"free": 1, "partner": 5})[0] == Access.SELF_SERVE_FREE
    assert decide_access({"partner": 2})[0] == Access.PARTNER
    assert decide_access({})[0] == Access.UNKNOWN


# ---------- validation ----------
def test_validation_flags_contradiction_and_foreign_docs():
    rec = AppRecord(id=999, app_name="MockCRM", category="CRM and Sales", developer_access=Access.PARTNER,
                    toolkit_buildability=Buildability.READY, developer_docs_url="https://other-vendor.test/docs")
    issues = validate_record(rec, MOCK_APP)
    assert any("contradiction" in i for i in issues) and any("identity" in i for i in issues)


def test_dataset_duplicates_and_invented_ids():
    apps = [{"id": 1, "app_name": "A"}, {"id": 2, "app_name": "B"}]
    recs = [AppRecord(id=1, app_name="A", category="c"), AppRecord(id=1, app_name="A", category="c"), AppRecord(id=7, app_name="Z", category="c")]
    issues = validate_dataset(recs, apps)
    assert "duplicate ids" in issues and any("invented ids" in i for i in issues) and any("missing ids" in i for i in issues)


# ---------- fetcher: cache, retry, failure ----------
def test_fetcher_retries_then_caches(tmp_path):
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<title>Docs</title>" + "<p>OAuth 2.0 docs</p>" * 300)

    async def go():
        f = Fetcher(tmp_path, retries=3, transport=httpx.MockTransport(handler))
        p1 = await f.get("https://mock.test/a")
        p2 = await f.get("https://mock.test/a")
        await f.close()
        return p1, p2, f.stats

    p1, p2, stats = asyncio.run(go())
    assert p1.ok and p2.ok and calls["n"] == 3 and stats["retries"] == 2 and stats["cache_hits"] == 1


def test_fetcher_failure_is_returned_not_raised(tmp_path):
    def handler(req):
        raise httpx.ConnectError("boom")

    async def go():
        f = Fetcher(tmp_path, retries=1, transport=httpx.MockTransport(handler))
        f._render = lambda url: asyncio.sleep(0, result=Page(url, url, 0, error="render disabled in test"))
        p = await f.get("https://down.test/")
        await f.close()
        return p

    p = asyncio.run(go())
    assert not p.ok and "ConnectError" in p.error and not list(tmp_path.glob("*.json")), "failures must not be cached"


# ---------- checkpointing ----------
def test_checkpoint_resume_skips_done(tmp_path):
    state = {"apps": {"1": {}, "2": {}}}
    save_json(tmp_path / "raw.json", state)
    loaded = json.loads((tmp_path / "raw.json").read_text())
    apps = [{"id": i} for i in (1, 2, 3, 4)]
    assert [a["id"] for a in pending(apps, loaded)] == [3, 4]
    assert len(pending(apps, loaded, force=True)) == 4


# ---------- registries ----------
def test_composio_matching_avoids_false_matches():
    assert "metaads" in slug_candidates("Meta Ads")
    assert _match("LinkedIn Ads", "LinkedIn") == "parent_platform"
    assert _match("Stripe", "Stripe") == "exact"
    assert _match("Plain", "Plaid") == "alias"


def test_mcp_registry_official_vs_community():
    class FakeFetcher:
        async def get(self, url, raw=False):
            body = {"servers": [
                {"server": {"name": "test.mockcrm/mcp", "description": "official (namespace = reversed mockcrm.test)"}},
                {"server": {"name": "io.github.mockcrm/mockcrm-mcp", "description": "official via org"}},
                {"server": {"name": "io.github.someone/mockcrm-mcp", "repository": {"url": "https://github.com/someone/mockcrm-mcp"}}},
                {"server": {"name": "io.github.someone/unrelated", "description": "no name match"}},
            ]}
            return Page(url, url, 200, text=json.dumps(body))

    res = asyncio.run(mcp_registry(FakeFetcher(), "MockCRM", MOCK_APP["official_hosts"]))
    assert {o["name"] for o in res["official"]} == {"test.mockcrm/mcp", "io.github.mockcrm/mockcrm-mcp"}
    assert [c["name"] for c in res["community"]] == ["io.github.someone/mockcrm-mcp"]


# ---------- review + scoring ----------
def test_review_preserves_before_after_and_scoring_counts_unknown_separately():
    rec = AppRecord(id=1, app_name="A", category="c", developer_access=Access.UNKNOWN)
    rec = apply_review(rec, {"fields": {"developer_access": {"value": "paid_plan", "reason": "pricing page", "url": "https://a.test/pricing"}},
                             "status": "reviewed", "checked_at": "2026-01-01"})
    assert rec.developer_access == Access.PAID_PLAN and rec.corrections[0].before == "unknown"
    audit = {"apps": {"1": {"app": "A", "fields": {"developer_access": {"value": "paid_plan"}, "official_mcp_status": {"value": "yes"}}}}}
    s = score({"x": {"1": {"developer_access": "unknown", "official_mcp_status": "unknown"}}}, audit)["x"]
    assert s["total"] == {"correct": 0, "wrong": 0, "unknown": 2, "n": 2}


# ---------- insights ----------
def test_insights_match_direct_counts(tmp_path):
    (tmp_path / "data").mkdir()
    recs = []
    for i in range(1, 7):
        r = AppRecord(id=i, app_name=f"Mock{i}", category="Cat A" if i <= 3 else "Cat B",
                      authentication_methods=[Auth.OAUTH2] if i % 2 else [Auth.API_KEY],
                      developer_access=Access.SELF_SERVE_FREE if i <= 4 else Access.PARTNER,
                      public_api_status=ApiStatus.AVAILABLE, existing_composio_toolkit=Tri.YES if i == 1 else Tri.NO, confidence_score=0.8)
        derive_buildability(r)
        recs.append(r.model_dump(mode="json"))
    (tmp_path / "data" / "research_verified.json").write_text(json.dumps(recs))
    ins = run_insights(tmp_path)
    assert ins["n"] == 6 and ins["auth_counts"]["OAuth2"] == 3 and ins["access_buckets"]["open"]["n"] == 4
    assert ins["buildability"]["ready"]["n"] == 4 and ins["by_category"]["Cat B"]["gated"] == 2
    assert all(o["app"] != "Mock1" for o in ins["opportunities"]["new_easy_wins"]), "apps already in Composio are not 'new' opportunities"


def test_composio_catalog_lookup():
    """MOCK catalog (not real Composio data): unexpected slug found by display name, Provider MCP labelled,
    zero-tool toolkits ignored, absence reported with the catalog size."""
    cat = [
        {"slug": "otter_ai_mcp", "name": "Otter.ai MCP", "app": "Otter.ai", "toolkit_type": "mcp", "tools_count": 3},
        {"slug": "mockcrm", "name": "MockCRM", "app": "MockCRM", "toolkit_type": "api", "tools_count": 40},
        {"slug": "mockcrm_mcp", "name": "MockCRM MCP", "app": "MockCRM", "toolkit_type": "mcp", "tools_count": 5},
        {"slug": "amazon", "name": "Amazon", "app": "Amazon", "toolkit_type": "api", "tools_count": 0},
    ]
    r = _catalog_lookup("MockCRM", cat)
    assert (r["status"], r["slug"], r["match"], r["siblings"]) == ("yes", "mockcrm", "exact", ["mockcrm_mcp"])
    assert _catalog_lookup("Otter AI", cat)["match"] == "provider_mcp"
    assert _catalog_lookup("Amazon Selling Partner", cat)["status"] == "no"
    assert _catalog_lookup("Nonexistent App", cat)["catalog_size"] == 3


def test_auth_ignores_json_blobs_and_oauth_client_basic():
    # MOCK pages: Mintlify-style feature-flag JSON and an OAuth token-exchange snippet must not add JWT/Basic
    text = ('Use OAuth 2.0 to connect. {"name":"jwt-refresh","enabled":true,"variant":{"name":"off"}} '
            "Exchange the code at https://api.example.com/v1/oauth/token. The request is authorized using HTTP Basic "
            "with your client_id and client secret. Send Authorization: Bearer <token> on every call.")
    page = Page(url="https://docs.example.com/auth", final_url="https://docs.example.com/auth", status=200, title="Authentication", text=text)
    got, _ = select_auth([page], "test")
    assert Auth.OAUTH2 in got and Auth.BEARER_TOKEN in got
    assert Auth.JWT not in got and Auth.BASIC not in got


def test_blockers_follow_final_access():
    # MOCK record: review turned access self-serve, so a stale gate blocker must go; a gated record must name its blocker
    rec = AppRecord(id=1, app_name="MockApp", category="Mock", public_api_status=ApiStatus.AVAILABLE, developer_access=Access.SELF_SERVE_FREE,
                    authentication_methods=[Auth.OAUTH2], integration_blockers=["Partner program / contact-sales gate"])
    derive_buildability(rec)
    assert rec.toolkit_buildability == Buildability.READY and rec.integration_blockers == []
    rec2 = AppRecord(id=2, app_name="MockGated", category="Mock", public_api_status=ApiStatus.AVAILABLE, developer_access=Access.PAID_PLAN,
                     authentication_methods=[Auth.API_KEY])
    derive_buildability(rec2)
    assert rec2.integration_blockers == ["API access tied to a paid plan"]


def test_human_check_reads_only_filled_rows(tmp_path):
    from src.reporting.build_report import human_check
    p = tmp_path / "human_check.csv"  # MOCK sheet
    p.write_text("id,app,field,agent_says,evidence_url,verdict,correct_value,note,checked_by,checked_on\n"
                 "1,MockApp,developer_access,self_serve_free,https://x,Correct,,,A Person,2026-11-24\n"
                 "1,MockApp,public_api_status,available,https://x,,,,,\n", encoding="utf-8-sig")
    rows = human_check(p)
    assert len(rows) == 1 and rows[0]["verdict"] == "correct"
    p.write_text("id,app,field,agent_says,evidence_url,verdict,correct_value,note,checked_by,checked_on\n1,M,f,v,u,maybe,,,,\n", encoding="utf-8-sig")
    with pytest.raises(SystemExit):
        human_check(p)
    assert human_check(tmp_path / "missing.csv") == []
