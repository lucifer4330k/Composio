"""Validation agent: deterministic checks on single records and on the whole dataset."""
from __future__ import annotations

from urllib.parse import urlparse

from ..models.schema import Access, ApiStatus, AppRecord, Buildability, Tri
from .research import is_official


def validate_record(rec: AppRecord, app: dict) -> list[str]:
    issues = []
    if rec.id != app["id"] or rec.app_name != app["app_name"] or rec.category != app["category"]:
        issues.append("identity: id/name/category differ from trusted input")
    for f in ("developer_docs_url", "official_website"):
        u = getattr(rec, f)
        if u and app["official_hosts"] and not is_official(u, app["official_hosts"]):
            issues.append(f"identity: {f} {urlparse(u).netloc} is not an official host for {app['app_name']}")
    claimed = {e.field for e in rec.evidence}
    if rec.authentication_methods and "authentication_methods" not in claimed:
        issues.append("evidence: auth methods without evidence")
    if rec.developer_access != Access.UNKNOWN and "developer_access" not in claimed and not any(c.field == "developer_access" for c in rec.corrections):
        issues.append("evidence: developer_access without evidence")
    if rec.public_api_status == ApiStatus.UNAVAILABLE and rec.toolkit_buildability == Buildability.READY:
        issues.append("contradiction: no public API but buildability=ready")
    if rec.developer_access in (Access.PARTNER, Access.APPROVAL) and rec.toolkit_buildability == Buildability.READY:
        issues.append("contradiction: gated access but buildability=ready")
    if rec.official_mcp_status == Tri.YES and not rec.official_mcp_url:
        issues.append("evidence: official MCP claimed without URL")
    if rec.existing_composio_toolkit == Tri.YES and not rec.composio_toolkit_identifier:
        issues.append("evidence: composio toolkit claimed without identifier")
    if rec.public_api_status == ApiStatus.AVAILABLE and not rec.developer_docs_url:
        issues.append("evidence: API available but no docs URL")
    for e in rec.evidence:
        if e.source_type.value.startswith("official") and app["official_hosts"] and not is_official(e.url, app["official_hosts"]):
            issues.append(f"identity: evidence marked official from foreign host {urlparse(e.url).netloc}")
            break
    return issues


def validate_dataset(records: list[AppRecord], apps: list[dict]) -> list[str]:
    issues = []
    ids = [r.id for r in records]
    if len(set(ids)) != len(ids):
        issues.append("duplicate ids")
    names = [r.app_name.lower() for r in records]
    if len(set(names)) != len(names):
        issues.append("duplicate app names")
    expected = {a["id"] for a in apps}
    if set(ids) - expected:
        issues.append(f"invented ids: {sorted(set(ids) - expected)}")
    if expected - set(ids):
        issues.append(f"missing ids: {sorted(expected - set(ids))}")
    doc_owner: dict[str, int] = {}
    for r in records:
        if r.developer_docs_url:
            if r.developer_docs_url in doc_owner and doc_owner[r.developer_docs_url] != r.id:
                other = next(x for x in records if x.id == doc_owner[r.developer_docs_url])
                # shared docs are legitimate only for sibling products of one vendor (e.g. Salesforce / Commerce Cloud)
                issues.append(f"shared docs url between #{other.id} {other.app_name} and #{r.id} {r.app_name}: {r.developer_docs_url}")
            doc_owner[r.developer_docs_url] = r.id
    return issues
