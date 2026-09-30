# R-G1A · T03+T04 批量独立审查报告

- 审查人：独立审查代理（非实现者；实现者=主控）
- 审查时间：2026-10-01 00:00—00:12（本回合内复跑）
- 工作目录：D:\dianzi
- 范围：T03（开发依赖容器与配置分层）、T04（领域类型、枚举与 JSON Schema）核心项；未查项如实记 not_run
- 依据：docs/tasks/T03_development_services.md、docs/tasks/T04_domain_contracts.md、docs/plan/03_data_contracts.md §1-2（T04 合同对照主范围）、AGENTS.md
- 主控范围澄清（已遵守）：backend/migrations/、backend/src/ai_intel/knowledge/、infrastructure/ 新增文件与 pyproject/uv.lock 变化属 T05 并行轨道，不计 T03/T04 违规
- 停止/升级项核查：**无升级**（无伪造测试、无密钥泄露、verify_plan --baseline = PLAN_OK）

## 0. 报告落盘状态

| 文件 | 状态 |
|---|---|
| reports/tasks/T03.md | **missing**（文档批 DOCS-G1A 并行撰写中，审查时未落盘；结论基于代码与 reports/runs/t03_*.log） |
| reports/tasks/T04.md | **missing**（同上） |
| progress/task_state.json | T03/T04 仍为 pending/not_started（未更新，与"报告落盘后统一更新"的流程一致；本审查不修改 progress/） |

---

## 1. T03 · 开发依赖容器与配置分层

### 1.1 审查对象 SHA-256

| 文件 | SHA-256 | 字节 |
|---|---|---|
| infra/compose/compose.yaml | 5c1a446944307c2d897d5b3a6737ce2bb8997da6d5c8603390a5860db2ebf7c7 | 1980 |
| config/dev.env.example | 5796763e71f4b07fbb0f38bb389716ad749f9db5a2ea605b5fc4b242ff23b7a4 | 357 |
| backend/src/ai_intel/infrastructure/settings.py | fdae8ac86077eda8e0b6857550154f50ad1188943a1841838fdc401d5c279f99 | 3153 |
| scripts/dev.py | 17331251f3e25fd2c4ec08858ca556fa6cf67549a55727d7a02d14d6df1adf8c | 6927 |
| backend/tests/integration/test_t03_development_services.py | 78014c32c043e594f36d837ab142489bf98821abbb088ce8cf4fc04c568ecbdd | 6858 |
| reports/runs/t03_compose_check.log | 4be4b5cdd5bfbe29b804dfef9a8bb59c96501a24f481fe8ec633994bc173d218 | 207 |
| reports/runs/t03_persistence_check.log | 09d8273e061062ea7a04999ff03b35c0369d3c79192bafd4e4d53fdea735e8fe | 801 |
| reports/runs/t03_services_startup.log | 3401cf4a93f7145ce187ddd9af52a8197f41f4a68ac7358393d6351dc71596cc | 884 |

### 1.2 复跑命令表（全部为本回合实测）

| 命令 | 工作目录 | 退出码 | 结果 |
|---|---|---|---|
| uv run pytest tests/integration -q --cov-fail-under=0 -v | backend | 0 | **6 passed**（真容器，10.44s；含重启/down/up），1 warning |
| uv run pytest tests/unit -q | backend | 0 | **24 passed**（覆盖率 81.64%，门槛 60） |
| uv run ruff check . | backend | 0 | All checks passed! |
| uv run ruff format --check . | backend | 0 | 13 files already formatted |
| uv run mypy src | backend | 0 | no issues found in 10 source files |
| E:\miniconda\python.exe scripts/dev.py services deps-check | 根 | 0 | postgres/redis/opensearch 均 healthy，overall: ready |
| E:\miniconda\python.exe scripts/dev.py check --scope security | 根 | 3 | 输出 `ERROR not_implemented: security`，**无 PASS 字样** ✓ |
| E:\miniconda\python.exe scripts/dev.py check --scope integration | 根 | 0 | 6 passed（透传 pytest 退出码）✓ |
| python scripts/verify_plan.py --baseline contracts/baselines/plan_baseline_t01.json | 根 | 0 | **PLAN_OK**（冻结未动；注：`--baseline` 需带基线路径参数） |
| 复跑期间 DOCKER_HOST 指向无效管道再跑 integration（C05 仿真） | backend | 0 | **6 skipped**，skip 理由="blocked: 容器环境不可用（T03-C05）…不使用 SQLite 冒充" ✓ |

### 1.3 必查项判定

1. **测试/lint/type 复跑：通过。** integration 6/6 真实容器（测试直接 docker compose exec psql/redis-cli 与 127.0.0.1:9200 HTTP 探针，无 mock、无 SQLite）；unit 24/24；ruff/format/mypy 全 0。
2. **deps-check 与 scope：通过。** 三服务 healthy→overall ready exit 0；security=3 且无 PASS；integration=0。
3. **验收断言真实性 T03-C01—C06：基本通过，附 1 项普通问题（见 1.4-F2）。**
   - C01：真容器三探针（pg_isready+SELECT 1、redis-cli ping→PONG、OpenSearch _cluster/health status∈{green,yellow}）——真实可观察 ✓
   - C02：真实写表→`docker compose restart postgres`→读回 'survives-restart' ✓（实现批日志 t03_persistence_check.log 另有 down/up 二次读回佐证）
   - C03：断言"search 降级不谎报 ready"存在（readiness dict 检查），但**断言只落在 settings 层**（opensearch_url=None），未覆盖"search profile 未启动→dev.py services deps-check 退出 4/degraded"的真实容器态路径（该行为仅有 t03_services_startup.log 人工证据："deps-check exit=4"）→ F2
   - C04：双负例测试存在（production+fixture、production+占位秘密均期望 ConfigurationError），并经审查人独立复算实测确认（见 1.5）✓
   - C05：模块级 skipif=blocked 语义经**实测仿真确认**（DOCKER_HOST 失效→6 skipped 且理由含"不使用 SQLite 冒充"）✓
   - C06：真实 down（不带 -v）→卷名保留（compose_postgres_data 等）→up→数据读回 'survives-down-up' ✓
4. **安全/边界：通过（附建议级备注）。**
   - compose 三服务端口均仅绑定 127.0.0.1 ✓；资源限制、健康检查、持久卷齐备；镜像钉版（postgres:16.4 / redis:7.4 / opensearch:2.17.0）✓
   - dev 占位秘密仅开发语义（dev-only-not-a-secret / Dev-Only-Not-A-Secret-1!），无真实密钥 ✓；production 校验拒绝占位秘密与 fixture（负例实测，见 1.5）✓
   - down 默认不删卷、`--confirm-destroy` 才加 -v（代码路径确认；销毁路径属破坏性操作 not_run）✓

### 1.4 问题分级（T03）

| 编号 | 级别 | 问题 |
|---|---|---|
| F1 | 普通 | **T03 §4.6 未落实**：README 与 CI 未随任务更新。README 仍称"容器化与容器集成测试 not_implemented""check --scope integration not_implemented"，与 dev.py 已实现 integration scope 的现状**互相矛盾**；任务卡要求的"CI 集成服务配置 + 实际内存/磁盘需求 + 未验证平台"记录均缺失（ci.yml 无集成 job）。属交付缺口而非造假，但 README 当前陈述已过时失实 |
| F2 | 普通 | **C03 断言层级不足**：自动测试只验证 settings 层 readiness 字典，没有回归测试锁定"profile 未启动→deps-check exit 4/degraded"的 CLI 真实路径；仅有人工日志证据，防回归能力缺失 |
| F3 | 建议 | subprocess(`text=True`)未指定 `encoding="utf-8"`（test_t03 的 run_compose 与 scripts/dev.py run_compose_services）：本回合 integration 复跑出现 PytestUnhandledThreadExceptionWarning（GBK 解码 0xa6 失败），中文 locale Windows 下 docker 输出解码脆弱，建议显式 UTF-8 + errors="replace" |
| F4 | 建议 | `containers_available()` docstring 称"探测…且本项目服务在运行"，实际仅检查 `docker compose ps` 退出码：docker 可用但服务未启动时测试会 error 而非 blocked 跳过（docstring 与实现不符；"无容器权限→blocked"语义本身正确） |
| F5 | 建议 | production 占位秘密检测为子串匹配且仅覆盖 DATABASE_URL："password" 子串可能误伤合法密码（保守方向），auth_secret_ref 的占位值不检；`--confirm-destroy` 传给 down 以外子命令被静默忽略；compose 注释称 OPENSEARCH_INITIAL_ADMIN_PASSWORD"经环境注入"但实际为文件内字面量（占位值、无真实秘密，仅注释措辞不准） |

### 1.5 production 负例独立实测（非复述测试期望）

| 输入 | 实测结果 |
|---|---|
| production + fixture + 强秘密 | ConfigurationError: "DATA_MODE=fixture is not allowed when APP_ENV=production" ✓ |
| production + live + dev-only-not-a-secret | ConfigurationError: "DATABASE_URL contains a development placeholder secret…" ✓ |
| production + live + changeme | ConfigurationError（占位秘密拒绝）✓ |
| production + live + 强秘密（对照） | 通过（无报错）✓ |
| development + fixture（对照） | 通过 ✓ |

### 1.6 T03 结论

**accepted（附条件）**。
条件（G1 阶段检查前完成，不影响本任务代码面结论）：
1. 补 T03 §4.6：更新 README（修正与 dev.py 矛盾的 not_implemented 陈述、记录实测内存/磁盘需求与未验证平台）与 CI 集成服务配置（F1）；
2. 补一条 C03 容器态回归（search profile 停止→deps-check exit 4 + degraded 输出断言）（F2）。
必须修复项（needs_changes 级）：**无**。伪造/泄露/冻结破坏：无。

---

## 2. T04 · 领域类型、枚举与 JSON Schema

### 2.1 审查对象 SHA-256

| 文件 | SHA-256 | 字节 |
|---|---|---|
| backend/src/ai_intel/domain/enums.py | 2b2a580e5b27a386ca6f4b097d6407c65e88ab97ae9ceac58ff9bb8ca031f708 | 3714 |
| backend/src/ai_intel/domain/values.py | 06b03e0979b069ad24f6db391a5607876e06aeaa030297daebcd318efd20f288 | 3455 |
| backend/src/ai_intel/domain/records.py | 428825ca10be666d01419e6e75ef46e9836f61663fd9b21cfbc025fe16df1bab | 3471 |
| backend/src/ai_intel/domain/schema_export.py | d1b561bbd10ff5fd989b3a0e3b606edc13b2071092b522acaaf65a1d4c3833b9 | 1776 |
| backend/tests/unit/test_t04_domain_contracts.py | 3c67520f31ca4b6f4470535ade9534374484f28a4e6cdbe3b005261d4d90f0d0 | 6132 |
| contracts/schemas/schema_bundle.json | 3f06dedecc524fe271ef6cf55253e50a093543b8d6cf05b9ca20fc0509448a34 | 18167 |
| docs/plan/03_data_contracts.md（合同对照依据） | ff5e87d080a1e42734683e6bf3bcc37ac194ffa8f1b43c1293398606693e62e0 | 13770 |
| docs/tasks/T04_domain_contracts.md（任务卡依据） | 9b028fa5dfd4e9f6cee82f9cdbd4fb735ba85a5180b1300fb705d56c1259d0d0 | 3900 |

### 2.2 命令表

| 命令 | 退出码 | 结果 |
|---|---|---|
| uv run pytest tests/unit -q（含 test_t04 13 项） | 0 | 24 passed（T04 侧 13） |
| uv run pytest tests/integration -q --cov-fail-under=0（回归） | 0 | 6 passed |
| ruff check / format --check / mypy src | 0/0/0 | 全部通过 |
| 独立复算 render_schema_bundle() 两次比对 | — | **字节一致**（确定性 ✓） |
| 复算结果 vs contracts/schemas/schema_bundle.json 落盘内容 | — | **逐字节相等**（落盘=生成器输出，无手改漂移）✓ |
| 独立脚本枚举值集合比对（12 枚举 vs 03 §2） | — | 12/12 **逐一完全一致**（值集合与顺序均同）✓ |

### 2.3 必查项判定

5. **复跑与 C01—C06：通过。** 13 个测试覆盖并保留 case ID 语义（docstring 标注 C01—C06）；C03 unknown≠false 序列化往返后仍异 ✓；C05 多余字段 skip_validation 拒绝（extra=forbid，负例真实断言 ValidationError）✓；C06 重复生成无漂移 + 版本一致 + 审查人独立复算确认落盘一致 ✓。C04 双分支（无时区拒绝、倒置区间/负偏移拒绝不取绝对值）✓。
6. **合同对照（03 §1-2）：通过（附普通级附注）。**
   - 12 枚举与 §2 逐一对应（脚本比对 12/12 全同）✓
   - ClaimStatus/ConditionValue/FreshnessStatus/JobStatus 四个独立 StrEnum 类，未合并 ✓
   - 左闭右开（EvidenceSpan end>=start，倒置拒绝不交换）、visibility 约束（public 禁 tenant_id、tenant 必填 tenant_id）、schema_version 必含（5 个记录均有）✓
   - 无 Any/cast/type: ignore/noqa（grep 于 domain/ 为空）✓；无万能框架（StrictRecord 仅 extra=forbid+frozen 薄基类）✓；命名/docstring 合规（英文语义命名、docstring 讲职责与约束）✓
   - 附注：§3 数据对象仅实现 5 个记录（Source/Document/Evidence/Claim/Assessment），资产/规则/任务等 DTO 未建（任务卡 §4.1 提及）；schema_bundle.json 仅携带 7/12 枚举（缺 ToolStatus/JobStatus/PocStatus/DimensionStatus/RuleStatus 的值）——若作"前端类型来源"仍不完整，见 G2/G3
7. **诚实性：** 两任务报告 missing（记 missing，不以缺失推断）；实现批现存日志/交接声明与实测复核相符（"6/6 真容器""13 测试 C01—C06"等均属实，无夸大）；dev.env.example 与 compose 仅开发占位值、无真实密钥，production 校验实测拒绝占位秘密 ✓。继承 G0 限制：CI 未实际运行（not_run）、live/性能/外部对照 not_run。

### 2.4 问题分级（T04）

| 编号 | 级别 | 问题 |
|---|---|---|
| G1 | 普通 | **DTO 覆盖不完整**：仅实现 5 记录，任务卡 §4.1 的资产/规则/任务（及 §3 的 SourceCursor/FetchAttempt/TextBlock/Entity/Event/ClaimEvidence/EnrichmentResult/VersionRange/PublishedRule/Asset*、JobRun/OutboxEvent/Investigation/ToolRun、Answer 等）未建。C01—C06 未要求，但"按 03 建立…资产、规则、研判和任务 DTO"是 §4.1 明文步骤；若渐进实现应显式声明归属任务，不能默认已完成 |
| G2 | 普通 | **字段语义相对 03 §3 存在简化**：EvidenceRecord.supports_claim: bool 无法表达合同的 support_kind(supports/refutes/context)+validation_status（"context"维度丢失）；ClaimRecord.object_value 为纯 str，未按"受 predicate 限定的联合类型"建模；EvidenceSpan 未含 revision_id/block_id/quote_sha256。§3 不在本次强制对照范围（§1-2 全过），但属合同偏差，应走变更单或在 T04.md 声明分期 |
| G3 | 建议 | schema_bundle.json 仅含 7/12 枚举（缺 ToolStatus/JobStatus/PocStatus/DimensionStatus/RuleStatus），作前端类型来源不完整；随 DTO 补全时应一并导出 |
| G4 | 建议 | values.py `end_offset_must_not_precede_start` field_validator 为**空操作**（原样返回 end_offset，真正校验在 model_post_init）：docstring 声称其拒绝倒置区间但行为不符，属误导性死代码，建议删除或移入该 validator |
| G5 | 建议 | schema_export.write_schema_bundle 文件写出路径未被测试覆盖（coverage 67%，45-49 行缺失）；Identifier 的 UUID 校验对 bytes 输入的 AttributeError 兜底分支未测 |

### 2.5 T04 结论

**accepted（附条件）**。
条件（G1 阶段检查前完成）：
1. G1/G2 二选一处置并留痕：补全缺失 DTO 与 §3 字段（或以变更单/任务报告显式声明分期归属与偏差理由）；
2. G4 空操作 validator 清理。
必须修复项（needs_changes 级）：**无**（强制对照项 §1-2 与 C01—C06 全部通过）。

---

## 3. not_run 清单（如实）

- `services down --confirm-destroy`（-v 销毁卷）破坏性路径：not_run（代码路径已核对：仅 --confirm-destroy 追加 -v；实测销毁不做）
- CI（.github/workflows/ci.yml）实际运行：not_run（继承 G0 限制，CI 未运行过）
- live/性能/持续运行/外部对照：not_run（无真实模型/FOFA/来源）
- reports/tasks/T03.md、T04.md 内容审阅（诚实性条目 #7 的"报告无夸大"部分）：**not_run—文件 missing**，待文档批落盘后由后续审阅补验
- T05 并行轨道文件（backend/migrations/、knowledge/、infrastructure/ 新增、pyproject/uv.lock）：out_of_scope（主控澄清）

## 4. 升级项核查

| 条件 | 结果 |
|---|---|
| 伪造测试 | 未发现（integration 6 项均真实容器操作，unit 13 项真实断言；复跑数字与实现批声明一致） |
| 密钥泄露 | 未发现（compose/dev.env 仅设计内开发占位值，无真实秘密；报告与日志无密钥值） |
| verify_plan 非 PLAN_OK | 否：`python scripts/verify_plan.py --baseline contracts/baselines/plan_baseline_t01.json` → PLAN_OK exit 0，冻结未动 |

**无升级项。**
