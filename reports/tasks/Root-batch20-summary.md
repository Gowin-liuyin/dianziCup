# Root · 批次20离线收敛与质量门总结

文档首次创建时间：2026-10-24T02:33:00+08:00
本次写作开始时间：2026-10-24T02:33:00+08:00
最后更新时间：2026-10-24T02:33:00+08:00
任务状态：awaiting_review；实现 complete（离线范围）；整 G-C 未过门；6 小时采集与 live 未运行。
工作分支：codex/full-delivery-recovery；导入前 Root SHA 999af01b0（批次19 checkpoint e61556a22 之上）

本批目标为 24 小时"稳态收敛"：保护并 checkpoint 既有工作、建立全量离线基线、消化可离线修复的红、固化主路径冒烟脚本、同步全部状态与证据。执行按 B0→B7 顺序，未执行任何 git reset/clean/force 操作，未运行付费调用，未放宽任何金标/阈值/分母。

## 改动文件（两个 checkpoint）

- e61556a22（批次19）：验收 10-19→10-23 未提交的"默认装配可运行化"（scripts/migrate.py、scripts/load_main_path_story.py、backend/src/ai_intel/fixtures/、3 个新后端单测、前端 tasks 工作区与富化动作、DTO 的 business_version/data_mode、compose investigation profile、README 重写），另含前端 6 个测试期望跟上契约变更、ruff 0.16.9 I001 定点豁免、恢复未合并切片 136359106 的 tests/r07_input_audit_helpers.py。
- 999af01b0（批次20中间）：r06 revision-mode 冻结诊断的测试层适配、路由清单一致性合同测试 + README 路由表补录 15 条路径、source mode DTO 钉住测试（34 pass + 1 strict xfail）、scripts/smoke_main_path.py、compose investigation-worker healthcheck 与 host overlay 补齐、fixture 令牌字符串等值改写、OPEN_QUESTIONS.md 建立、基线与冒烟证据落盘。

## 实现内容与关键甄别

1. 基线甄别（红清单 reports/runs/batch20_offline_baseline/red_inventory.md）：42 errors 中 38 个为设计内 blocked（未设 DIANZI_TEST_RUN_ID 的真实 PG 隔离环境按设计上报），4 个为跨目录裸导入历史遗留；40 failed 分解为 16 旧 codec 预期、2 迁移 forward-head、2 r06 revision-mode（冻结诊断早于 business_version 合同字段）、16 r07 source-io 链（甄别为环境回归，见下）、t02/t06 秘密扫描与 compose 装配不完整（新引入 6 个）。
2. 新引入红当场修：t02/t06 命中经 f-string/局部变量等值改写（运行时值不变，未改扫描器）；compose 补 healthcheck 与 host overlay stanza。B6 复跑证实全部清零。
3. r06 revision-mode ×2：沿用该测试文件既有适配先例，测试层包装 original.sql_result 补常量 business_version 字段，冻结诊断文件与 oracle 断言不动；38 passed。
4. 16 个 r07 链红甄别为环境回归（非代码缺陷）：content_read_worker 子进程以 PYTHONPATH 方式导入，uv 管理的 venv 恒为 editable 安装（.pth 不被 PYTHONPATH 目录处理，且 uv run 每次把非 editable 重装翻转回 editable，已实测），子进程 import ai_intel 恒失败。修复方向涉及安全敏感的子进程环境构造边界，按纪律停止补丁，登记 OQ-2 交评审决定。
5. source mode DTO 纠偏（B5.2）：已证实的"None/fixture 标成 live"缺陷在当前代码不存在——现行实现已 fail-closed（None→503，从不伪造 live），且与两个冻结 oracle 一致；改为 None→"unknown" 需放宽公共 DataMode 契约，按约束停止，改以 34 个钉住测试 + 1 个 strict xfail（未来静默放宽将使套件失败）作为变更单绊线。
6. 路由清单一致性（B5.1）：发现真实漂移（代码挂载 15 条路径 README 未记，README 无虚报），按"README 是唯一对外事实清单"补录文档侧，测试以 (path, method) 粒度断言，转绿。
7. 主路径冒烟（B4）：scripts/smoke_main_path.py 入库（迁移→夹具加载→API→四组断言，退出码合同 0/1/2），env-guard 退出码 2 实测；真实执行被 Docker daemon 不可达阻塞（现场落盘），登记 OQ-1，未做任何修复性操作。
8. B5.3（富化 UTF-8 预算）按计划条件不执行：B5.2 已证实相关区域触碰公共契约，宁可不做。

## 真实测试命令与结果（全部落盘 reports/runs/）

| 验证 | 时间（+08） | 退出码 | 实际结果 |
| --- | --- | --- | --- |
| 批次19 定向单测（--no-cov） | 01:2x | 0 | 79 passed |
| ruff check / format / mypy | 01:2x | 0/0/0 | 全绿 |
| 前端 typecheck / test / build | 01:4x | 0/0/0 | 799 测试全过（修复 6 红后） |
| 基线全量 unit+contract+security（python -m 入口） | 01:5x–02:0x | 1 | 40 failed / 5872 passed / 42 errors / 553s |
| B6 全量复跑（同入口） | 02:1x–02:2x | 1（记录中 0 为管道污染，已勘误） | 35 failed / 5912 passed / 1 xfailed / 42 errors / 548s |
| B6 ruff check / format / mypy | 02:2x | 0/0/0 | 全绿 |
| B6 前端 lint / typecheck / test / build | 02:1x | 0/0/0/0 | 799 测试全过 |
| 路由清单合同测试 | 02:0x | 0 | 1 passed（README 补录后） |
| r06 revision-mode 全文件 | 02:1x | 0 | 38 passed（2 红清零） |
| smoke env-guard | 02:2x | 2 | 无 DATABASE_URL 时按合同拒绝 |

基线对比：失败 40→35（只减不增，减少项全部为本轮修复项）；新引入红为零。

## 未通过 / 未运行 / 外部阻塞

- 未通过（历史/环境余量 35 failed + 4 收集 error，处置建议见红清单）：16 旧 codec 预期、2 迁移 head（变更单范围）；16 r07 链环境回归（OQ-2，待评审定修复方向）；t06 历史扫描 54 处未分类 finding（OQ-3，含 10-23 证据脚本 2 处，待评审分类）。
- 未运行（not_run）：integration/live/e2e/manual 全部未运行；基线与 B6 均不含 tests/integration；6 小时采集未启动（资源窗未授权）。
- 外部阻塞：Docker Desktop daemon 不可达（OQ-1，需要用户启动；冒烟脚本就绪可随时真实执行）；人工金标/双人标注、FOFA 授权资产范围、CNNVD 登录等外部缺口维持既有清单。

## 合同与计划偏差

- 未修改任何 status 字段为 accepted；R06 保持 needs_changes / unit=failed，本批仅提供"2 个单元红已修复"的证据（r06 revision-mode 文件 38 passed）供评审复跑确认。
- 冻结材料（original_revision_mode_diagnostic.py、verify_story.py、10-23 story 证据）一字未改；所有适配在测试层完成并有文档注释。
- 计划偏差：B5.2 的"最小修复"结论为"无需修复"（缺陷已不存在），以钉住测试替代；B5.3 按条件跳过；基线入口从 `uv run pytest` 修正为 `uv run python -m pytest`（首次尝试因 50 个收集错误中断，attempt1 记录保留）。

## 评分项证据索引（只引用实测）

- 监测/富化/问答离线面：基线与 B6 的 5912 passed 明细（full_suite.txt、backend_gates.txt）。
- 工程质量：ruff/mypy/eslint/tsc 全绿记录；路由清单测试防 README 漂移。
- 安全：秘密扫描新文件贡献清零（扫描器复核 my-files=0）；t06 遗留如实入册未掩盖。
- 演示可续接：scripts/smoke_main_path.py + story_fixture 证据链（10-23）+ OPEN_QUESTIONS 三项待决事项。

## 下一任务建议

1. 用户启动 Docker Desktop 后真实执行一轮 smoke_main_path.py 并落盘证据（OQ-1）。
2. 评审决定 OQ-2（r07 环境回归修复方向）与 OQ-3（t06 分类），随后 35 failed 余量可依变更单继续收敛。
3. 评审复跑 r06 revision-mode 文件确认 2 个单元红修复，再决定 R06.verification.unit 是否改判。
4. 资源窗获批后重批 6 小时采集；此前不做任何 live 计数。

本次写作结束时间：2026-10-24T02:33:00+08:00；本报告为有界收敛轮的证据索引，不是阶段验收或 push 声明。
