"""Consolidation: pass-1 record -> + automated verification -> + review adjudications -> final dataset.

Also scores each pipeline stage against the browser audit (data/audit.json) so the report can show how
accuracy moved from pass 1 to the final dataset, with explicit denominators."""
from __future__ import annotations

import json
import time
from pathlib import Path

from ..agents.extract import confidence, derive_buildability
from ..agents.validate import validate_dataset, validate_record
from ..models.schema import AppRecord, Correction, Evidence, SourceType

OPEN = {"self_serve_free", "self_serve_trial"}
GATED = {"paid_plan", "approval_required", "partner_or_sales"}
LIST_FIELDS = {"authentication_methods", "api_types", "integration_blockers", "community_mcp_examples"}


def access_bucket(v: str) -> str:
    return "open" if v in OPEN else "gated" if v in GATED else v


def apply_review(rec: AppRecord, review: dict) -> AppRecord:
    for field, fix in review.get("fields", {}).items():
        before = getattr(rec, field)
        before_v = [getattr(x, "value", x) for x in before] if isinstance(before, list) else getattr(before, "value", before)
        after = fix["value"]
        changed = before_v != after
        if changed:
            rec.corrections.append(Correction(field=field, before=before_v, after=after, reason=fix["reason"], stage="review", evidence_url=fix.get("url")))
            setattr(rec, field, after)
        # a confirmed value still gets its source when the record had no evidence for that field
        if fix.get("url") and (changed or not any(e.field == field for e in rec.evidence)):
            rec.evidence.append(Evidence(field=field, claim=f"{field}: {after} (review)", url=fix["url"], source_type=SourceType(fix.get("source_type", "official_docs")),
                                         excerpt=fix.get("excerpt", fix["reason"])[:400], retrieved_at=review.get("checked_at", ""), stage="review"))
    rec.verification_status = review.get("status", "reviewed")
    rec.last_verified_at = review.get("checked_at")
    return AppRecord.model_validate(rec.model_dump(warnings=False))  # re-validate: reviewed values must still be legal enum values


def _norm(v):
    return sorted(v) if isinstance(v, list) else v


def score(stage_records: dict[str, dict], audit: dict) -> dict:
    """Field-level accuracy of each stage on audited apps. Unknown is reported separately from wrong."""
    out = {}
    for stage, recs in stage_records.items():
        tallies = {}
        for app_id, truth in audit["apps"].items():
            r = recs.get(app_id)
            if not r:
                continue
            for f, t in truth["fields"].items():
                tl = tallies.setdefault(f, {"correct": 0, "wrong": 0, "unknown": 0, "n": 0, "misses": []})
                tl["n"] += 1
                if f == "authentication_methods":
                    got = set(r[f])
                    prim, extra = set(t["primary"]), set(t.get("acceptable_extra", []))
                    res = "unknown" if not got else "correct" if prim <= got <= prim | extra else "wrong"
                elif f == "developer_access":
                    res = "correct" if access_bucket(r[f]) == access_bucket(t["value"]) else "unknown" if r[f] == "unknown" else "wrong"
                else:
                    res = "unknown" if r[f] == "unknown" and t["value"] != "unknown" else "correct" if r[f] == t["value"] else "wrong"
                tl[res] += 1
                if res != "correct":
                    tl["misses"].append({"id": app_id, "app": truth["app"], "got": _norm(r[f]), "expected": t.get("value", t.get("primary")), "result": res})
        tot = {k: sum(v[k] for v in tallies.values()) for k in ("correct", "wrong", "unknown", "n")}
        out[stage] = {"fields": tallies, "total": tot, "accuracy": round(tot["correct"] / tot["n"], 3) if tot["n"] else None}
    return out


def consolidate(root: Path) -> None:
    data = root / "data"
    apps = {a["id"]: a for a in json.loads((data / "apps_input.json").read_text(encoding="utf-8"))["apps"]}
    raw = json.loads((data / "research_raw.json").read_text(encoding="utf-8"))["apps"]
    reviews = json.loads((data / "review_adjudications.json").read_text(encoding="utf-8")) if (data / "review_adjudications.json").exists() else {"apps": {}}
    vlog_path = data / "verification_log.json"
    vlog = json.loads(vlog_path.read_text(encoding="utf-8")) if vlog_path.exists() else {"automated": {}}

    final, stage_pass1, stage_verify, stage_final = [], {}, {}, {}
    for i, app in sorted(apps.items()):
        entry = raw.get(str(i))
        if not entry:
            rec = AppRecord(id=i, app_name=app["app_name"], category=app["category"], errors=["not researched"])
            final.append(rec)
            continue
        stage_pass1[str(i)] = entry["record"]
        rec = AppRecord(**entry.get("record_after_verify", entry["record"]))
        stage_verify[str(i)] = rec.model_dump(mode="json")
        if str(i) in reviews["apps"]:
            rec = apply_review(rec, reviews["apps"][str(i)])
        derive_buildability(rec)
        issues = validate_record(rec, app)
        rec.errors = [e for e in rec.errors if not e.startswith("validation:")] + [f"validation: {x}" for x in issues]
        confidence(rec)
        final.append(rec)
        stage_final[str(i)] = rec.model_dump(mode="json")

    ds_issues = validate_dataset(final, list(apps.values()))
    out = [r.model_dump(mode="json") for r in final]
    (data / "research_verified.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    audit = json.loads((data / "audit.json").read_text(encoding="utf-8")) if (data / "audit.json").exists() else None
    holdout = json.loads((data / "audit_holdout.json").read_text(encoding="utf-8")) if (data / "audit_holdout.json").exists() else None
    stages = {"pass1": stage_pass1, "after_auto_verify": stage_verify, "final": stage_final}
    v1 = data / "research_raw_v1.json"  # snapshot of the first full run, before extractor rules were tightened on sample A
    if v1.exists():
        stages = {"rules_v1": {k: e["record"] for k, e in json.loads(v1.read_text(encoding="utf-8"))["apps"].items()}, **stages}
    vlog["accuracy"] = {
        "audit_sample": score(stages, audit) if audit else None,
        "holdout_sample": score(stages, holdout) if holdout else None,
    }
    vlog["dataset_issues"] = ds_issues
    vlog["record_issues"] = {r.id: [e for e in r.errors if e.startswith("validation:")] for r in final if any(e.startswith("validation:") for e in r.errors)}
    vlog["corrections"] = [dict(c.model_dump(mode="json"), id=r.id, app=r.app_name) for r in final for c in r.corrections]
    vlog["consolidated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (data / "verification_log.json").write_text(json.dumps(vlog, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[consolidate] {len(out)} records -> research_verified.json | corrections={len(vlog['corrections'])} dataset_issues={ds_issues}")
