"""Writes data/human_check.csv: a hand-check sheet for a person (not the agent) to fill in.

10 apps drawn with random.Random(20261124) from the 70 apps outside audit samples A and B, so the human check is a third,
independent sample. One row per field, with the agent's answer and the link it relied on. Fill `verdict` with
correct / wrong / unclear, put the right value in `correct_value` when wrong, and add your name and date.
The report reads the filled sheet on the next `python -m src.main report`.

  python scripts/make_human_check.py          # refuses to overwrite a sheet that already has verdicts
"""
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "human_check.csv"
FIELDS = ["public_api_status", "authentication_methods", "developer_access", "official_mcp_status", "existing_composio_toolkit"]
COLS = ["id", "app", "field", "agent_says", "evidence_url", "verdict", "correct_value", "note", "checked_by", "checked_on"]


def main() -> None:
    if OUT.exists() and any(r["verdict"].strip() for r in csv.DictReader(OUT.open(encoding="utf-8-sig"))):
        raise SystemExit(f"{OUT} already has verdicts; not overwriting.")
    recs = {r["id"]: r for r in json.loads((ROOT / "data" / "research_verified.json").read_text(encoding="utf-8"))}
    sampled = set()
    for name in ("audit.json", "audit_holdout.json"):
        sampled |= {int(i) for i in json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))["apps"]}
    pool = sorted(i for i in recs if i not in sampled)
    pick = sorted(random.Random(20261124).sample(pool, 10))
    rows = []
    for i in pick:
        r = recs[i]
        for f in FIELDS:
            v = r[f]
            ev = next((e["url"] for e in r["evidence"] if e["field"] == f), "")
            if f == "existing_composio_toolkit" and r["composio_toolkit_identifier"]:
                ev = "https://composio.dev/toolkits/" + r["composio_toolkit_identifier"].split(" ")[0]
            if not ev:
                ev = r["developer_docs_url"] or r["official_website"] or ""
            rows.append({"id": i, "app": r["app_name"], "field": f, "agent_says": "; ".join(v) if isinstance(v, list) else v,
                         "evidence_url": ev, "verdict": "", "correct_value": "", "note": "", "checked_by": "", "checked_on": ""})
    with OUT.open("w", newline="", encoding="utf-8-sig") as fh:  # utf-8-sig so Excel opens it cleanly
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"{OUT.relative_to(ROOT)}: {len(rows)} rows for apps {', '.join(recs[i]['app_name'] for i in pick)}")


if __name__ == "__main__":
    main()
