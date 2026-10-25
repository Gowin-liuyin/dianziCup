# OPEN_QUESTIONS

记录被跳过/等待用户输入的事项。每条含：已经验证的事实、具体缺口、影响任务、可以继续的独立部分、最小所需输入。本文件由批次20（2026-10-24）建立。

## OQ-1 Docker Desktop daemon 不可达（批次20 主路径冒烟真实执行被阻塞）

**状态更新（2026-10-25T03:56+08:00 完成事实、2026-10-25T03:56+08:00 勘误记录，批次21 C1）：主路径冒烟已通过"单容器回环"路线真实解决；宿主虚拟交换机故障本身仍未修复（用户侧事项）。**

**状态收束（批次23，2026-10-25T10:2x+08:00）：单容器路线已闭环（冒烟 attempt7 exit 0 + integration 107 文件逐文件真实证据），宿主修复后可回归 compose 宿主验证；宿主侧修复仍归用户，本 OQ 不再作为批次阻塞项跟踪。**

**批次23 宿主复测精确化（2026-10-25T10:3x+08:00，`reports/runs/batch23_quality_gates/host_port_diag.txt` 等五件）**：用户修复虚拟交换机后宿主 Docker **部分恢复**——`docker run --rm hello-world` exit=0；独立 `docker run -p` 的端口发布与宿主→容器数据面正常（HTTP 200 数据回传，25499 实测）。**compose 路径端口发布仍静默失败**：compose.yaml 请求 `127.0.0.1:25433->5432`，容器运行时 `NetworkSettings.Ports` 为 `{"5432/tcp":[]}`、`docker port` 无输出、宿主连接 10061 拒绝——批次20 的症状原样，但仅限 compose 创建的容器（同刻同宿主独立容器正常）。宿主 compose 冒烟因此 `database unreachable` 退出 2（compose_up_exit=0、容器 Healthy、脚本与栈本身正常、teardown 干净）。本机 Docker Compose 为 **v5.0.2**（README 要求 ≥2.24.4）——版本兼容性是用户侧排查方向。按授权未做任何宿主修复；smoke 与 integration 的单容器路线持续可用。

- 批次21 C1 按 OQ-1 实测事实（容器内 loopback 与出网正常）把 PostgreSQL16+pgvector 与被测系统放进同一容器（dianzi:batch21-smoke 镜像，python:3.12-bookworm + pgdg），全部流量走容器内 127.0.0.1：`scripts/dev_single_container.py` 编排，attempt7 真实退出码 0，六组断言全过（迁移/夹具/评估/幂等/健康），证据 `reports/runs/batch21_single_container_smoke/attempt7_run.txt`。
- 过程中发现并修复冒烟脚本真实缺陷：SQLAlchemy 2.1.1 的 `str(URL)` 把密码渲染为 `"***"`，`smoke_main_path.py` 的字符串往返导致密码失效（与宿主无关，任何环境带真实 DATABASE_URL 首跑即触发；宿主侧离线复核 + 容器双探针诊断，6 次尝试定位根因、第 7 次验证修复，cap 偏差已记入 timeline）。
- C2 integration 真实执行复用同一镜像与路线（`scripts/dev_integration_container.py`）。
- 宿主侧修复（重启 Docker Desktop / wsl --shutdown / 排查代理）仍是用户事项；compose profile 的宿主→容器验证在宿主网络恢复前仍不可用，不计为软件缺陷。

**状态更新（2026-10-24T11:1x+08:00）：daemon 已由用户恢复，但 WSL2/Docker Desktop 虚拟交换机数据面故障，真实冒烟经 6 次尝试仍被环境阻塞。**

- 已验证事实（全部落盘 `reports/runs/batch20_main_path_smoke/`）：
  1. daemon 恢复后 core profile 容器可启动且健康（pg_isready 容器内 unix socket 正常）；
  2. 端口发布对任意端口（25499/29500）静默失败：HostConfig.PortBindings 有请求、NetworkSettings.Ports 运行时为空、宿主 netstat 无监听；
  3. 宿主→容器 TCP 握手成功但数据包黑洞（对 172.19.0.2:5432 发送 PG SSLRequest 无响应）；
  4. compose 网内容器→postgres 同样失败（smoke 在网内临时容器、uv 锁定安装成功后仍 `database unreachable`）；
  5. 网桥容器→互联网数据正常（uv sync 成功装完锁定依赖）。
  - 结论：仅虚拟交换机跨端数据面损坏（宿主↔容器、容器↔容器），容器内 loopback 与 VM 出网正常。10-23 同一路径正常，判断为 10-24 会话期间宿主环境变化（安全/代理软件或 WSL 网络状态）。
- 具体缺口：需要用户修复宿主虚拟网络（建议顺序：重启 Docker Desktop → `wsl --shutdown` 后重启 → 排查当日新启用的代理/安全软件）。本批按约定未执行任何修复操作。
- 影响任务：smoke_main_path.py 真实执行；任何宿主侧容器验证。
- 可以继续的独立部分：脚本本身已验证（退出码合同 0/1/2，env-guard=2 实测，锁定依赖安装成功并真实运行到连接阶段）；主路径流程以 10-23 证据为参照。
- 最小所需输入：宿主网络恢复后执行一条命令即可（恢复 `--profile core` 并以 `DATABASE_URL=postgresql://story_smoke:<随机口令>@postgres:5432/story_smoke_20261024` 在网内容器或宿主运行冒烟，见证据文件 attempt6 记录的完整命令形态）。

## OQ-2 content_read_worker 子进程在 uv 管理的 venv 下必然导入失败（16 个 r07 链红的根因）

**已解决（2026-10-25T03:56+08:00 勘误标注）：用户授权后已于提交 `6c9bb455c` 选定方案 (b) 修复——`content_store.py` Windows 分支新增 `_content_read_child_python_paths()`，4 个受影响文件复测 165 passed 全绿（证据见 batch20 续推轮补记与 red_inventory 附注2）。本节以下保留原始记录供追溯。**

- 发现时间：2026-10-24T02:2x+08:00（批次20基线甄别）
- 已验证事实（含最小复现）：`backend/src/ai_intel/infrastructure/content_store.py` 在 Windows 下以 `base_prefix/python.exe` + `PYTHONPATH=<venv>/Lib/site-packages` 启动 `ai_intel.infrastructure._content_read_worker` 子进程；该 venv 由 `uv run`/`uv sync` 管理时项目始终以 editable 安装（`_editable_impl_ai_intel_backend.pth` 内容即 `D:\dianzi\backend\src`）。PYTHONPATH 目录不做 .pth 处理，且 `uv run` 每次都会把 `uv sync --no-editable --reinstall-package ai-intel-backend` 的实体安装翻转回 editable（已实测翻转），因此子进程内 `import ai_intel` 恒为 ModuleNotFoundError → `OSError: content_read_worker_unavailable`（content_store.py:233）→ `tests/unit/test_r07_source_io_deadline.py` 等 16 个测试失败。产品代码在不可编辑安装（如容器镜像）下无此问题。
- 具体缺口：需要评审决定修复方向：(a) 约定本机测试一律 `UV_NO_SYNC=1` 且 venv 保持非 editable 安装（工作流约定）；(b) spawn 环境构造中追加源码布局路径（触碰安全敏感的子进程环境边界，需按变更单走）。
- 影响任务：批次20基线中 16 个 r07 source-io/report/enricher 链测试的分类（环境回归，非代码缺陷）；任何依赖 content_read_worker 的离线验证。
- 可以继续的独立部分：其余全部离线测试、DTO、R06 单测、冒烟脚本编写。
- 最小所需输入：评审在 (a)/(b) 间做出决定（或给出第三方案）。

## OQ-3 t06 秘密扫描遗留未分类 finding（54 处，含 10-23 证据脚本）

**状态更新（2026-10-24T11:3x+08:00）：决议经历一次修正。** 用户授权自决后先执行了逐条分类（54 条记录，全部验证为合成值并带证据链，t06 一度 15 passed 转绿）；随后发现分类表受 R20 冻结登记控制（`tests/security/test_r20_secret_provenance.py` 冻结 total_records=136 = 原 54 + 已审增补 82，且扩展需完整的提案证据束程序），单方面追加登记等于绕过该变更单级控制。已回退分类表至 136 条（R20 复测全绿 158 passed），**54 条已建好的分类记录连同证据链保存于 `reports/runs/batch20_secret_classification_20261024/classification_records_54_ready_to_land.json` 作为待落地提案材料**。

**已解决（2026-10-25T03:56+08:00 勘误标注，批次21 C3.1）**：54 条记录已按 R20 提案程序落地（提案材料 `reports/runs/batch21_r20_registry_extension_20261024/`、bundle `fixtures/synthetic/security/r20_registry_extension_batch21.zip`、CR `docs/decisions/CR-R20_secret_registry_extension_batch21.md`，136→190），R20+t06+t02 复跑 303 passed / exit 0；批次21 C3.4 全量 0 failed，"19 failed 历史余量"表述自此作废（历史余量清零）。

- 落地路径：按 R20 提案程序为 54 条记录建立 fixture bundle + fixture_bindings + 更新 total_records（54→190），走变更单；完成后 t06 转绿。
- 影响：t06 维持唯一历史红（16 codec + 2 迁移 head + 1 t06 = 19 failed 最终余量）；不影响其他批次。
- 最小所需输入：评审/下一批次按 R20 程序落地上述提案材料。

## OQ-4 公开 /tasks 需要新 producer（批次21 C5.2 盘点结论，非纯接线缺口）

- 发现时间：2026-10-25T01:1x+08:00（批次21 C5.2，盘点报告 `reports/tasks/Root-batch21-public-producer-inventory.md`）
- 已验证事实：GET /tasks/{task_id} 背后 `public_extension_reads.py:801-805` 的 `get_task_result` 是恒 503 桩，且该桩语义被 `tests/integration/test_r18_public_read_producer_pg.py:250` 冻结测试钉住；按冻结契约已写好的真实读取 producer `PublicTaskBindingService.read_in_session`（`public_task_bindings.py:594`）在 src 中零装配零导入；写侧 `bind_in_session` 同样无生产调用方（/ask 为同步问答不入队 typed job）。端到端闭环需要新增"ask 受理入队 + typed job 绑定 + 发布"整条 producer 链，属于新功能开发而非接线缺口，且改 503→404 语义需变更单。
- 影响任务：R18 公开任务读取面的端到端可用性。
- 相邻发现：`public_risk_summary.py` 为同家族更彻底的未接模块（无路由、src 零导入），见盘点报告。
- 可以继续的独立部分：其余公开面（/vulns /sources /ask）已证实完整接线，契约测试齐备。
- 最小所需输入：评审决定是否立项 typed-task producer 链（涉及新路由语义、入队与绑定流程、变更单）。

## OQ-5 R19 人工依赖项与 C2 长尾（批次21 C5 完成后的剩余缺口）

- 记录时间：2026-10-25T03:56:00+08:00（批次21 C5 收口）
- **R19 人工侧未达成项**（工具与装配基础设施已就绪并测试覆盖，见 `reports/runs/batch21_r19_implementation/implementation_report.md`）：真实双人独立标注、分歧裁决、身份核验、冻结 manifest 签字、真实规模扩展（依赖 R04–R16 真实闭环）、镜像/索引泄漏审计——均需人工输入或资源窗，0 gold 如实保持；正式指标声明继续 not_run。
- **C2 integration 长尾**（107 文件全部有真实 exit code 与数字，56 绿；证据 `reports/runs/batch21_integration_unlocked/`）：51 个非绿文件按类收敛为 (a) 钉定 db/端口拓扑残差——需按 fixture-cluster 预置库拓扑逐文件预置（r11/r15/r16/r18/t24 等，含 6 个 pin 歧义文件）；(b) 平台敏感断言（r07_source_io 37 例为 Windows 语义，宿主 6080 passed 为权威，跨平台统一属产品级工作）；(c) 宿主环境测试（compose/TLS 渲染 21 例，容器无 docker CLI，宿主已证绿）；(d) 真实业务失败待逐条甄别（r04/r05/r06/r07 局部，约 30 例，每个都有完整 traceback 在 *_pf.txt）。下一批建议按 (d)→(a) 顺序收敛；(b)(c) 维持宿主为权威环境。
- **R21 评审待确认口径**：config_sha256 绑定整份配置（含 baseline_id）导致跨基线不同——r21_plan §5 C01 的"相同"字面预期按"资源字段跨基线一致 + 同基线复跑不变"实现（`reports/runs/batch21_r21_implementation/implementation_report.md` §5.1），需评审确认。
- **C2 审计族前置条件（plan5 两轮定向重跑后精确化；批次23 解锁）**：`tests/security/test_r07_input_audit_security_pg.py` 与 `fix1_acl_pg` 的 `owned_audit_engine` fixture 要求 (1) drivername=`postgresql+psycopg`（已解决）(2) 端口=25432（已解决）(3) 一个迁移状态与 helper 自装约束不冲突的预置库。**批次23 解锁（2026-10-25T09:3x+08:00，`reports/runs/batch23_audit_family/fixed_run3/`）：审计族 5 文件 52 passed / 0 failed，容器 exit=0。**诊断精确化修正：原记录把第三层归因为"provisioning 迁移 head 与 helper install 冲突"，实测冲突是 helper 自身在 fresh schema 里 `run_migrations(head)`（含 0023——该迁移采纳了 test proposal 的 DDL）与 `install=True` 重装的内在冲突，与 provisioning 库状态无关；修复为 helper 迁移目标钉 `0022_sbom_sidecars`（恢复 helper docstring 自述的"proposal 是安装者"合同，fixture 层一行）。另两件配套修复：`R07_INPUT_AUDIT_TRACE_DIR` 写重定向（observation 文件原目标目录不存在且容器只读）与 harness 组模式可选 `port` 钉定（security 文件裸导入需同组收集 + helper 断言 25432）。r14_tools_fix1 的 `test_review_real_pg_query_time_is_bounded_not_only_lock_time` 为 (d) 类真实业务失败（19 passed/1 failed，traceback 在案）。
- **批次22 目标1 取证结论（2026-10-25T06:2x+08:00，`reports/runs/batch22_d_triage/plan_evidence.json` 三文件重跑）**：剩余 6 例中 3 例 D 类已取证升级为 B 类（产品行为/冻结 oracle 裁决，非环境）：r07_job_execution 维度 outcome `partial` vs 冻结期望 `failed`；r14_read_adapters `ToolStatus.FAILED` vs 冻结期望 `partial`（ACL 隐藏态 event_detail）；r14_default_runtime HTTP 200 但 0 行 vs 期望 1 行（独立库下稳定复现）。**批次23 三项裁决收束（2026-10-25T10:3x+08:00）**：r05 legacy-0013（19 例）、r04_source_documents evidence 计数（1 例）、公网读错误码映射（5 例）已按 `progress/DECISIONS_pending.md` 建议项执行闭环（三份 CR：`CR-r05_legacy_seed_annotation_batch23.md`、`CR-r04_evidence_count_oracle_alignment_batch23.md`、`CR-public_read_projection_error_mapping_batch23.md`），受影响文件容器复跑全绿（24/25/9+28+38 passed），证据 `reports/runs/batch23_decisions/`。r07_job_execution / r14_read_adapters / r14_default_runtime 三例 B 类取证（outcome/状态映射/0 行机制）仍未裁决，留待评审。至此 C2 长尾归属：审计族已解锁；三项裁决已闭环；3 例 B 类取证待评审；pgvector 0.8.2 钉版仍不可行。
- 最小所需输入：人工标注资源窗（R19）；下一批 C2 收敛工作包授权（无需新授权类型，纯离线+容器）；R21 口径评审意见。

## OQ-6 SourceEnricher UTF-8 输出预算触合同停止（批次22 目标2，按停止条件记录）

- 记录时间：2026-10-25T04:50:00+08:00（调研报告 `reports/runs/batch22_source_enricher_research/research.md`，全程只读）
- 已验证事实：(1) UTF-8 计量本身已存在且被冻结测试钉定为正确语义（`_output_json_bytes` 按 ensure_ascii=False 真实 UTF-8 计数，investigation/workflow_service.py:139-145，冻结测试 test_r14_source_report_output_budget.py:108-112）——"缺口"不在计量；(2) 唯一可新增的是行为级预算约束（trim-to-fit 裁剪），但其反面（大报告超预算→整体拒绝、receipts 清空、公开结果为空）是本区域冻结 oracle（unit :435-473 与 integration :285-308，B2/B2b/B3 × 1024 全策略钉死）；(3) 富化 receipt 输出经 WorkflowResult 直入公开 API DTO（graph_contracts.py:92-102 → investigation_routes.py:80,300）。
- 三条实现路径（裁剪行为 / DTO 字符串字节上限 / 预算参数）全部触碰冻结断言或公共合同/阈值——按批次22 计划停止条件停该项。
- 影响任务：富化输出预算行为约束；未来如需实现，走变更单（research.md §3 有最小变更单路径与约 20 条不可动冻结断言清单）。
- 最小所需输入：评审决定是否立项该行为变更单。
