"""Freeze one proposed table for a unique implementer; production migration remains pending."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from ai_intel.assets.sbom_persistence_models import (
    SIDECAR_IMMUTABILITY_SQL,
    asset_snapshot_sbom_sidecars,
)

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
table = asset_snapshot_sbom_sidecars
assert [column.name for column in table.primary_key] == ["snapshot_id"]
assert set(table.columns.keys()) == {"snapshot_id", "asset_id", "tenant_id", "adapter_version", "spec_version", "sidecar_sha256", "combined_semantic_sha256", "canonical_payload"}
foreign_key = next(iter(table.foreign_key_constraints))
assert [element.target_fullname for element in foreign_key.elements] == ["asset_snapshots.asset_id", "asset_snapshots.tenant_id", "asset_snapshots.snapshot_id"]
assert "UPDATE OR DELETE" in SIDECAR_IMMUTABILITY_SQL
ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
assert "JSONB NOT NULL" in ddl and "PRIMARY KEY (snapshot_id)" in ddl
(RUN / "sbom_sidecar_table_proposed.sql").write_text(ddl, encoding="utf-8", newline="\n")
cr_path = ROOT / "docs/decisions/CR-R11_sbom_sidecar_table.md"
cr_path.write_text(f"""# CR-R11 · SBOM 私有快照 sidecar 冻结提案

首次创建时间：{started}
写作开始/结束时间：{started} / {datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')}
主控：/root；状态：awaiting_review，仅内部合同，生产迁移 not_run。

依据：用户已批准真实 SBOM、完整资产历史与变化重判。独立纯 adapter 审查确认 projection hash 无法单独代表 dependency/composition 等关系变化；本变更保留这些已要求语义，不增加评分要求。

唯一新增表：asset_snapshot_sbom_sidecars，snapshot_id 为主键；asset_id/tenant_id/snapshot_id 三列外键约束已有私有快照；adapter_version、spec_version、sidecar_sha256、combined_semantic_sha256、canonical_payload JSONB 全必填。两个 hash 固定64位小写hex，版本/租户1–200字符，payload必须object。UPDATE/DELETE触发器拒绝改写，原资产 raw_input BYTEA 仍为唯一原文；不建立新的事实或任务状态。

兼容：既有 snapshot DTO 与 manifest_sha256 保持原 projection 语义，JSON/CSV历史不回填、不重新解析或改hash。新 SBOM current判等使用combined hash，sidecar-only变化必须新增快照、scope epoch和change/outbox；outbox保留 manifest_sha256 并新增 combined_semantic_sha256 与 sidecar_sha256。安全 sidecar 读取用独立接口，不将raw/opaque字段加到旧严格前端DTO。

迁移：生产0022由主控统一，依赖0020/0021后再正式冻结。当前只新增metadata模块，应用不自动create_all，既有0019库不因此声称已迁移。实现者在独占test库forward0019后创建这一局部表，仅计服务集成验证；正式空库/旧资料升级另验收。

回滚：未生产迁移可回退本metadata及依赖它的调用方；生产有历史后不得删除sidecar，仅关闭新增导入，保留读兼容或前向修复。不能只退表而留下调用方查询失败。

任务与测试：R11/T24导入、历史、原文与依赖变化重判；需新增PG真实外键/跨租户/immutable/rollback/replay/sidecar-only变化用例及新独立审查。现静态Ruff/format/mypy单文件通过与DDL/字段/FK assert smoke通过；PG、frontend、e2e、live、manual尚not_run，不签任务或阶段。

定位：修改前实际CBM main5f-assets-sbom-seam 198nodes/823edges，schema/trace与源码rg核对；图未呈现入口调用边，源码inventory_routes直接调用import_manifest已确认，不能据无边推无路径。工具原始输出在本次tool运行记录，未补造未保存的磁盘日志或时间。
""", encoding="utf-8", newline="\n")
files = ["backend/src/ai_intel/assets/sbom_persistence_models.py", "docs/decisions/CR-R11_sbom_sidecar_table.md"]
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip()
subprocess.run(["git", "add", "--", *files], cwd=ROOT, check=True)
assert set(subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).splitlines()) == set(files)
subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
with (RUN / "sbom_sidecar_table_commit.log").open("xb") as output:
    subprocess.run(["git", "commit", "-m", "R11 freeze private immutable SBOM sidecar table seam"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "files": files, "ddl_sha256": hashlib.sha256(ddl.encode()).hexdigest(), "status": "awaiting_review", "pg_migration": "not_run", "push": "not_run"}
(RUN / "sbom_sidecar_table_freeze_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
