"""Produce the factual bounded-task handoff from recorded results."""

import json
from datetime import datetime
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
history = json.loads((RUN / "history_0022_before.json").read_text(encoding="utf-8"))
populated = sum(bool(rows) for rows in history.values())
manifest = json.loads((RUN / "manifest.json").read_text(encoding="utf-8"))
source_rows = "\n".join(f"| `{row['path']}` | `{row['sha256_raw']}` |"
                        for row in manifest["source"])
report = f"""# R07/R12/R10/R18 · 0023–0026 forward migrations

任务状态：awaiting_review；实现 complete；本报告不登记 accepted，也不代表 R07/R12/R10/R18 整卡或阶段验收。记录时间 {datetime.now().astimezone().isoformat()}。

独立工作树 `D:/wt/r07-r12-r10-r18-migrations`；分支 `codex/recovery-forward-migrations-0023-0026`；base `456320b6c78e2936fd9f9767724ec3eb17f5c88b`；代码 commit `{manifest['source_commit']}`。材料与代码分开提交，未 push。

## 范围与输入

仅增加四个生产 Alembic 迁移、自有 contract/PG tests，以及本报告和 `reports/runs/recovery_forward_migrations_0023_0026_20261016`。输入、旧合同和 workflow/answers/jobs/session 历史结构已核对 AGENTS、00 执行地图、恢复 R07/R10/R12/R18/R20 卡、03 数据合同及 CR-R18_api_key_credential_seam。业务 `backend/src`、原迁移、原 tests、进度、app/env/locks/公共 schema/金标/.gitattributes 均未修改；业务 source worktree/cached diff=0。

冻结输入只用下列版本，原 raw SHA/Git blob/Git LF SHA 在 [frozen_inputs.json](../runs/recovery_forward_migrations_0023_0026_20261016/frozen_inputs.json)：R07 `014de585413c8a82a04d00b1ff2fbd1ff62d733b` 的 0023_input_audit_proposal.sql（raw SHA `ee2fde666548f57cdd56376e443d00592ee107a3efb4d6c169e9c1df6581bbd6`）；R12 `f557df069a0e0eb74194557ebdb9be338d9a5b0e` conversation_models；R10 `e8e4086fccc2d9c3f2f582f85e185f5b6f395f0b` graph_projection_models；R18 `8ae692b5c2824c368b6296481d12695babc717cd` credential_models。作者源接受状态没有被解释为 migration accepted。R07 作者 fix648 business jobs 不在本 ownership。

`frozen_inputs_raw.zip` 保留四份原输入完整字节，特别是 R10 CRLF；可读 `.py/.sql` 副本可能被现有 core.autocrlf=true 存为 Git LF。没有改 .gitattributes 或工具全局配置。metadata 只在独立 run 编译；引用 users.user_id/grounded_answers.answer_id 的占位 Table 仅供编译对照，不是 production model 或建表路径。

## 实现与合同差异

严格 `0022_sbom_sidecars → 0023_enrichment_input_audit → 0024_conversation_context → 0025_graph_projection → 0026_api_key_credentials`，单一 head；生产文件只 import Alembic op，逐项 literal DDL，不导入可变 metadata，不 create_all。

| 迁移 | 行为 |
|---|---|
| 0023 | 两个 nullable 字段，无回填/default；保留冻结五项原 DDL 的审计摘要、workflow/model identity 与 receipt update guard；仅拒绝删除 OLD.input_audit_payload 非 NULL 的 receipt，原无 receipt step 仍可删除，result 正常更新仍可用 |
| 0024 | 两张会话表、原 users/grounded_answers FK、双字段 active-turn deferred FK、唯一轮次/答案身份、三个 deferred owner trigger；完整 turn UPDATE/DELETE 拒绝；conversation version/active turn/revoke 与 answer pending→terminal 可更新 |
| 0025 | 两张可重建投影侧表；batch 唯一序列/尺寸/类型/摘要格式；额外实际 SHA256(payload) 核验与 batch UPDATE/DELETE 拒绝；state 水位正常可变，无另建事实权威 |
| 0026 | 原冻结两表、owner FK、唯一小写 hash、固定 resource、有序非空 read scopes、2160 小时有效期、撤销时间/version、分钟桶 PK/FK/read≤60/ask≤10；无明文 token 或租户/角色快照 |

每个 downgrade 明确拒绝，历史不 drop。原 schema 内对象由部署 search_path 创建；两个查询型 trigger 函数用 `ALTER FUNCTION ... SET search_path FROM CURRENT` 固定部署路径，物理 FK 目标经真实反射对照。历史 to_regclass/version 查询明确 schema-qualified。

上述额外 DELETE/immutable/hash 与 search_path guards 是主控在本轮明确限定授权的完整性加强，未替换原提案字节。依据 AGENTS 不可变历史、不允许模型假设变事实以及 CR-R18 仅前向/保留撤销历史；原 metadata 与 migration 的新增 guard 差异在 [approved_guards.json](../runs/recovery_forward_migrations_0023_0026_20261016/approved_guards.json) 单列。root 负责 formal CR 与作者 metadata 同步；R12 fix 作者已收到精确 DDL/hash。rg 全调用方确认 turn/batch 的正常业务路径只 INSERT/read，未发现合法 UPDATE/DELETE；state 的合法 UPDATE 予以保留。

## 实测命令与结果

统一 cwd=`D:/wt/r07-r12-r10-r18-migrations/backend`，Python=`D:/dianzi/backend/.venv/Scripts/python.exe`。各同名 `.json` 保存实际 argv/cwd/start/end(+08)/exit/head，`.log/.xml` 保存真实输出；不把缺资源改 skip。

| 命令核心（全部真实执行） | 结果与日志 |
|---|---|
| `python -m pytest tests/contract/test_recovery_forward_migrations_0023_0026.py -o addopts= -q --junitxml=…/final_contract.xml` | exit 0，18 passed；完整 26-chain/single head、整链 offline、literal 原 DDL、forward-only、正负边界；final_contract.json/log/xml |
| `python -m pytest tests/contract/test_r11_forward_rules_sbom_migrations.py tests/contract/test_r01_migration_configuration.py -o addopts= -q --junitxml=…/prior_contract_pure.xml` | exit 0，7 passed；原测试未改 |
| `python -m pytest …/testcopy/test_previous_forward_contract.py -o addopts= -q --junitxml=…/prior_contract_adapted.xml` | exit 0，5 passed；只副本路径、旧 head 与完整 chain 列表适配，原 raw/diff/SHA 保留 |
| `python -m pytest tests/integration/test_recovery_forward_migrations_0023_0026_pg.py -o addopts= -q --junitxml=…/pg_2.xml` | exit 0，60 passed/0 failed/0 errors/0 skipped；45 自有 + 15 原 aggregate security 函数，原函数不改，只 head-aware 自有 fixture |
| `python -m ruff check`（六个源文件，完整 argv 在 final_ruff.json） | exit 0；final_ruff.log |
| `python -m mypy --follow-imports=silent`（六个源文件） | exit 0；final_mypy.log，6 source files |
| `git diff --cached --check`（code 六文件） | exit 0；code_diff_check.json/log |

真实 PG 先在空隔离 schema 经全部历史生产 Alembic 升到 0022，再有数据逐级升级到 26。所有迁移子进程实际安装 create_all 禁止 guard，每次进程退出结束连接。PG 对照新建独立 reference schema，逐条执行冻结 compiler SQL，没有用 metadata.create_all 冒充 migration。

历史快照覆盖 {len(history)} 张旧表、{populated} 张有行表；保存完整逐列 row JSON，包含 claims/evidence/document_revisions/hash、auth_sessions、job/outbox、grounded_answers、workflow/step；每级旧列快照完全一致。`raw_content.bin` 是显式 synthetic bytes，与数据库 content_objects hash/size 一致，不是 live 原文。六张新表每列/type/null/default/PK/unique/FK/check/index 经 PG 反射比较；0025 新 SHA 实核单列差异明确检查。七个触发器的 schema/function/body/type/deferred/enable 物理核对通过。

边界包括缺/错 input identity、nullable 部分字段与摘要、必须 precreated step、同一步并发冻结一次、immutable tamper/delete、合法 step result；跨 user/tenant deferred commit、active turn FK/原 answer FK、重复答案/轮次、完整 turn 并发 tamper/delete、正常 conversation/answer lifecycle；batch 摘要/8 MiB/唯一序列与 state mutable；API Key owner/resource/scopes/hash/expiry/version/DST、rate FK/整分钟/最后槽并发与失败事务回滚。隔离 rollback schema 故意制造 0026 表冲突，真实升级失败且 23–25/版本号全回滚，再只前向 retry 成功；另新客户端/迁移进程重启后 revoked key bytes 保持不变。

最终资源 `test_forward26_89877475a840`，[cleanup.json](../runs/recovery_forward_migrations_0023_0026_20261016/cleanup.json) 实测 marker 验证、sessions_before_drop=0、databases_after_drop=0、schema_markers_after_drop=0；heavy PG slot 已交还 root。仅操作 marker-owned DB/schema，没有开发/生产 DSN、没有共享 PG server restart。DPAPI 当前用户 pwsh7 解密只由 Python capture memory 获取；实际 DSN/password 通过 SecretStr fixture hook 登记，PG2 和 owned material 扫描无命中。未保存/打印连接串或密码。

## 失败、未运行与证据局限

`pg_1` exit1：58 passed/2 failed/0 errors/0 skip；是测试 text() 将 JSON literal 的 `:true`/`:1` 当 bind，已改参数+CAST，一次修复后 pg_2 60 全通过；migration 无修改。红 pg_1.log/xml/json 留存。首库 `test_forward26_2b0e49a492a9` 原 cleanup 实测 session0/drop0 已记录 pg_1_resource_cleanup_observed.json。fixture 级 upgrade/history/reflection 固定文件名被 pg_2 复用，首轮逐子命令与快照未完整保留，这是审计缺口；最终 PG2 完整轨迹保留，不伪称首轮全部 raw 保留。

原 prior_contract_original exit1：27 cases=11 passed/1 failed（旧测试硬编码 head0019）/15 errors（隔离 TEST_RUN_ID 在连接前阻断）；无 PG 连接、非业务失败，未改成 skip。上述 15 原行为在 pg_2 用本轮隔离资源跑通过。早期 ruff/mypy/CBM 参数诊断红日志保留；最终对应检查通过。第一批读文件/worktree 建立命令在工具会话可见，未由本轮 checks.py 持久化 +08 起止，报告不补造时间。

独立 material_diff_check 的 git diff --cached --check exit2，命中保留的 compiler metadata SQL trailing whitespace 与红 pytest/rollback log 空白；代码六文件 check exit0。没有改 raw 来涂绿，没有改 .gitattributes 或全局关闭检查。材料空白复核/必要 scoped attribute 由 root 所有权处理；此项不记录 passed。

保留 1 个 SAWarning：旧 embedding 反射仅收集列名时 dialect 未注册 vector，未用该反射 type 作向量合同证明；六新表的类型对照不涉及 vector。独立 unit=not_run（纯检查计入 contract）；frontend/e2e/live/manual=not_run；PG server restart=not_run。没有模型/Neo4j/公开 API/MCP/收费 ask 在线验收，未触及旧 cookie 接线；不据此提升 R12 问答、R10 Neo4j 或 R18 公开入口状态。

## 索引、评分证据与交接

CBM WSL portable 独立项目 `dianzi-forward-0023-26-456-20261016`，fast/persistence=false，1819 nodes/9955 edges；真实 graph schema/architecture/trace_path 输出保留。assets 默认 exclude，源码 rg 补全迁移和 table caller；trace_path 的 inbound0 不解释为无调用，rg 明确覆盖 tests/scripts 中迁移 caller。索引没有加载秘密/KEYS/holdout，没有执行工具自动 ADR 指令。新 migration 不在 backend/src 索引范围，判断使用源码与实际 Alembic chain。

F2/F3/E1/X1 的有限证据为可追溯不可变 receipt、真实 FK/租户引用一致、PG 权威侧表、旧事实保持、失败回滚、隔离清理；不声称整评分项通过。raw/Git LF/source commit 与 artifact 时间快照在 manifest.json。代码 SHA256：

| 文件 | raw SHA256（代码 raw=Git LF） |
|---|---|
{source_rows}

下一任务建议：由全新非作者 reviewer 对代码 commit+配套 material 复跑本切片，确认 formal CR/作者 metadata guards 一致，再由 root 决定有限 migration 状态与接入主线。进度文件由 root ownership 更新，本实现者没有自行 accepted、跨阶段或继续接线。
"""
(ROOT / "reports/tasks/R07-R12-R10-R18-forward-migrations.md").write_text(
    report, encoding="utf-8", newline="\n"
)
print(json.dumps({"report": "R07-R12-R10-R18-forward-migrations.md", "old_tables": len(history),
                  "populated_old_tables": populated, "status": "awaiting_review"}))
