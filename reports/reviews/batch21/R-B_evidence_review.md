# batch21 C1/C2 证据链独立审查（非作者）

- 审查人：R-B（批次21 独立审查，非作者视角）
- 审查开始时间：2026-10-25T03:42:01+08:00
- 文档首次创建时间：2026-10-25T03:55:40+08:00
- 最后更新时间：2026-10-25T03:57:39+08:00
- 审查范围：C1 冒烟证据（reports/runs/batch21_single_container_smoke/）、C2 逐文件证据（reports/runs/batch21_integration_unlocked/）、batch21_timeline.md C1/C2 记录一致性、红线核对
- 方法约束：仅 git 只读、读文件、docker 只读查询（docker images / docker ps -a / docker volume ls）；未运行任何测试；未修改本报告目录以外的任何文件；所有结论直接读原始输出，不接受转述
- 审查时仓库状态：HEAD=cc9e1d90 之后工作区（b467cd69c），git status 显示 batch21 证据文件有未提交修改（详见 NC-7）

## 一、C1 单容器冒烟证据核对

### 1.1 attempt7 六组断言逐条核对（确认通过）

reports/runs/batch21_single_container_smoke/attempt7_run.txt 全文核对：

| 断言 | 原始证据位置 | 内容 |
|---|---|---|
| rule_published | attempt7_run.txt:72 | `check=rule_published result=pass detail=rule_status=published rule_version=1` |
| story_assets_present | attempt7_run.txt:73 | `check=story_assets_present result=pass detail=count=2 versions=1.4.1,1.4.2` |
| asset_assessment_1_4_1 | attempt7_run.txt:75 | `check=asset_assessment_1_4_1 result=pass detail=assessment_status=supported_applicability`（:74 资产行 component_version=1.4.1） |
| asset_assessment_1_4_2 | attempt7_run.txt:77 | `check=asset_assessment_1_4_2 result=pass detail=assessment_status=excluded_with_evidence`（:76 资产行 component_version=1.4.2） |
| story_idempotent | attempt7_run.txt:89 | `check=story_idempotent result=pass detail=rerun_state=already-present rule_id_matches=True`（:78 rerun_exit=0，:86 rule_id 与首跑 :63 一致） |
| health_live | attempt7_run.txt:91 | `check=health_live result=pass detail=health_status=200 body_status=live` |

- attempt7_run.txt:92-94：`failures=none`、`smoke_result=pass`、`smoke_exit=0`；:196 `exit=0`。
- attempt7_summary.json：`run_exit_code: 0`，completed_at 2026-10-24T15:10:33+00:00（= 23:10:33+08:00）。
- 六组断言全部真实存在、均为 result=pass，与 timeline "六组断言全过" 记录一致。**确认通过。**

### 1.2 attempt1-7 诊断链与"str(URL) 掩码密码"根因（确认通过）

- attempt1：host_attempt1.txt（全文 12 行）为宿主 NameError traceback（`NameError: name 'attempt_label' is not defined`，dev_single_container.py:246），docker run 已执行但 record_output 前崩溃、容器输出丢失——与 timeline "容器实际跑完但输出丢失" 一致。
- attempt2：attempt2_run.txt:14-21 CRLF 报错（`$'\r': command not found`、`syntax error near unexpected token`），pg_ctlcluster_start_rc=1——与 timeline CRLF 修复记录一致。
- attempt3：attempt3_run.txt PG 启动/建库/uv sync（96 包）成功，末尾 `ERROR database unreachable: OperationalError`、exit=2——一致。
- attempt4：attempt4_run.txt:12 `probe_ok ('smoke_writer', 'story_smoke_20261024')`（裸 psycopg 同 URL 连接成功），smoke 仍 `database unreachable`——一致。
- attempt5：attempt5_run.txt:12-13 双探针：裸 psycopg 成功、`sqlalchemy_probe_failed ... password authentication failed`——一致。
- attempt6：attempt6_run.txt:12 `raw_pw_len 32`，:19 `dialect_pw_len 3 dialect_pw_sha 596f4162a52f315b`——SQLAlchemy 方言路径收到 3 字符密码，直接支持根因。
- **根因双重佐证**：(a) attempt6 raw_pw_sha=bedb16f18fe575b6 与 attempt7 raw_pw_sha=c9777d240a4aace1 不同（每次随机口令），而 dialect_pw_sha 两轮同为 596f4162a52f315b——3 字符值为常量占位符（即 `"***"`），非真实口令；(b) git 提交 6795db3e6（2026-10-24 23:34:59+08，标题含 "str(URL) password masking fix"）diff 显示被删除的旧实现 `def normalize_database_url(database_url: str) -> str: ... return str(url.set(drivername="postgresql+psycopg"))`，新实现返回 URL 对象（现 scripts/smoke_main_path.py:131-136）。conftest 先例在 backend/tests/conftest.py:198（`.render_as_string(hide_password=False)`），timeline 引用行号 196 有 2 行漂移（见 NC-6）。
- attempt7 保留 preflight 探针继续显示 `dialect_pw_len 3`（attempt7_run.txt:19）且 `dialect_kwargs_probe_failed`：与 scripts/dev_single_container.py:130 探针代码一致——探针**刻意复现** str 往返缺陷作诊断留痕，冒烟主路径已改走 URL 对象（migrate_exit=0、database_probe=reachable），二者不矛盾。
- **确认通过：诊断链完整，根因证据（dialect_pw_len=3）真实存在。**

### 1.3 容器脚本与证据一致性、容器清理（确认通过）

- scripts/dev_single_container.py 与证据逐项吻合：证据文件命名 `{attempt_label}_run.txt`/`{attempt_label}_summary.json`（:297、:359）、summary 字段与 attempt*_summary.json 完全一致（:352-358）、`--rm`（:273）、运行后 `docker rm -f` 兜底（:314-315、:348）、2g/2cpu（:277-279）、repo 只读挂载（:281）。
- preflight.txt：7 条 `docker info` 记录（14:56:11 / 14:59:15 / 14:59:47 / 15:01:27 / 15:03:38 / 15:06:45 / 15:09:58 UTC），与 7 次尝试一一对应。
- image_build.txt：1 次构建（14:57:07 UTC，python:3.12-bookworm + pgdg postgresql-16 + postgresql-16-pgvector + uv，exit=0）+ 6 条 `image reuse`（attempt2-7），构建/复用模式与脚本逻辑（:330-338）一致。
- docker ps -a 实查：仅剩 compose-postgres-1 / compose-redis-1 / compose-opensearch-1（30 小时前的既有栈），**无任何 dianzi-batch21-* 遗留容器**；docker images 实查 dianzi:batch21-smoke 存在（与 timeline "保留供 C2 使用" 一致）。
- **确认通过。**

## 二、C2 逐文件证据核对

### 2.1 汇总数字可复算（确认通过）

对 107 个 `test_*_pf.txt` 全量复算（取各文件末尾 pytest 汇总行与 exit 行）：

- exit 直方图：**56 个 exit=0，51 个 exit=1**——与 container_run_summary.txt run6 节 `entries_total=107 entries_failed=51`（:898 节内）及 timeline "56/107 绿" 一致。
- pytest 计数合计：**1103 passed / 74 failed / 511 errors**——与 timeline run6 记录 "1103 passed、74 failed、511 errors" 逐位一致。
- run6 节 107 条 `entry=... exit=...` 与 107 个 pf 文件 exit 逐条比对：**0 处不一致**。
- run5 数字用 git 只读方式复核：HEAD（提交 ff9109a43 "run5 evidence"，2026-10-25 01:49:11+08）中 107 个 pf 文件合计 **1060 passed / 72 failed / 556 errors、56 exit=0**——与 timeline run5 记录 "56/107 绿、1060 passed、72 failed、556 errors" 逐位一致（工作区 pf 已被 run6 以 open("w") 覆盖，run5 原件仅存于 git，属可接受留痕）。
- run2 组级数字：g_offline_unlock.txt:6119 `60 failed, 6030 passed, 1 xfailed, 6 warnings, 73 errors in 1247.64s`——与 timeline "unlock 组 6030 passed / 60 failed / 73 errors" 一致；container_run_summary.txt run2 节 `groups_total=24 groups_failed=21`，3 个 exit=0 组。
- 三个全绿组：g_detachedworkerb21202610110.txt（12 passed）、g_r06catalogr10graphb2120216.txt（35 passed）、g_r07executionapib2120261022.txt（9 passed）——与 timeline "detached_worker 12、r06_catalog_r10_graph 35、r07_execution_api 9" 一致。
- 自由组：g_free_integration.txt:6662 `11 failed, 509 passed, 3 warnings, 568 errors`——与 timeline "自由组 568 errors" 一致。
- A1 收集检查：integration_collect_check3.txt:1888 `1886 tests collected in 2.45s`（0 error）——与 timeline "1886 tests / 0 error" 一致。
- run3/run4 残骸：run3 节 `entries_total=107 entries_failed=104`（仅 3 绿，输出丢失形态）、run4 节仅 `groups_runner_rc=1` 无 entry——与 timeline "run3 输出丢失 / run4 env 未传" 一致。
- **确认通过。**

### 2.2 抽验 12 个文件（确认通过，含指定覆盖项）

绿（exit=0，passed 数真实出现）：

| 文件 | 证据行 | 内容 |
|---|---|---|
| test_detached_job_executor_pg_pf.txt | :12-13 | `12 passed, 1 warning in 28.02s` + `exit=0` |
| test_r02_auth_state_pf.txt | :12-13 | `11 passed, 1 warning in 35.80s` + `exit=0` |
| test_r03_jobs_pg_pf.txt | :12-13 | `15 passed, 1 warning in 11.81s` + `exit=0` |
| test_public_ask_route_pg_pf.txt | :12-13 | `18 passed, 1 warning in 75.80s` + `exit=0` |
| test_r07_publication_acl_lock_fix_pg_pf.txt | :12-13 | `15 passed, 1 warning in 46.47s` + `exit=0` |
| test_r11_r08_migration_head_regression_pf.txt | :12-13 | `46 passed, 1 warning in 37.70s` + `exit=0` |

非 0 退出（失败/错误行与汇总一致，覆盖指定 4 项中的 3 个 pf + g_offline_unlock）：

| 文件 | 证据 | 内容 |
|---|---|---|
| g_offline_unlock.txt | :6119 | 60 failed / 6030 passed / 73 errors（与 run2 汇总一致） |
| test_r11_pg_assessments_pf.txt | :414 | `2 warnings, 33 errors in 3.39s`，port=25432、run_id=r11_assessment_20261016（:1-2）；HEAD run5 版同为 33 errors |
| test_r18_public_producer_fix2_pg_pf.txt | :49 | `2 failed, 36 passed, 2 warnings in 129.40s`，:19 可见真实断言失败（`assert response.json()["error"]["code"] == "not_configured"`）；HEAD run5 版为 `2 warnings, 38 errors in 8.46s`——**与 timeline "38 errors 转 36 passed+2 failed" 逐位吻合** |
| test_r04_knowledge_api_pg_pf.txt | :122 | `10 failed, 14 passed, 2 warnings in 63.07s` |
| test_t24_asset_inventory_pf.txt | :454、:478 | 逐条 ERROR 列表 + `2 warnings, 46 errors in 3.55s` |
| test_r07_input_audit_pg_pf.txt | :174 | `2 warnings, 6 errors in 4.85s`（run_id=r07_execution_20261021，来自 fixture 模块 pin，符合 env 推导描述） |

- 每个 pf 文件头部均有 `run_id=`、`port=`、`pin_ambiguity=`、`file=` 四行（如 test_detached_job_executor_pg_pf.txt:1-4），可追溯到 plan4.json 条目。**确认通过。**

### 2.3 分组/排除/覆盖完整性（确认通过，含 1 项澄清）

- groups.json：24 组 = 1 个 unlock 组（run_id=r07_input_audit_20261016，覆盖 tests/unit+contract+security）+ 22 个钉定组 + 1 个自由组（80 文件，run_id=batch21_c2_free）——与 timeline 分组描述逐项一致。
- 16 个排除文件在 groups.json `excluded`（含理由）与 plan3.json / plan4.json `excluded` 三处**完全一致**，每个文件均有理由（OpenSearch/TLS、MinIO、Celery、Neo4j+DPAPI、real_services×2、R12_OPENSEARCH_URL×3、Compose、DPAPI+预置库、preset db 0012、两个 preset db 0019、R20 launcher、DPAPI+CREATEDB、r06_mode 控制器预置库）。
- 覆盖完整性：backend/tests/integration 现有 125 个文件 = plan4 的 107 + 排除 16 + **2 个新增文件**（test_r10_default_graph_runtime_pg.py、test_r10_graph_runtime_policy_pg.py，均由 R10 提交 b467cd69c 于 2026-10-25 03:13:50+08 加入，晚于 run6 完成时间 03:04）。C2 执行时点 107+16=123 为全量，无漏排。
- plan3 端口分布 99×5432 + 8×25432（与 timeline "8 文件 25432" 一致）；plan4 演进为 95×5432 + 12×25432、pin_ambiguity 6 文件（与 timeline "6 个 pin 歧义文件" 一致）。scripts/dev_integration_container.py:38-46 在容器内建 parentport 集群 @25432，:259 使用 `--rm`，:122 口令为 secrets.token_hex(16) 随机生成。
- **确认通过**（时间戳元数据问题见 NC-2）。

## 三、timeline C1/C2 记录与原始证据的一致性

### 确认一致的部分

C1 attempt1-7 的事实性描述（NameError、CRLF、unreachable、双探针、dialect 诊断、根因、最小修复、attempt7 六断言全过、超出 6 次上限的偏差声明）、C2 的 A1 修复范围、1886 收集、r12 缺失模块恢复说明、run1 挂载报错 exit=125、run2 24 组/3 绿、run2 六条甄别结论（unlock 数字、角色冲突 g_r07inputauditb212026101601.txt `role ... already exists exit=3` 有原件、25432 守卫、跨文件 fixture 继承、unlock 60 failed 分类）、run3-run6 harness 演进与最终数字、16 排除依据——均与原始证据一致。

### 偏差清单（"报告说 X，原始输出说 Y"）

- **偏差-1（NC-1）**：timeline:21 称 attempt1 "23:56 UTC+8"；证据 host_attempt1.txt mtime 10-24 22:57、preflight.txt 首条 docker info 14:56:11 UTC = 22:56:11+08。差 1 小时。
- **偏差-2（NC-1）**：timeline:30 称 attempt7 结果 "23:2x+08:00"；证据 attempt7_summary.json completed_at 2026-10-24T15:10:33+00:00 = 23:10:33+08。差 10-19 分钟。
- **偏差-3（NC-1）**：timeline:63 称 run1 "23:59 启动"；证据 container_run_summary.txt:1-6 run1（挂载报错 exit=125）记录头 2026-10-24T15:35:30 UTC = 23:35:30+08，且 C1 提交 6795db3e6 在 23:34:59+08。差约 24 分钟且晚于 C1 提交。
- **偏差-4（NC-1）**：timeline:64 称 run2 "00:0x–02:0x"；证据：24 个 g_*.txt 落盘时间 10-24 23:57:39 – 10-25 00:28:10（+08），container_run_summary.txt:7 run2 记录头 16:28:12 UTC = 00:28:12+08（记录头为完成时刻，经 attempt2/attempt7 头-摘要时序交叉验证）。实际约 23:55 启动、00:28 完成，与 "00:0x–02:0x" 均不符。
- **偏差-5（NC-1）**：timeline:71 称 run3 "02:3x 启动"；证据 run3/run4 记录头分别为 16:48:12 / 16:48:51 UTC = 00:48+08，run5 完成于 17:47:18 UTC = 01:47+08，run6 的 107 个 pf 落盘 01:49:56 – 03:04:10、记录头 19:04:13 UTC = 03:04:13+08。逐文件阶段实际 00:30（plan3 mtime 00:30:35）启动、03:04 完成。
- **偏差-6（NC-1，范围外提示）**：同一系统性后移也出现在 C3/C6/C3.4/R10：C3.2+C3.3 复跑证据 c32_c33_targeted_rerun.txt mtime 10-24 23:22、C3.1 复跑3 c31_r20_t06_t02_rerun3.txt mtime 23:36（内容 `303 passed in 389.02s`、exit=0）、C3 提交 13a580e23 于 23:35:11+08，timeline 却记 "完成 00:3x"；frontend 门证据 23:38-23:40（batch21_quality_gates/），timeline 记 "01:0x"；full_suite_after_c3.txt mtime 23:57，timeline 记 "01:3x"；R10 证据 host_unit_rerun.txt 03:07 / host_registration_final2.txt 03:13，timeline 记 "06:0x"。timeline 时间叙事整体晚于证据 1.5-3.5 小时。
- **偏差-7（NC-2）**：plan3.json `generated_at: "2026-10-25T02:3x+08:00"`（文件 mtime 00:30:35）、plan4.json `"2026-10-25T05:1x+08:00"`（mtime 01:48:56）、groups2.json `"2026-10-25T02:0x+08:00"`（mtime 00:08:25）——机器可读字段的 generated_at 为含字面 "x" 的手写近似值，且均晚于文件自身最后写入时间，内部自相矛盾。
- **偏差-8（NC-3）**：timeline:71 称 groups2.json（unlock_v2 + 4 个钉定组）"随后补跑"；全仓检索（reports/、progress/、docs/）仅 groups2.json 与 timeline 自身含 h2_* 痕迹，**5 个 h2 组无任何留痕输出**。h2 组覆盖的 tests/contract、tests/security 钉定文件不在 107 个 pf 之列，其在容器内的通过状态无证据留存。
- **偏差-9（NC-4）**：timeline:28 称 "宿主离线验证 password_len=32 保留"；reports/ 与 progress/ 中未检索到该离线验证的留存物（无对应证据文件）。attempt7 容器内通过可部分弥补，但该句本身无证据支撑。
- **偏差-10（NC-6）**：timeline 文档头 "最后更新时间：2026-10-24T22:55:00+08:00" 与正文（记录至 10-25 "06:0x" 叙述）矛盾；C1 节（:20）与 C2 节（:35）状态仍为 "进行中"，与后文 "C1 验收达成 / C2 验收达成口径" 自相矛盾；:39 "OpenSearch×3" 实为 4 个 OpenSearch 相关排除（另含 r01_search_tls_live 的 secure OpenSearch container）；:27 "conftest.py:196" 实为 backend/tests/conftest.py:198；:71 "8 文件 25432" 是 plan3 口径，run6 实际用 plan4（12 文件 25432），正文未更新。
- **偏差-11（NC-5）**：host_run1-6.txt 与 host_attempt*.txt 均为单行 `exit=...`；scripts/ 内无任何脚本生成 "host_run"/"host_attempt" 文件名（grep 无命中），产出者不明、无 docker 层细节；docker 层面记录实际载体是 container_run_summary.txt（6 节 docker run stdout/stderr 完整留存）。

## 四、红线核对

- **凭据**：两个证据目录全量正则扫描（password/token/api_key/secret 赋值、sk-/ghp_/AKIA/Bearer 形态、postgresql:// URL）：未发现任何明文口令或 token。所有连接串密码位均为掩码（如 test_r18_public_read_producer_pg_pf.txt:9 原文 `postgresql://test_dianzi_r18_public_read_20261016:***@127.0.0.1:5432/...`）；SecretStr('**********')、`[redacted test credential fragment]` 均为掩码形态。冒烟证据中口令仅以 sha256 前 16 位出现（attempt7_run.txt:12-14），database_ready 行明示 "(credentials not printed)"（:8）。
- **DATABASE_URL 拓扑**：C1 恒为容器内 `127.0.0.1:5432/story_smoke_20261024`（一次性容器、token_hex 随机口令，scripts/dev_single_container.py:77、:105）；C2 全部 pf/g 证据中的库均为 `127.0.0.1:5432` 或 `127.0.0.1:25432` 上的 `test_dianzi_<run_id>` 一次性库（scripts/dev_integration_container.py 在容器内建两集群并随机建 role/db）。未发现连接宿主父服务或外部库的证据。**红线核对通过。**
- 容器清理：docker ps -a 无 batch21 容器（见 1.3）。docker volume 实查 batch21_smoke_uv_cache 仍在——timeline 合同是 "C2 结束即删"，批次尚未收尾（R10 后续工作仍在进行），列为跟踪项（NC-7）。

## 五、结论

**C1/C2 的核心证据链真实、完整、可复算**：attempt7 六组断言逐条存在且 pass、smoke_exit=0；str(URL) 掩码根因有 dialect_pw_len=3、跨轮恒定 dialect_pw_sha、git diff 三重证据；容器清理无遗留；C2 的 56/107、1103/74/511（run6）、1060/72/556（run5，git HEAD 复核）、unlock 6030/60/73、自由组 568 errors、1886 收集等全部数字与原始输出逐位吻合；12 个抽验文件全部真实；16 个排除三处一致且覆盖当时全部 integration 文件；无凭据泄漏、全部流量在一次性容器内 127.0.0.1。

**主要问题集中在时间元数据与两处证据留存缺口**（不影响 C1/C2 实质验收，但 timeline 为 "唯一进度真相源"，必须修正）：

| 编号 | 级别 | 摘要 |
|---|---|---|
| NC-1 | 中 | timeline 时间叙事系统性晚于原始证据 24 分钟~3.5 小时（偏差-1~-6，含 C3/C6/R10 范围外提示） |
| NC-2 | 中 | plan3/plan4/groups2.json generated_at 为含 "x" 的手写近似值且晚于文件 mtime，机器可读字段失真 |
| NC-3 | 中 | groups2 五个 h2 组补跑无留痕输出，contract/security 钉定文件容器内通过状态无证据 |
| NC-4 | 低 | "宿主离线验证 password_len=32" 无留存物 |
| NC-5 | 低 | host_run*/host_attempt* 单行文件无脚本来源（provenance 不明） |
| NC-6 | 低 | timeline 头部时间戳/状态过时；OpenSearch 计数、conftest 行号、25432 文件数口径未更新 |
| NC-7 | 低 | run6 证据（107 pf 重写、summary +236 行、timeline）截至 HEAD b467cd69c 未提交；batch21_smoke_uv_cache 卷未按 "C2 结束即删" 清理（批次未收尾，需跟踪） |

**needs_changes 合计：7 条（其中中等 3 条、低 4 条）。C1/C2 实质验收证据本身：确认通过。**
