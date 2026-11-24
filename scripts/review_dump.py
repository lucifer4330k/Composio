"""Print a compact, reviewable summary of records (after automated verification) so a reviewer can
adjudicate fields against the stored evidence. Usage: python scripts/review_dump.py [ids comma-separated]"""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
raw = json.loads((root / "data" / "research_raw.json").read_text(encoding="utf-8"))["apps"]
vlog = json.loads((root / "data" / "verification_log.json").read_text(encoding="utf-8")).get("automated", {})
ids = sys.argv[1].split(",") if len(sys.argv) > 1 else sorted(raw, key=int)
for i in ids:
    e = raw[i]
    r = e.get("record_after_verify", e["record"])
    print(f"#{i} {r['app_name']} | api={r['public_api_status']} access={r['developer_access']} auth={r['authentication_methods']} "
          f"mcp={r['official_mcp_status']} composio={r['existing_composio_toolkit']}({r['composio_toolkit_identifier']}) build={r['toolkit_buildability']} "
          f"conf={r['confidence_score']} pages={r['pages_fetched']} verify={vlog.get(i, {}).get('status')}")
    print(f"   docs={r['developer_docs_url']}")
    for f in ("developer_access", "authentication_methods", "official_mcp_status"):
        for ev in [x for x in r["evidence"] if x["field"] == f][:3]:
            print(f"   [{f[:6]}] {ev['claim'][-28:]:<28} {ev['url'][:90]}\n        {ev['excerpt'][60:300]}")
