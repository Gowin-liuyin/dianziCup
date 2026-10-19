# R06 · 修订模式 PG 测试输入解包修复

文档首次创建时间：2026-10-17T04:13:19+08:00
本次写作开始时间：2026-10-17T04:14:32+08:00
本次写作结束时间：2026-10-17T04:14:32+08:00
最后更新时间：2026-10-17T04:14:32+08:00
证据截止时间：2026-10-17T04:14:32+08:00
任务状态：awaiting_review；本输入修复 implementation complete；整张 R06 仍 partial。
分支：codex/r06-revision-mode-fixture-body-fix
worktree：D:/wt/r06-revision-mode-fixture-body-fix
基线：48f96b5ba35d19f5e26868a2bccd5b124afb2bd0
已测 source SHA：6bb19fcdbf5c8242142c3f61e338b98a29bc5501；独立复核 SHA：尚未发生。
作者：/root/r06_revision_mode_read_root_cause；独立审查者：/root/batch14_revision_mode_first_independent_review。
本地 source commit 已完成；未 push、未 accepted，不代表 G-C 阶段过门。

## 1. 输入、问题与最小修复

独立审查者在冻结 Root48 的真实 PG 中运行作者原 8 例，6 pass / 2 fail。两个失败是 `test_event_detail_keeps_same_pg_source_mode[fixture]` 和 `[live]`。`tests.r06_source_worker_fixtures.source_response("nvd_ollama")` 返回 `(bytes, content_type)`，原 PG 测试把整个 tuple 当 SourceResponse.body；source_documents.py:240 的 bytes 类型边界正确拒绝，错误发生在持久化之前，不能归因于模式投影算法。

我修复自己新增测试的接线：在现有 test 函数前解包 `body, _content_type`，仅传 bytes 为 body。原 allowlisted NVD request URI 字符串不变；media type 绝不是 URI。复用现有录制 NVD 响应、SourceResponse 和解析器，不新增 helper、依赖或业务容错。新增一个离线 contract 验证 tuple 的 bytes 与 JSON media type，并通过原 `_prepare_documents` 出版边界。该记录输入属于显式 fixture，合成 live PG 分支也只是隔离元数据验证，不是现场采集 live。

业务源码、schema/枚举、迁移、锁、Root App、历史数据库、金标、指标分母、共享 helper、前端/SDK均没有改动。原 PG 10 条 assert AST、所有原函数名、SourceResponse 第三参数 URI、原 24 反例原文保持；guard 实际 exit0，见 [fixture_oracle_guard.json](../runs/r06_revision_mode_fixture_body_fix_20261017/fixture_oracle_guard.json)。原报告与红日志保留，没有改失败为 skip。

## 2. 文件所有权、调用方与证据

只冻结这两个测试文件：

- `backend/tests/integration/test_r06_revision_mode_read_pg.py`：2 insertions / 1 deletion 的输入修复。
- `backend/tests/contract/test_r06_revision_mode_fixture_input_contract.py`：一个离线 recorded-input contract。

其余仅本报告与 own run 目录。本次按 Ponytail 5.3.1 full 复用来源夹具，必要新增仅边界反例验证。主控独占状态、业务集成、PG 窗口和 push；不触 reviewer WT。Root 原用户 tsbuildinfo 与其他修改没有 stage。

独立 tests 索引：项目 r06_revision_mode_fixture_body_fix_48f96b5，缓存在 /tmp/r06-revision-mode-fixture-body-fix-cbm-20261017，索引 3276 节点 / 15163 边，工具实际排除了 integration 目录与 pycache。source_response trace caller0、callee nist_pdf1 **不能证明没有调用**；rg 全 backend/tests 交叉查到多条使用路径，其他 PG 来源测试已使用 `[0]` 或 bytes/media 解包。本 PG 唯一错误点与源码和真实原红吻合。索引对应 Root48 加这两个测试的 source tree，见 source_identity.json；没有拿该测试索引为产品完整链路背书。

原 reviewer combined9（作者8+reviewer默认 probe1）实际 6 pass / 3 fail；其中 probe 有同一 fixture 接线问题，由 reviewer 自己修它的输入。原作者8单列6 pass / 2 fail，两者不混计。亲自只读核对如下 raw 文件 SHA256，原件未改：

- D:/dianzi-worktrees/g-c-batch14-mode-review-1/reports/runs/g_c_batch14_mode_review_1_20261017/pg_modes_and_default.stdout.log：fe6876df4e9414f4c641b1e496c3f3537a6000ae25490cae9738c2e1ebfbec16。
- 同目录 pg_modes_and_default.xml：5473df532fd4c89312fbfd116eeb15971eea579aab67420ca4cfe0c3a7fce6e0。

reviewer 告知 B 旧 nonce 库已于 2026-10-17T04:06:04+08:00 安全交回。那是 reviewer 操作事实，不计作作者资源验证；本次作者没有 PG 会话、服务启动、凭据读取、付费/API 调用，产品外部服务新增费用0；编程 Agent 实际费用unknown。

## 3. 实际验证与问题台账

离线共 37 passed / 0 fail / 0 error / 0 skip：{"tests.contract.test_r06_revision_mode_fixture_input_contract": 1, "tests.unit.test_r06_revision_mode": 32, "tests.contract.test_r06_revision_mode_router_contract": 4}。其中新增 contract1，相关 mode unit32 / route contract4；两类不计 live。原 PG 仍完整 collect8 / executed0，没有占 B。Ruff/format 两文件通过；新 contract strict mypy通过。

初次广范围 mypy从 repo 根运行缺 MYPYPATH 导入根，13 import-untyped 与1既有 attr-defined，exit1；原日志保留。补正确 backend 与 backend/src 搜索路径后，旧 PG file:186 metadata `.get` 仍被推断为 object，exit1 / 1 error。这行原断言未改，超出本输入修复；不加 cast/ignore，不以新 contract strict success冒充整 PG 文件类型通过。该旧告警待主控单独分配，未掩盖。

| 层 | 本次实际状态 | 范围/限制 |
|---|---|---|
| unit | passed | 相关32离线 |
| contract | passed | 新1 + 原router4；Ruff/format2与新strict mypy单列 |
| integration | not_run | 修复后的真实 PG8待原 reviewer 根调度B复验，旧8有2红 |
| security | not_run | 本次未重跑权限攻击；没有改安全代码 |
| frontend | not_run | 没有前端改动 |
| e2e | not_run | 未启动API/浏览器 |
| live | not_run | recorded输入和合成元数据不计live |
| manual | not_run | 无人工标注或验收 |

本包代码编写开始/结束未单独打点，写“历史未记录”，不能把命令窗口当编写耗时。首次实际 baseline clock读数2026-10-17T04:09:17+08:00；source冻结实际04:12:12+08:00。各测试时长见下表；真实持续采集观察窗口0。

复用先前 own bounded harness，仅改当前 WT/cache 与运行命令；Windows以 PID+birth枚举含控制 shell的 own full tree，采样间隔50ms，普通cap10 / 60s，CBM Windows+Linux cap16 /60s。普通实测峰8，CBM峰9、每run最长8.156s，没有 breach。采样不被描述成OS硬限制。工具命令、实际退出码、时间与raw均在 own run，无新服务。

| 命令日志名 | 实际开始/结束（+08:00） | exit | 秒 | own tree峰 | 完整命令（cwd本WT） |
|---|---|---:|---:|---:|---|
| offline_input_and_read_contracts | 2026-10-17T04:10:30+08:00 / 2026-10-17T04:10:33+08:00 | 0 | 3.156 | 6 | `["D:\\dianzi\\backend\\.venv\\Scripts\\python.exe", "-m", "pytest", "backend/tests/contract/test_r06_revision_mode_fixture_input_contract.py", "backend/tests/unit/test_r06_revision_mode.py", "backend/tests/contract/test_r06_revision_mode_router_contract.py", "--no-cov", "-q", "--junitxml=D:\\wt\\r06-revision-mode-fixture-body-fix\\reports\\runs\\r06_revision_mode_fixture_body_fix_20261017\\offline_input_and_read_contracts.xml"]` |
| pg_collect_only | 2026-10-17T04:10:33+08:00 / 2026-10-17T04:10:36+08:00 | 0 | 2.296 | 6 | `["D:\\dianzi\\backend\\.venv\\Scripts\\python.exe", "-m", "pytest", "backend/tests/integration/test_r06_revision_mode_read_pg.py", "--collect-only", "--no-cov", "-q"]` |
| fixture_mypy | 2026-10-17T04:10:36+08:00 / 2026-10-17T04:10:42+08:00 | 1 | 6.157 | 6 | `["D:\\dianzi\\backend\\.venv\\Scripts\\python.exe", "-m", "mypy", "backend/tests/integration/test_r06_revision_mode_read_pg.py", "backend/tests/contract/test_r06_revision_mode_fixture_input_contract.py", "--allow-untyped-defs", "--check-untyped-defs", "--follow-imports=silent"]` |
| fixture_format | 2026-10-17T04:10:42+08:00 / 2026-10-17T04:10:42+08:00 | 0 | 0.204 | 6 | `["D:\\dianzi\\backend\\.venv\\Scripts\\python.exe", "-m", "ruff", "format", "--check", "backend/tests/integration/test_r06_revision_mode_read_pg.py", "backend/tests/contract/test_r06_revision_mode_fixture_input_contract.py"]` |
| fixture_ruff | 2026-10-17T04:10:42+08:00 / 2026-10-17T04:10:42+08:00 | 0 | 0.218 | 7 | `["D:\\dianzi\\backend\\.venv\\Scripts\\python.exe", "-m", "ruff", "check", "backend/tests/integration/test_r06_revision_mode_read_pg.py", "backend/tests/contract/test_r06_revision_mode_fixture_input_contract.py"]` |
| fixture_mypy_correct_import_roots | 2026-10-17T04:10:59+08:00 / 2026-10-17T04:11:04+08:00 | 1 | 5.563 | 6 | `["D:\\dianzi\\backend\\.venv\\Scripts\\python.exe", "-m", "mypy", "backend/tests/integration/test_r06_revision_mode_read_pg.py", "backend/tests/contract/test_r06_revision_mode_fixture_input_contract.py", "--allow-untyped-defs", "--check-untyped-defs", "--follow-imports=silent"]` |
| fixture_input_strict_mypy | 2026-10-17T04:11:04+08:00 / 2026-10-17T04:11:12+08:00 | 0 | 8.156 | 6 | `["D:\\dianzi\\backend\\.venv\\Scripts\\python.exe", "-m", "mypy", "backend/tests/contract/test_r06_revision_mode_fixture_input_contract.py", "--strict", "--follow-imports=silent"]` |
| fixture_cbm_index | 2026-10-17T04:11:21+08:00 / 2026-10-17T04:11:28+08:00 | 0 | 7.0 | 9 | `["wsl.exe", "--exec", "sh", "-c", "(printf 'shell '; cat /proc/$$/stat) > /mnt/d/wt/r06-revision-mode-fixture-body-fix/reports/runs/r06_revision_mode_fixture_body_fix_20261017/tool_active_host.stat; exec env CBM_CACHE_DIR=/tmp/r06-revision-mode-fixture-body-fix-cbm-20261017 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r06-revision-mode-fixture-body-fix/backend/tests --name r06_revision_mode_fixture_body_fix_48f96b5 --mode fast"]` |
| fixture_cbm_callers | 2026-10-17T04:11:28+08:00 / 2026-10-17T04:11:31+08:00 | 0 | 3.062 | 9 | `["wsl.exe", "--exec", "sh", "-c", "(printf 'shell '; cat /proc/$$/stat) > /mnt/d/wt/r06-revision-mode-fixture-body-fix/reports/runs/r06_revision_mode_fixture_body_fix_20261017/tool_active_host.stat; exec env CBM_CACHE_DIR=/tmp/r06-revision-mode-fixture-body-fix-cbm-20261017 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project r06_revision_mode_fixture_body_fix_48f96b5 --function-name r06_revision_mode_fixture_body_fix_48f96b5.r06_source_worker_fixtures.source_response --direction both --depth 2 --format json --max-output-tokens 2000"]` |
| fixture_oracle_guard | 2026-10-17T04:11:55+08:00 / 2026-10-17T04:11:55+08:00 | 0 | 0.485 | 8 | `["D:\\dianzi\\backend\\.venv\\Scripts\\python.exe", "D:\\wt\\r06-revision-mode-fixture-body-fix\\reports\\runs\\r06_revision_mode_fixture_body_fix_20261017\\verify_fixture_fix.py"]` |
| source_commit | 2026-10-17T04:12:12+08:00 / 2026-10-17T04:12:12+08:00 | 0 | 0.172 | 6 | `["git", "commit", "-m", "fix(R06): unpack recorded NVD bytes in mode PG fixture"]` |
| source_explicit_add | 2026-10-17T04:12:12+08:00 / 2026-10-17T04:12:12+08:00 | 0 | 0.141 | 6 | `["git", "add", "--", "backend/tests/integration/test_r06_revision_mode_read_pg.py", "backend/tests/contract/test_r06_revision_mode_fixture_input_contract.py"]` |
| source_sha | 2026-10-17T04:12:12+08:00 / 2026-10-17T04:12:12+08:00 | 0 | 0.109 | 5 | `["git", "rev-parse", "HEAD"]` |
| source_staged_check | 2026-10-17T04:12:12+08:00 / 2026-10-17T04:12:12+08:00 | 0 | 0.109 | 5 | `["git", "diff", "--cached", "--check"]` |
| source_staged_names | 2026-10-17T04:12:12+08:00 / 2026-10-17T04:12:12+08:00 | 0 | 0.125 | 5 | `["git", "diff", "--cached", "--name-only"]` |


原始日志：reports/runs/r06_revision_mode_fixture_body_fix_20261017，每个名称有 stdout/stderr/receipt；pytest XML单独保存。环境参数只运行隔离 offline/collect；原日志不改。完整源文件身份与仅 CRLF/LF 差异见 source_identity.json。

## 4. 独立复核、合同与下一步

不产生新的公共合同偏差，沿用 CR-R06_revision_mode_read_projection。修复支持 F1/E1 的 truthful mode 验证，但尚无新评分结果；不能让旧两红自动过门。已将固定 source SHA交原非作者 reviewer；Root安排新有界 B 后复跑原8与它自己的默认API probe。通过前本包 awaiting_review / PG not_run，整R06/R17混合历史限制仍 partial，未知或混合历史503不等于完整历史工作台。

下一步：原 reviewer 定向核 source 6bb19fcdbf5c8242142c3f61e338b98a29bc5501、原URI/10 asserts、PG两红及8完整集，Root核结果再登记；不新建审查流水线、不代签 accepted、无push。

## 5. 文档修订记录

2026-10-17T04:13:19+08:00，作者：首次建立本输入修复报告，全部结果来自当前 run；材料 commit SHA不要求写入自身文档。

2026-10-17T04:14:01+08:00，作者：更正费用口径为产品外部新增0/编程Agent unknown；初次创建时间保留，开始材料字节封存。


2026-10-17T04:14:32+08:00，作者：保留材料checkpoint a0acd09668660adbf96572888dbcfdf14b4e5194。prepare_material 的 staged diff check 发现 own run_checks.py:149 末尾额外空行，exit2；外层 PowerShell未因该非零返回停止，随后错误执行了材料commit。该问题是作者命令控制错误；不改变 source6bb或测试结论。此轮仅删除取证脚本额外EOF空行，重新封存文件raw/Git身份，Python check=True顺序阻止失败后commit。旧manifest及失败checkpoint不覆写，初次创建时间保留，不称旧材料检查通过。
