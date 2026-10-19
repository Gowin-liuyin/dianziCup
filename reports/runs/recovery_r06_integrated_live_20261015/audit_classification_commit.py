"""Compare only the three reviewed exact records against frozen old classifications."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path("D:/dianzi")
RUN = Path(__file__).resolve().parent
path = "reports/security/recovery_fixture_false_positives.json"
old_sha = "1156b2ed6616e3a4297215c2893d2cbe633f5215"
new_sha = "415ee580258ce55b8771c4fc4d070c3a8e78aea0"


def strict_pairs(items):
    value = {}
    for key, member in items:
        assert key not in value, key
        value[key] = member
    return value


def read_commit(sha):
    body = subprocess.check_output(["git", "show", sha + ":" + path], cwd=ROOT)
    return json.loads(body, object_pairs_hook=strict_pairs)


old = read_commit(old_sha)
new = read_commit(new_sha)
identity = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
old_rows = set(map(identity, old["records"]))
new_rows = set(map(identity, new["records"]))
assert len(old["records"]) == 51 and old_rows <= new_rows
added = [record for record in new["records"] if identity(record) not in old_rows]
assert len(added) == 3
audit = json.loads((RUN / "fixture_origin_audit.json").read_text())
for record in added:
    match = next(item for item in audit["matches"] if all(item[key] == record[key] for key in ("path", "pattern_id", "start", "end")))
    assert record["raw_sha256"] == match["raw_sha256"]
    assert record["pattern_sha256"] == match["pattern_sha256"]
    assert hashlib.sha256(record["match_value"].encode()).hexdigest() == match["match_value_sha256"]
    assert record["category"] == "verified_synthetic_fixture"
    assert record["review_ref"] == "reports/reviews/recovery/G-C-R06-fixture-classification-review-1.md"
    origin = record["fixture_origin"]
    origin_blob = subprocess.check_output(["git", "rev-parse", origin["source_commit"] + ":" + origin["source_path"]], cwd=ROOT, text=True).strip()
    assert origin_blob == origin["source_blob"] == match["source_blob"]
assert hashlib.sha256((ROOT / "reports/reviews/recovery/G-C-R06-fixture-classification-review-1.md").read_bytes()).hexdigest() == "d3e175f83e081a1f335cca1314660f35cdd0298a4a2ac6ea20656f5645a10e66"
recorded = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
receipt = {"observed_at": recorded, "old_commit": old_sha, "reviewed_commit": new_sha, "old_51_records_completely_unchanged": True, "new_3_exact_records_match_independent_audit": True, "raw_pattern_offset_value_hash_origin_verified": True, "values_echoed": False, "classifications_or_scanner_modified": False}
(RUN / "classification_commit_audit.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
report = ROOT / "reports/reviews/recovery/G-C-R06-fixture-classification-metadata-recheck.md"
assert not report.exists()
report.write_text(f"""# G-C · R06 fixture 分类元数据定向复核

文档首次创建/本次写作开始/结束/最后更新时间：{recorded}
独立审查者：/root/r06_integrated_live_validation，未实现此分类表。

What this change does: 核对主控 415ee580258ce55b8771c4fc4d070c3a8e78aea0 的三条精确分类是否准确落实 d3e175… 独立意见，并保留原 1156 的 51 条历史记录。首轮独立报告原字节/hash 未改。

结论：Ship（仅 classification 元数据）。strict duplicate-key JSON 读取通过；原 51 条记录逐对象完整相同；新增 3 条 path/raw SHA256/pattern SHA256/LF start:end/value SHA256 均与 fixture_origin_audit.json 相同；source commit 对应 blob、fixture source path 和 review_ref 真实存在且一致。未修改分类、scanner、业务、阈值或状态。完整脱敏 receipt 见 ../../runs/{RUN.name}/classification_commit_audit.json，脚本 audit_classification_commit.py 可复跑。

实际命令：D:/wt/r06-integrated-live-1156/backend/.venv/Scripts/python.exe -B reports/runs/{RUN.name}/audit_classification_commit.py；cwd D:/dianzi；exit0（本脚本所有断言通过才写本结论）。未重跑 34 fixture/全纯测试；主控已保存的原安全 42 passed 是其执行证据，不冒称本审查实际重跑。后续 1a52e17 的原 log -text/-diff 保全不在本次分类逻辑范围；实际 source/browser live 仍固定 1156。

Verdict: Ship（仅上述元数据一致性）。Not checked: 全阶段、秘密全集和后续产品变化。
""", encoding="utf-8")
print(json.dumps({"result": "passed", "old_records": 51, "new_records": 3, "report": str(report), "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest()}))
