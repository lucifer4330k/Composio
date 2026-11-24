"""First real Composio tool call for this project (Composio Platform, Python SDK sessions).

Steps: create a session for the project's single developer identity -> check the GitHub connection ->
if not connected, print a Connect Link and wait -> discover a read-only GitHub tool at runtime -> execute it.

Needs COMPOSIO_API_KEY in .env (never printed). Optional COMPOSIO_USER_ID (default below).
Usage: python scripts/composio_first_call.py [--query "get the authenticated github user profile"]
"""
import argparse
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()
if not os.getenv("COMPOSIO_API_KEY"):
    sys.exit("COMPOSIO_API_KEY is not set (add it to .env).")

from composio import Composio  # noqa: E402  (import after env check so the error is clear)

TOOLKIT = "github"
# This project has no user model; one stable developer identity owns the connection.
USER_ID = os.getenv("COMPOSIO_USER_ID", "composio-ai-product-ops-dev")


def slugs_in(obj) -> list[str]:
    """Collect tool slugs from a search response without assuming its exact nesting."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("tool_slug", "slug") and isinstance(v, str) and v.upper().startswith(TOOLKIT.upper() + "_"):
                found.append(v)
            found += slugs_in(v)
    elif isinstance(obj, list):
        for v in obj:
            found += slugs_in(v)
    return list(dict.fromkeys(found))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="get the authenticated github user profile")
    ap.add_argument("--tool", help="exact tool slug to run (skip discovery)")
    args = ap.parse_args()

    composio = Composio()
    session = composio.create(user_id=USER_ID)
    print(f"session_id={session.session_id} user_id={USER_ID}")

    state = session.toolkits(toolkits=[TOOLKIT])  # dataclass ToolkitConnectionsDetails
    connected = any(t.slug == TOOLKIT and t.connection and t.connection.is_active for t in state.items)
    if not connected:
        req = session.authorize(TOOLKIT)
        print(f"GitHub not connected. Open this Connect Link and approve:\n  {req.redirect_url}")
        req.wait_for_connection(timeout=300)
        print("GitHub connected.")

    tool = args.tool
    if not tool:
        found = slugs_in(session.search(query=args.query).model_dump(mode="json"))
        print("discovered tools:", found[:8])
        if not found:
            sys.exit("no GitHub tool found for that query; pass --tool <slug>")
        tool = found[0]

    res = session.execute(tool, arguments={})
    print(f"tool={tool} result_type={res.result_type} log_id={res.log_id}")
    if res.result_type != "completed":
        sys.exit(f"error: {res.error}")
    data = res.data if isinstance(res.data, dict) else {"data": res.data}
    inner = data.get("data", data) if isinstance(data, dict) else data
    safe = {k: inner.get(k) for k in ("login", "name", "public_repos", "html_url", "created_at")} if isinstance(inner, dict) else str(inner)[:300]
    print("result:", json.dumps(safe, default=str))


if __name__ == "__main__":
    main()
