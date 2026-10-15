"""Record independently recomputed counts without rewriting historical scan data."""

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone

from inspect_candidates import ROOT, RUN


def raw_sha256(relative):
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


local_timezone=timezone(timedelta(hours=8))
started_at=datetime.now(local_timezone).isoformat()
report_path=ROOT / "reports/reviews/recovery/G-B-secret-fixture-classification.md"
report_text=report_path.read_text(encoding="utf-8")
revision_line="准确性修订时刻：`" + datetime.now(local_timezone).isoformat(timespec="seconds") + "`。仅校正去重文件数和已记录时间格式，原扫描/测试日志及提案记录未改。"
if "准确性修订时刻：" in report_text:
    report_text="\n".join(revision_line if line.startswith("准确性修订时刻：") else line for line in report_text.split("\n"))
else:
    report_text=report_text.replace("# G-B 安全命中诊断与精确 fixture 分类\n", "# G-B 安全命中诊断与精确 fixture 分类\n\n" + revision_line + "\n",1)
report_path.write_text(report_text,encoding="utf-8")
proposal_path="reports/security/gb_fixture_classification_proposal.json"
history_path="reports/runs/recovery_gb_secret_fixture_classification_20261015/unclassified_metadata.json"
seal_path="reports/runs/recovery_gb_secret_fixture_classification_20261015/analyzed_file_snapshots.json"
proposal=json.loads((ROOT / proposal_path).read_text(encoding="utf-8"))
history=json.loads((ROOT / history_path).read_text(encoding="utf-8"))
old_seal=json.loads((ROOT / seal_path).read_text(encoding="utf-8"))
records=proposal["records"]
occurrences=history["occurrences"]
venv=[item for item in occurrences if "/venv/" in item["path"]]
non_venv=[item for item in occurrences if "/venv/" not in item["path"]]
proposal_counts={"records":len(records),"unique_paths":len({item["path"] for item in records}),"unique_spans":len({(item["path"],item["start"],item["end"]) for item in records})}
assert proposal_counts == {"records":15,"unique_paths":11,"unique_spans":13}
historical_counts={"records":len(occurrences),"unique_paths":len({item["path"] for item in occurrences})}
assert historical_counts == {"records":70,"unique_paths":58}
venv_counts={"records":len(venv),"unique_paths":len({item["path"] for item in venv})}
non_venv_counts={"records":len(non_venv),"unique_paths":len({item["path"] for item in non_venv})}
assert venv_counts == {"records":55,"unique_paths":47}
assert non_venv_counts == {"records":15,"unique_paths":11}
assert {item["path"] for item in records} == {item["path"] for item in non_venv}
receipt={"started_at":started_at,"ended_at":datetime.now(local_timezone).isoformat(),"head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"proposal_path":proposal_path,"proposal_sha256":raw_sha256(proposal_path),"historical_metadata_path":history_path,"historical_metadata_sha256":raw_sha256(history_path),"old_seal_path":seal_path,"old_seal_sha256":raw_sha256(seal_path),"formulas":{"records":"len(records)","unique_paths":"len({r['path'] for r in records})","unique_spans":"len({(r['path'], r['start'], r['end']) for r in records})","venv_scope":"[r for r in historical_occurrences if '/venv/' in r['path']]"},"proposal_counts":proposal_counts,"historical_counts":historical_counts,"venv_counts":venv_counts,"non_venv_counts":non_venv_counts,"withdrawn_summary":{"project_unique_paths":10,"venv_unique_paths":48},"reason":"Manual project path count was used without deduplicating records; its complement against 58 total paths inherited the same off-by-one error.","historical_metadata_rewritten":False,"proposal_records_changed":False,"classification_implementation_changed":False,"shared_manifest_changed_by_this_task":False,"tests_rerun":"not_run; arithmetic and file identity correction only"}
(RUN / "counts_correction_receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
report_paths=["reports/reviews/recovery/G-B-secret-fixture-classification.md","reports/tasks/G-B-secret-fixture-classification.md"]
updated_reports=[]
for relative in report_paths:
    old=next(item for item in old_seal["file_snapshots"] if item["path"] == relative)
    updated_reports.append({"path":relative,"previous_sealed_sha256":old["sha256"],"current_sha256":raw_sha256(relative),"observed_at":datetime.now(local_timezone).isoformat()})
seal={"recorded_at":datetime.now(local_timezone).isoformat(),"head":receipt["head"],"supersedes_report_entries_only_from":seal_path,"previous_seal_preserved":True,"historical_scan_metadata_sha256":receipt["historical_metadata_sha256"],"proposal_sha256":receipt["proposal_sha256"],"correction_receipt_sha256":hashlib.sha256((RUN / "counts_correction_receipt.json").read_bytes()).hexdigest(),"revised_report_snapshots":updated_reports,"scope":"Count and recorded-time format correction only. No new scan, secret comparison, business test, classification edit, or stage acceptance."}
(RUN / "counts_correction_seal.json").write_text(json.dumps(seal,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
assert raw_sha256(proposal_path) == receipt["proposal_sha256"]
assert raw_sha256(history_path) == receipt["historical_metadata_sha256"]
assert raw_sha256(seal_path) == receipt["old_seal_sha256"]
print(json.dumps({"head":receipt["head"],"proposal_counts":proposal_counts,"historical_counts":historical_counts,"venv_counts":venv_counts,"non_venv_counts":non_venv_counts,"proposal_sha256":receipt["proposal_sha256"],"historical_metadata_preserved":True,"old_seal_preserved":True,"new_report_seal":"counts_correction_seal.json"}))
