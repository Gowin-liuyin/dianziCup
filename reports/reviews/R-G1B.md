# R-G1B · T06 修复态（N1—N4）+ T07 批量收窄审查报告

- 审查人：独立审查 subagent R-G1B（非实现者）｜审查对象基线：git HEAD 60dbbe1，工作树干净
- 本审查未修改任何被审文件；仅写入 reports/reviews/R-G1B.md 与 R-G1B_runs.log
- 复跑命令全文与抽查输出：reports/reviews/R-G1B_runs.log
- **结论：T06 = accepted（附条件）；T07 = accepted（附条件）**（两轨独立结论，详见 §3、§4）

## 0. 审查对象 SHA-256

| 文件 | SHA-256 |
|---|---|
| backend/src/ai_intel/api/authentication.py | 6E89F436EB735FD307BE39286E8F5054C5ED5E161953189AFC906E614C3D63F5 |
| backend/tests/security/test_t06_authentication_and_scope.py | A35CEB394EC18B4D2F4B83A63C8D18821203DD42D1795AE748F248CEB34CFA0F |
| scripts/admin_user.py | 8C85484DD57080A923DEF1DB938ED5A195B8EA1C5C5CD8973BF15AB4782CC517 |
| reports/tasks/T06.md | 06900C14C9529E879501221486981B5241D1C0E5E9FDE0EE49ABD119866BF5C6 |
| backend/migrations/versions/0004_jobs_outbox.py | E16A0711A575190A6C8F9C64C7D7F4D0EB82F0DEE98810394EF158684305D35B |
| backend/src/ai_intel/infrastructure/outbox.py | 45FBC4772DE010FAD3A289BB6EBFE503F7BF025EBDB6CC4E64E56E15F8E7B060 |
| backend/src/ai_intel/workers/jobs.py | 2F336E191E5FEE10E139ACA2D80DCCCD9C52B2D13EF8C107814595A1FBF2E423 |
| backend/src/ai_intel/knowledge/models.py | B1356A49CEC6B46EF249250328AC93AEC882E36A6F1B22BEA9F1999625F028D6 |
| backend/tests/integration/test_t07_jobs_and_outbox.py | 700213CCB3EC53136E69F67DD2030660F472821054D91F50AD21A0DAD57C9B11 |
| reports/tasks/T07.md | CC58F2EF1CAA8B28CAD470818037B559C996C45820524D35F57E282CEC2A4A9E |

## 1. 复跑结果（本回合实测，命令全文见 runs.log）

| 复跑项 | 实测 | 与报告声称 |
|---|---|---|
| cd backend && uv run pytest tests/integration/test_t07_jobs_and_outbox.py -q --cov-fail-under=0 | exit 0，**6 passed**（1.64s，真库） | T07.md 一致（6/6） |
| uv run pytest tests/integration -q | exit 0，**27 passed**（12.84s） | T07.md 一致（27/27） |
| uv run pytest tests/unit -q | exit 0，**34 passed**，cov 69.85%（门槛 60%） | 数量一致；T06.md §6.9 的 cov 73.24% 已过时（见 T06-C4） |
| uv run pytest tests/security -q | exit 0，**12 passed**（1.10s） | T06.md §6.9 一致（12/12） |
| uv run ruff check . / ruff format --check . | 均 exit 0（31 files formatted） | 一致 |
| uv run mypy src | exit 0（18 source files，0 ignore 型掩盖见 §4） | T07.md 一致（18 文件 0） |
| verify_plan --baseline plan_baseline_t01.json | exit 0，**PLAN_OK** | 一致 |
| uv run ruff check ..\scripts / admin_user.py | **exit 1**：目录级 10 errors；admin_user.py 单独 4 errors + format 需重排 | C3 残留（非 CI 门禁） |

## 2. T06 N1—N4 修复态逐项判定

| 项 | 判定 | 实测依据（非仅读码） |
|---|---|---|
| N1 正则盲区消否 | **成立** | 原指名盲区逐一实测命中：`SECRET_KEY = 'supersecretvalue123'`、`secret_key: '…'`、`DB_PASS = 'hunter2hunter2xx'` 双正则均命中；`token='aaaaaaaa'`（8 字符）值捕获命中；jwt 点值命中。测试断言"命中值∉占位集合即失败"保留判别性 |
| N1 报告无夸大 | **成立** | §6.9 M2 行已改为"仍非穷举——纯 base64/无键名赋值形态不保证命中（如实声明，非全覆盖声称）"，与实测一致；残余盲区（`secret key = …` 空格命名形态、<6 字符值）落在其声明的非穷举范围内，不再构成夸大 |
| N2 无明文 token | **成立** | 登录后实测 record.session_id == sha256(token) 且 ≠ token，repr(record) 不含明文 token；会话字典键亦为哈希（前轮已证）——"服务端只存 hash"落地 |
| N3 created_at 后新用户名成功/重复名拒绝 | **成立** | 真库实测（dev PG）：新用户名插入成功且 find_by_username 读回一致（created_at 已写）；重复用户名由 users_username_key 真实拒绝 → ValueError。探测行已清理 0 残留 |
| N4 无 trace_id 拒记 | **成立** | _append_audit('probe_no_trace', {}) → AuditEventError("audit event requires trace_id")；带 trace_id 的敏感键 password 亦被拒（"sensitive field refused…"），双分支实测 |

T06 核心判定四项全部成立。

## 3. T06 结论：**accepted（附条件）**

附带条件（均非安全实质、不阻塞 accepted，建议下批一次小修带掉）：
- **G1B-T06-C1（表述不实，建议尽快）**：scripts/admin_user.py docstring 称缺 DATABASE_URL 时"明确报缺配置而非 traceback"，实测为 MissingDatabaseUrlError 全量 traceback（main 未捕获）。二者择一：改为可读错误（except MissingDatabaseUrlError → stderr + exit 2），或删去"而非 traceback"字样。属 C2 修复批引入的新不实表述。
- **G1B-T06-C2（N3 残留）**：DatabaseUserDirectory.add_precreated_user 仍把一切 IntegrityError 归并为 "username already exists"（实测 user_id 主键冲突也报"已存在"）；且该类仍 0 测试覆盖。建议按异常类型区分 + 至少 1 条单测（或删类改述）。
- **G1B-T06-C3（C3 残留）**：admin_user.py ruff check 4 errors（E501:3、I001×2、UP017:75）+ format --check 失败；不在 CI 门禁（backend 全 0 成立）。
- **G1B-T06-C4（数字过时）**：§6.9 仍写 "integration 17/17"、"unit cov 73.24%"、正文 "security 9/9"；实测 27/27、69.85%、12/12。系过时非夸大，建议刷新。

过程观察（不判违规）：`test_audit_and_sources_carry_no_secret_values_t06_c06` 中敏感字段负例因缺 trace_id 先被第一道守卫拒绝，敏感键分支的命中实为间接（本审查已直接实测该分支成立）；O3（InMemoryUserDirectory 参数标注 + engine: object + type: ignore×2）维持前轮观察。

## 4. T07 逐项判定

| 判定项 | 判定 | 依据 |
|---|---|---|
| C01—C06 断言真实性（真库） | **成立** | 6 用例全部打真实 PostgreSQL（端口探测失败即 skip 并标注 blocked，不以 SQLite 冒充；本回合真跑 6/6）。期望值独立构造：C03 用测试侧 hashlib 独立计算 sha256(b'original')、C02 用行数与 job_id 相等、C04/C05 用错误类型与状态列 |
| 判别性（对简化实现必败） | **成立（抽查）** | C02：简化 enqueue（无幂等）实测第二次插入被 uq_job_idempotency_key 拒 → first==second 必败；且 DB 唯一约束为不变量兜底。C03：覆盖 payload_sha256 的实现必败于独立 sha256 期望。C05：一律重试的实现必败于 outcome=='failed'。C04：lease_owner 判别（旧 worker complete_job 实测 JobLeaseLostError）。C06：错误串实测固定 'resource not found'，断言 'secret'/'tenant-alpha' 不出现 |
| 幂等不变量（重复消息单业务结果 / 409 不覆盖） | **成立** | C02 同键同 payload → 同一 job_id、单行；C03 同键不同 payload → IdempotencyConflictError 且原 payload_sha256 断言不被覆盖 |
| 租约丢失恢复 | **成立** | C04：租约过期后 worker-2 认领同一 job_id（不丢任务），原 worker 提交被拒 |
| 404 无泄露 | **成立** | 读取/取消先可见性后权限（顺序已修复），跨租户与不存在同串 'resource not found'，无 tenant/payload 字样 |
| 无 Any/cast/吞异常 | **成立** | 4 个 T07 文件扫描 0 命中（Any/cast/except:/pragma/type:ignore）；异常均显式抛出分类（IdempotencyConflictError/JobLeaseLostError/LookupError/ValueError） |
| 报告诚实 | **成立** | §5 not_run 如实（真实 Celery/Redis、进程级 kill 崩溃注入、并发压测均未做且已声明）；§4 数字（6/6、27/27、34/34、ruff/mypy 18 文件 0）全部复现一致 |

迁移/模型一致性：0004 与 models.py 的 job_runs/outbox_events 列、CHECK、FK 一致；users CHECK 已对齐 0003（前轮 O2 消除）。残留漂移：idempotency 唯一约束命名（迁移 uq_job_idempotency_key vs 模型 unique=True 自动名），仅影响 create_all 型库的约束名（观察项）。

## 5. T07 结论：**accepted（附条件）**

附带条件（不阻塞 accepted，接入 Celery/HTTP 前应处理）：
- **G1B-T07-C1（并发语义未闭环）**：enqueue_job 的幂等检查-插入存在竞态窗口，同键并发会以 IntegrityError 冒出而非复用/409 语义（库唯一约束保证不重复，但错误语义不符）；relay_pending_events 并发双发无 published_at IS NULL 守卫。T07.md §5 已声明并发压测 not_run——要求在并发验证补做前不宣称并发安全。
- **G1B-T07-C2（retry_wait 路径无测试）**：jobs.py 113-126（非永久错误进 retry_wait、attempt 耗尽转 failed）已实现但无用例（jobs.py cov 71%），任务卡 §4.4"有限重试"建议补 1 条负例。
- **G1B-T07-C3（C01 模拟语义）**："队列不可用"以不投递模拟，未做显式故障注入；报告 §5"崩溃注入为逻辑模拟"部分覆盖该口径，建议明示 C01 同为逻辑模拟。
- **G1B-T07-C4（约束命名漂移）**：见 §4 观察项，建议模型显式命名 uq_job_idempotency_key 对齐迁移。

## 6. not_run（如实，非本次失败）

真实浏览器 CSRF 流、真实 IdP/LDAP、生产 HTTPS 端到端、渗透测试（继承 T06.md §5）；真实 Celery/Redis 队列、进程级 kill 崩溃注入、并发压测（继承 T07.md §5，与报告声明一致）。

## 7. 总结

T06 四项必改（N1—N4）经实测全部消否：命名形态正则盲区已补且报告如实收敛、会话仅存哈希键、created_at 修复后新用户名成功/重复名拒绝、无 trace_id 拒记成立——**accepted（附条件）**，条件为 C2 文档不实表述、N3 错误归并+0 测试、C3 lint 残留、§6.9 数字过时，均小改。

T07 六项验收在真库上断言真实、判别性抽查对简化实现必败、幂等/租约/404 三不变量成立、无 Any/cast/吞异常、报告诚实——**accepted（附条件）**，条件为并发语义未闭环、retry_wait 无用例、C01 模拟口径、约束命名漂移，均不阻塞当前 G1 内部推进。
