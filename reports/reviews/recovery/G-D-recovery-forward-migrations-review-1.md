# 0023–0026 前向迁移独立审查

What this change does: 这四个迁移将冻结的 R07 输入审计、R12 会话、R10 图投影和 R18 API Key 侧表接入生产 Alembic 前向链。它保留旧事实、原始内容摘要和任务历史，并在数据库层拒绝冻结记录的篡改。

任务：R07/R12/R10/R18 的 **forward migrations 0023–0026 切片**。独立结论：**Verdict: Ship.** 无已确认的迁移 Must fix。此结论不登记 accepted，不代表整张 R 卡、G-D、R20 或任何真实模型/公开产品入口验收。

审查者为新的非作者 agent `/root/recovery_forward_migrations_first_independent_review`。工作树 `D:/wt/recovery-forward-migrations-review1`，分支 `codex/recovery-forward-migrations-review1`；材料 HEAD `2a833225bc5f2dfc720219d6765b034bd6bd6288`；审查代码固定 `16484eaca45791ed2ec403471561faa10ab6d036`，其父版本 `456320b6c78e2936fd9f9767724ec3eb17f5c88b`。没有借用 root main 的代码或索引。报告及证据写入时间以本 run 的 +08:00 命令收据和 manifest 为准；最初阅读/worktree 命令只在工具历史，未补造起止时间。

## 范围、规范与输入

已读 AGENTS、00_execution_map、12_recovery_task_cards 的 R07/R10/R12/R18、03_data_contracts、正式 `CR-R18_api_key_credential_seam`、已批准 CR-R02/07/09，以及相关 R07 工作流/R10 修复/R12 迁移变更。按 Ponytail 5.2 review 检查正确性、历史安全、并发、测试与复杂度；用户要求中文报告优先于该 skill 默认英文。假设负载是多 worker/多请求并发访问同一 PostgreSQL。

审查对象只有四份新 migration 与两份新 test；作者提交共六文件，旧业务、原迁移和原 tests 无变更。独立审查只新增本报告及 `reports/runs/recovery_forward_migrations_review1_20261016`，不改 progress、公共 metadata、认证、env、锁文件、评分/金标或 `.gitattributes`。受保护目录 diff=0，原 head0019 测试 raw 未修改。

精确核验作者 `manifest.json` 中 177 个 source/artifact 条目：Git LF SHA 全部匹配，六源码 Git blob 也匹配，作者工作树六源码 raw SHA 与 manifest 相符。**本独立 Windows 检出的 166 个 raw SHA 与作者 raw 不同，全部只是 CRLF/LF 差异；不能称两者 raw 一致。** `material_inventory.json` 同时保存当前 checkout raw、Git LF 与预期 raw；`verified_evidence_summary.json` 非换行差异为 0。

四输入从原 `frozen_inputs_raw.zip` 逐字节读取，并按输入 revision 的 Git blob/LF 验证：R07 `014de585` SQL、R12 `f557df06` conversation_models、R10 `e8e4086f` graph_projection_models、R18 `8ae692b5` credential_models。四份 archive raw SHA 均匹配。R10 archive raw SHA=`fab1f02b479f852b6e5aaef51123dfcc683e2496552d717254f750a236ff5caa`，Git LF SHA=`23daa49e9486d25eee612a566df9e85d830f3a0560347d892ccef51a64112ea8`，两者明确不同。其余三输入 raw=Git LF。

在独立 run 从 zip 冻结源码重新编译三份 metadata DDL，与材料 SQL 字节一致；users/grounded_answers 占位 table 仅用于 FK 编译，未用 create_all。原五项 R07 DDL、原 R12 owner 函数/触发器及九条额外 guard 分开核验。额外 DELETE/full-row immutable/SHA256/search_path guard 的权限依据是 root 本轮明确审查指令与材料 approved_guards；正式 R18 seam 的仅前向/保留历史要求亦保留。冻结作者 metadata 不因此被宣称已同步 guard，后续同步仍归 root 所有权。

## 已核验行为

| 对象 | 独立核验 |
|---|---|
| 前向链 | 单 head `0022→0023→0024→0025→0026`；完整 26 个 revision；literal DDL 仅 import Alembic op；四 downgrade 明确拒绝；全部 PG migration 子进程安装 create_all 禁止 guard |
| 0023 | 两列 nullable，无默认值/回填；旧步骤保持可用；冻结 receipt 的 hash、workflow/model identity、precreated step、并发只冻结一次；有审计 receipt 的 DELETE 被拒，未冻结旧步骤可删除，result 正常更新 |
| 0024 | 六新表反射中会话两表列/type/null/default/PK/unique/FK/check/index 与重新编译的冻结 metadata 一致；active turn 双列 FK deferred；三个 owner constraint trigger deferred；NULL tenant 用 IS DISTINCT FROM 校验；完整 turn UPDATE/DELETE 拒绝；conversation slot/version/revoke 与 answer pending→terminal 仍正常 |
| 0025 | batch 冻结且实际 SQL `sha256(payload)` 核验；尺寸 8 MiB、唯一序列、kind/hash 格式约束；state 水位允许合法 mutable 更新；无新事实/ACL 外键或业务真相 |
| 0026 | 冻结 owner FK、hash 唯一、resource、非空有序 read scopes、2160 小时上限、撤销/version、分钟桶 FK/主键/read≤60/ask≤10；无明文 token、角色/tenant/当前 ACL 快照或另一套任务预算 |
| 影子 schema | 两个查询函数绑定部署 schema；物理 FK target 和七个触发器的 schema/body/type/enabled/deferred 属性亲复；自构 shadow workflow 和空 owner 影子表仍不能绕过原表的身份/owner guard |
| 历史/失败恢复 | 每次两套隔离库均从真实 0022 开始，54 张旧表、16 张有行表、18 行逐列对比；每级 old row 差异 0。原 bytes SHA=`227f2f7c4ac58efb9f1f5ea4bfe5405c9bb4ea75f9051155b47b688698e3f2cf`。另自构有数据 rollback schema：0026 冲突使 23–25 与版本号单事务回滚，所有旧行不变；关闭旧 engine、另起迁移进程前向 retry 后旧行仍不变 |

冻结 Git caller 核对：R12 conversation_context 的 turn 只 INSERT/read，正常状态改 grounded_answers 与 qa_conversations；R10 graph_projection 的 batch 只 INSERT/read，state 使用 UPDATE；R18 credentials 读取并锁 key/current users，权限交集与 tenant 来自当前 users，rate bucket 原事务内锁/更新。当前迁移没有用 DDL 代替这些服务层认证/预算义务。固定 worktree 源码、Alembic env 和 migration caller 也经 rg 核对；不是借用后续 root main 行为证明本版本。

## 实际命令与结果

全部命令 cwd=`D:/wt/recovery-forward-migrations-review1/backend`，Python=`D:/dianzi/backend/.venv/Scripts/python.exe`。每个 label 的 `.json` 记录完整 argv/cwd/start/end(+08)/exit/head，`.log/.xml` 保存真实输出。

| 实际入口 | 起止（2026-10-16 +08:00） | exit / 结果 | 证据 label |
|---|---|---|---|
| `python -m pytest tests/integration/test_recovery_forward_migrations_0023_0026_pg.py -p review_plugin -o addopts= -q --junitxml=…/pg60.xml` | 10:09:49–10:10:23 | 0；60 passed，0 failed/error/skip；45 新 + 15 原 aggregate 函数 | pg60 |
| `python -m pytest tests/contract/test_recovery_forward_migrations_0023_0026.py -o addopts= -q --junitxml=…/contract18.xml` | 10:11:21–10:11:22 | 0；18 passed | contract18 |
| `python -m pytest …/test_independent_pg.py -p tests.conftest -p review_plugin -o addopts= -q --junitxml=…/independent_pg6.xml` | 10:11:30–10:11:42 | 0；6 passed，0 failed/error/skip | independent_pg6 |
| `python -m pytest tests/contract/test_r11_forward_rules_sbom_migrations.py tests/contract/test_r01_migration_configuration.py -o addopts= -q --junitxml=…/prior_contract7.xml` | 10:11:53–10:11:55 | 0；原 7 passed | prior_contract7 |
| `python -m pytest tests/contract/test_r11_r08_forward_migrations.py -o addopts= -q --junitxml=…/prior_head_original_red.xml` | 10:12:03–10:12:04 | 1；原 4 passed/1 failed/0 skip，head0019 硬断言真实红 | prior_head_original_red |
| `python -m pytest …/test_previous_forward_contract.py -o addopts= -q --junitxml=…/prior_head_own5.xml` | 10:12:08–10:12:09 | 0；自有 head-aware 副本 5 passed；只改副本路径/head/完整链列表 | prior_head_own5 |
| `python -m ruff check <六源码>` / `python -m mypy --follow-imports=silent <六源码>` | 10:12:44–10:12:53 | 均 0；mypy 6 files | code_ruff / code_mypy |
| `git diff 16484eac^ 16484eac --check` | 10:12:44 | 0，代码检查独立通过 | code_diffcheck |
| `git diff 16484eac 2a833225 --check` | 10:14:02 | 2，真实材料空白问题保留，未 trim/全局忽略 | material_diffcheck |

六组自构测试覆盖：all-NULL tenant 合法但改成私有 tenant 即时拒绝；R07/workflow 与会话 owner 影子 schema；四线程同时对 turn/batch 做 no-op UPDATE/DELETE 全拒绝并保留 bytes；ask 最后槽 9→10 仅一线程成功且失败的撤销/version 事务回滚；同 America/New_York 时区跨秋季 DST 的准确 2160 小时成功、超 1µs 拒绝；带旧 fact/auth/job/answer/workflow 行的失败迁移与新进程 retry。它们使用真实 PostgreSQL，无 fixture 成功替代。

`review_plugin` 仅重定向作者测试的 RUN/MARKER/测试资源读取函数，使输出落在独立 pg_author 目录，并使用 `scripts.dev.require_isolated_test_database()` 验证 TEST_DATABASE_URL/DIANZI_TEST_RUN_ID。原 test 文件及测试函数/断言均未改。自有 PG 探针使用另一 marker-owned DB 和独立目录，显式加载原 conftest 并注册 SecretStr failure hook。每 agent 只有一个 pytest 进程，PG 连接采用 NullPool/短时连接，未重启共享 PG、杀他人 session 或连接开发 DSN。

## 审计局限与非阻断改进

1. **应修复：PG 重跑应使用不同证据目录。** 作者新 PG 测试 `backend/tests/integration/test_recovery_forward_migrations_0023_0026_pg.py:153` 和 `:306` 等位置按固定 label 写升级日志与历史快照。其 `pg_1` 顶层 log/xml/json 留存且真实 58 passed/2 failed；fixture 子日志/快照被 pg_2 覆盖，故不能还原首轮全部子命令。下一次运行给每个 attempt 独立 RUN 目录即可，本审查已这样隔离；不要补造或覆盖旧红材料。不修会使下一次红→绿重跑继续丢失中间迁移证据。这不改变本次冻结代码、最终作者 PG2 或本次独立复跑的迁移结论。

材料 diffcheck exit2 来自未改的 metadata compiler SQL trailing whitespace 与红 pytest/rollback 输出空白；本审查未将其改成 passed。原 head0019 测试的真实红也未改文件/skip；副本 diff 和原 raw 同时保留。初次 frozen caller git grep 在 backend cwd 使用仓库根相对 pathspec，真实 exit1 空结果已留存；改为 `:(top)` 后重新核验通过。独立证据汇总首次同名收据覆盖汇总 JSON 的 harness 命名问题已一次修正为 `verified_evidence_summary.json`，原 stdout/命令收据保留，不影响测试。

两套 PG 会出现旧 embedding 反射 vector 的 SAWarning，只用列名收集旧列，不将此 warning 解释为 vector type 合同通过。四份 raw 来源为 synthetic/冻结业务源码与 SQL；旧 raw bytes 也是显式 synthetic，不是 live 原文。

CBM WSL portable 独立 `dianzi-forward-review1-164-20261016` 索引 1819 nodes/9955 edges，已读 schema/architecture/callers；assets 默认排除，另窄索引 `dianzi-forward-review1-assets-164-20261016` 261/1171 并查 schema。trace_path callers=0 的索引局限用源码 rg、实际 tests/scripts caller 和冻结 revision 的 git grep 补足，未将 0 当无调用。未执行工具提示的自动 ADR 写入。

Not checked: unit 独立层 not_run；frontend/e2e/live/manual、PG server restart、真实模型/Neo4j/收费 ask、公开 API/MCP/SDK 客户端接线、全 R07/R12/R10/R18 与 R20/G-D 门均 not_run。当前 ACL、服务预算和产品鉴权仅作冻结源码兼容审查，未用本次 DDL PG 测试为其产品 live 签字。

## 资源、评分证据与交接

独立资源 `test_forward26_393211ef339d` 与 `test_forward26_f39939180b35` 清理前 marker 经数据库核验、session=0；drop 后 database/schema marker=0。`resource_release` 10:12:26–10:12:27 实际复查两库均不存在、own session/schema=0；`release.json` 保存收据，heavy PG slot 已交还 root。没有公开发布、push、自动 accepted 或下一任务接线。

F2/F3/E1/X1 的有限证据是 receipt/turn/batch 不可变、owner/FK/当前 schema 一致、PG 权威侧表、原 bytes/历史逐列保持以及失败回滚/资源清理。本报告不判整个评分项通过。下一步建议 root 按固定 source/material 与本独立 manifest 收据决定迁移切片接入，并协调作者 metadata 的 guard 同步；保留原 head 红、材料 diffcheck 红和首轮日志缺口。

最终报告 SHA、各 run artifact 的当前 raw/Git LF SHA、命令收据、资源 release 与未检查范围在本独立 `manifest.json`。manifest 不把自身纳入自摘要；自摘要由封存后单独收据输出。
