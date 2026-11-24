"""Strict data model. Every published value is an enum or a validated type; unknown is explicit."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ApiStatus(str, Enum):
    AVAILABLE = "available"            # documented public API found on an official host
    RESTRICTED = "restricted"          # API exists but docs/access are behind partner/enterprise gates
    UNAVAILABLE = "unavailable"        # credible evidence there is no public API (e.g. local CLI only)
    UNKNOWN = "unknown"


class Access(str, Enum):
    SELF_SERVE_FREE = "self_serve_free"      # free account / free tier / sandbox gives credentials
    SELF_SERVE_TRIAL = "self_serve_trial"    # credentials during a free trial only
    PAID_PLAN = "paid_plan"                  # API needs a paid or specific plan
    APPROVAL = "approval_required"           # app review / admin approval / developer token approval
    PARTNER = "partner_or_sales"             # partnership / contact sales / enterprise-only
    NOT_APPLICABLE = "not_applicable"        # no API to get access to (local tool)
    UNKNOWN = "unknown"


class Auth(str, Enum):
    OAUTH2 = "OAuth2"
    API_KEY = "API key"
    BEARER_TOKEN = "Bearer/access token"
    BASIC = "Basic"
    JWT = "JWT"
    HMAC = "HMAC/signed request"
    NONE = "None (local tool)"
    OTHER = "Other"


class ApiType(str, Enum):
    REST = "REST"
    GRAPHQL = "GraphQL"
    SOAP = "SOAP"
    WEBHOOKS = "Webhooks"
    GRPC = "gRPC"
    WEBSOCKET = "WebSocket"
    SQL = "SQL/Query API"
    CLI = "CLI"
    SDK = "SDK"


class Tri(str, Enum):
    YES = "yes"
    NO = "no"           # only with credible negative evidence (e.g. registry checked, no match)
    UNKNOWN = "unknown"


class Buildability(str, Enum):
    READY = "ready"                        # public API + self-serve credentials + known auth
    READY_WITH_ACCESS = "needs_access"     # API exists but credentials gated (paid/approval/partner)
    LIMITED = "limited"                    # narrow/unofficial surface, CLI only, or major restrictions
    NOT_BUILDABLE = "not_buildable"        # no viable programmatic surface found
    UNKNOWN = "unknown"


class SourceType(str, Enum):
    OFFICIAL_DOCS = "official_docs"
    OFFICIAL_SITE = "official_site"
    OFFICIAL_GITHUB = "official_github"
    MCP_REGISTRY = "mcp_registry"
    COMPOSIO_REGISTRY = "composio_registry"
    THIRD_PARTY = "third_party"
    SEARCH_SNIPPET = "search_snippet"


class Evidence(BaseModel):
    field: str                      # which record field this supports
    claim: str                      # the specific claim, e.g. "auth: OAuth2"
    url: str
    source_type: SourceType
    excerpt: str = Field(default="", max_length=400)
    retrieved_at: str
    stage: str = "research"         # research | verify | registry | review


class Correction(BaseModel):
    field: str
    before: object
    after: object
    reason: str
    stage: str                      # validation | verify | review | audit
    evidence_url: Optional[str] = None


class AppRecord(BaseModel):
    id: int
    app_name: str
    category: str
    product_description: str = ""
    official_website: Optional[str] = None
    developer_docs_url: Optional[str] = None
    public_api_status: ApiStatus = ApiStatus.UNKNOWN
    authentication_methods: list[Auth] = []
    developer_access: Access = Access.UNKNOWN
    approval_required: Tri = Tri.UNKNOWN
    api_types: list[ApiType] = []
    api_surface_breadth: str = "unknown"   # narrow | moderate | broad | unknown (counted from doc nav)
    official_mcp_status: Tri = Tri.UNKNOWN
    official_mcp_url: Optional[str] = None
    community_mcp_status: Tri = Tri.UNKNOWN
    community_mcp_examples: list[str] = []
    existing_composio_toolkit: Tri = Tri.UNKNOWN
    composio_toolkit_identifier: Optional[str] = None
    toolkit_buildability: Buildability = Buildability.UNKNOWN
    toolkit_buildability_reason: str = ""
    integration_blockers: list[str] = []
    confidence_score: float = 0.0
    confidence_label: str = "low"
    last_verified_at: Optional[str] = None
    evidence: list[Evidence] = []
    corrections: list[Correction] = []
    verification_status: str = "unverified"   # unverified | auto_validated | auto_verified | disputed | audited
    errors: list[str] = []
    pages_fetched: int = 0

    @field_validator("official_website", "developer_docs_url", "official_mcp_url")
    @classmethod
    def _url(cls, v):
        if v in (None, ""):
            return None
        HttpUrl(v)  # raises on malformed URL
        return v

    @field_validator("confidence_score")
    @classmethod
    def _conf(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence_score must be in [0,1]")
        return round(v, 2)
