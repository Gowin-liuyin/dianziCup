"""Retain the original failure and freeze a migration-head compatibility test correction."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
OLD_RUN = ROOT / "reports/runs/recovery_r07_enrichment_jobs_20261016"
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
cr = ROOT / "docs/decisions/CR-R07_metadata_head_test_compatibility.md"
cr.write_text(f"""# CR-R07 · 前向0019后元数据测试兼容

首次创建时间：{started}；主控/root；状态awaiting_review。
独立审查固定1b在真实forward0019运行原20元数据用例，19pass/1fail：唯一失败是原测试硬编码head0017，实际0019_aggregate_observations。原20自检确在pre0019运行，不能据原记录宣称最终SHA20通过。审查原红由reviewer保存，不改它。

仅修改test_r07_enrichment_job_metadata_pg.py的installed revision检查：要求真实PG installed等于当前冻结Alembic head，并要求0017在真实祖先链。原19约束/并发用例、输入、业务表、迁移、指标/金标/阈值均不变。这样保留必须已经迁移0017的验收，并允许已批准的0018/19前向链。不是任意revision或不存在数据库通过。

真实同原20测试于current0019重新运行20/20，原报告/manifest1b原bytes保留，新证据另run。生产业务代码与1f0522完全相同，只有测试兼容变更；无需数据库迁移，回退仅回退本测试会恢复已知false failure。需原独立reviewer检查新diff并亲复跑20，root不自签。
""", encoding="utf-8", newline="\n")
files = ["backend/tests/integration/test_r07_enrichment_job_metadata_pg.py", cr.relative_to(ROOT).as_posix()]
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip()
subprocess.run(["git", "add", "--", *files], cwd=ROOT, check=True)
subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-q", "-m", "R07 verify enrichment metadata on the approved forward migration chain"], cwd=ROOT, check=True)
code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
for suffix in ("log", "json", "xml"):
    (RUN / ("metadata_post0019_recheck." + suffix)).write_bytes((OLD_RUN / ("metadata_post0019_recheck." + suffix)).read_bytes())
(RUN / ".gitattributes").write_text("* -text whitespace=cr-at-eol\n", encoding="utf-8", newline="\n")
entries = [{"path": path.relative_to(ROOT).as_posix(), "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(RUN.iterdir()) if path.is_file() and path.name != "artifact_manifest.json"]
manifest = {"code_sha": code_sha, "parent_material_sha": "1b894daaa4523f37600c8ff8f9990c5df534a3fa", "business_code_sha": "1f0522e3f3fb9547ea55136efa64fc589466c992", "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "entries": entries}
(RUN / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
subprocess.run(["git", "add", "--", *[item["path"] for item in entries], (RUN / "artifact_manifest.json").relative_to(ROOT).as_posix()], cwd=ROOT, check=True)
subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-q", "-m", "R07 retain independent metadata correction evidence"], cwd=ROOT, check=True)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert all(subprocess.check_output(["git", "show", head + ":" + item["path"]], cwd=ROOT) == (ROOT / item["path"]).read_bytes() for item in entries)
print(json.dumps({"code_sha": code_sha, "material_sha": head, "artifact_manifest_sha256": hashlib.sha256((RUN / "artifact_manifest.json").read_bytes()).hexdigest(), "business_code_unchanged": True, "root_test_recheck": "20 pass", "status": "awaiting_review"}))
