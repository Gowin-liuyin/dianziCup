"""Read only the explicitly authorized public receipt subset; never accesses services or labels."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
RECEIPT = Path("D:/dianzi/reports/runs/recovery_r06_document_live_20261015/collection_receipt.json")
ZONE = timezone(timedelta(hours=8))
start = datetime.now(ZONE).isoformat(timespec="seconds")
receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
public_subset = {key: receipt[key] for key in ("first_document", "first_detail", "first_history")}
document = public_subset["first_document"]
original = public_subset["first_detail"]["evidence"][1]
assert original["quote_text"] == "vllm"
assert hashlib.sha256(original["quote_text"].encode()).hexdigest() == original["quote_sha256"]
assert original["end_offset"] - original["start_offset"] == len(original["quote_text"])
observed = datetime.fromisoformat(document["first_observed_at"].replace("Z", "+00:00")).astimezone(ZONE).isoformat(timespec="seconds")
evidence = {key: original[key] for key in (
    "span_id", "revision_id", "block_id", "start_offset", "end_offset", "quote_text",
    "quote_sha256", "locator_kind", "page_number", "json_pointer", "source_uri",
)}
evidence.update(verified_at=observed, field_meaning="原公告结构化 vulnerabilities[0].package.name 字段；只支持核查包名，不能支持版本、条件或完整漏洞结论。")
candidate = {
    "schema_version": 1, "prepared_at": start, "cases": [{
        "case_id": "REAL-R19-GHSA-6cxc-2vcg-w5qc-PACKAGE-01",
        "event_family_id": "GHSA-6cxc-2vcg-w5qc", "family_aliases": ["GHSA-6cxc-2vcg-w5qc"],
        "data_kind": "real", "split": "dev", "source_refs": [{
            "source_kind": "public_document", "uri": document["canonical_uri"],
            "document_id": document["document_id"], "revision_id": document["revision_id"],
            "revision_number": document["revision_number"], "title": document["title"],
            "source_published_at": document["source_published_at"], "source_modified_at": document["source_modified_at"],
            "observed_at": observed,
        }], "source_snapshot_time": observed,
        "input_refs": [{"kind": "evidence", "ref_id": original["span_id"], "sha256": original["quote_sha256"], "path": None}],
        "license": {"status": "unknown", "identifier": None, "uri": None, "redistribution": "unverified"},
        "candidate_origin": "model_assisted",
        "candidate_task": "两位标注人各自打开公告固定来源、核查 vulnerabilities[0].package.name 的字段含义及证据支持范围；记录能确认与尚不可确认的事实。不得仅凭标题或此短证据确认受影响版本、修复版本或资产适用条件。",
        "evidence": [evidence], "limitations": [
            "仅1个真实dev候选、1个4字符精确字段证据、0人工标签；不是完整漏洞/版本/条件金标。",
            "许可标识与转载权限未在收据中提供，均待人工核验；不复制完整未知许可正文。",
            "source时间保留原UTC值；观察/准备时间用真实北京时间秒级表示，原观察精度/hash另见构建收据。",
            "candidate由模型辅助整理；两位真实独立人工及裁决尚未执行，后续完整题型覆盖未完成。",
        ], "label_status": "awaiting_human_label",
    }],
}
target = ROOT / "benchmarks/manifests/r19_public_dev_candidate_v1.json"
target.parent.mkdir(parents=True, exist_ok=True)
with target.open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(candidate, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
subset_hash = hashlib.sha256(json.dumps(public_subset, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
metadata = {
    "command": "python reports/runs/recovery_r19_preparation_20261015/build_public_candidate.py",
    "cwd": str(ROOT), "start": start, "end": datetime.now(ZONE).isoformat(timespec="seconds"), "exit_code": 0,
    "authorized_source": str(RECEIPT), "authorized_keys": list(public_subset), "authorized_subset_sha256": subset_hash,
    "source_document_id": document["document_id"], "source_revision_id": document["revision_id"],
    "source_span_id": original["span_id"], "source_quote_sha256": original["quote_sha256"],
    "source_verified_at_original": original["verified_at"], "source_first_observed_at_original": document["first_observed_at"],
    "candidate_file": str(target.relative_to(ROOT)), "candidate_file_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    "candidate_count": 1, "human_gold_count": 0, "human_labels": 0, "network_calls": 0,
    "scope": "Public original evidence only; no label or expected_* synthesis; no services, DPAPI or holdout access",
}
(RUN / "public_candidate_build.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("PUBLIC_CANDIDATE_BUILT: 1 real candidate; 0 human labels")
