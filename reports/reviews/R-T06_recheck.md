# R-T06-RECHECK · T06 修复批（M1—M6）定向复核报告

- 复核人：独立复核 subagent R-T06-RECHECK（首轮审查者立场，非修复作者）｜结论：**needs_changes（仅 4 项小修；安全实质已达标）**
- 复核范围：M1—M6 修复后定向复核；T05/T07 轨道文件不属本次复核（integration 差额来源已注明）
- 本复核未修改任何被审文件；仅写入 reports/reviews/R-T06_recheck.md 与 R-T06_recheck_runs.log
- 运行日志与抽样命令全文：reports/reviews/R-T06_recheck_runs.log

## 0. 复核对象 SHA-256

| 文件 | SHA-256 |
|---|---|
| backend/src/ai_intel/domain/access.py | A9CCD105A8C29CFACA681834A8A0A38525CC79F4B24D50242362B00A5378EDD6 |
| backend/src/ai_intel/api/authentication.py | 3AC97CF2AC680328C81426DDEBF82E1DA35D7DDBCE4675844AFCD431FA66DF51 |
| backend/migrations/versions/0003_users.py | 73E617F677FEF5E301491D8C8B0CA2DAA5E034008E45E5A35C8BDC40BEE6F428 |
| backend/src/ai_intel/knowledge/models.py（users 表） | 72628CE919DCB992B36C79A17E08BE958E89DAEC995FC0D321FAA88CACA0A276 |
| scripts/admin_user.py | 689E0E70EA7E745FFEFAF7D1EC7662E1A8801C1FADD822CBEB11963312D92CDF |
| backend/tests/security/test_t06_authentication_and_scope.py | 62862662B341A058FA947882C1B8B463D1AC8660AF9F9EF6695E51170E466CE8 |
| reports/tasks/T06.md | 544557268496168358D511D12B18631DB98A57DF3A2D4DD13D0384E9DAC45E3D |

git status：仅 progress/context_handoff.md 修改（非本次复核写入）；contracts/ 冻结文件未改动。

## 1. 复跑结果（命令全文与退出码见 R-T06_recheck_runs.log）

| 复跑项 | 实测 | 与 T06.md §6.9 声称 |
|---|---|---|
| cd backend && uv run pytest tests/security -q --cov-fail-under=0 | exit 0，**12 passed**（1.13s） | 一致（12/12） |
| uv run pytest tests/unit -q | exit 0，**34 passed**，cov **73.24%**（门槛 60%） | 一致（精确吻合） |
| uv run pytest tests/integration -q --cov-fail-under=0 | exit 0，**21 passed**（12.21s） | 声称 17/17；差额 +4 来自 T05/T03 轨道文件（见 O1），全部通过无回归 |
| uv run ruff check .（backend） | exit 0 | 一致 |
| uv run ruff format --check .（backend） | exit 0（27 files already formatted） | 一致；access.py:48 已重排（M1 主体修复成立） |
| uv run mypy src | exit 0（16 source files） | 一致 |
| uv run ruff check/format --check ..\scripts（非 CI 门禁） | **exit 1**：35 errors（admin_user.py 2 处为修复批引入）+3 文件需重排 | 首轮"仅 T06 文件 format 全 0"口径不复现（见 C3） |
| uv run python ..\scripts\verify_plan.py --baseline ..\contracts\baselines\plan_baseline_t01.json | exit 0，**PLAN_OK**（含 source_hashes 对比） | 一致 |

CI 门禁（.github/workflows/ci.yml）仅覆盖 backend 的 ruff check/format/mypy/tests/unit——backend 全 0 成立。

## 2. M1—M6 逐项判定

| 项 | 判定 | 依据 |
|---|---|---|
| M1 format 全 0 | **通过（附条件 C3）** | backend 全 0（access.py:48 已重排）；scripts/admin_user.py（复核对象）ruff/format 未过且为修复批引入，但不在 CI 门禁 |
| M2 扫描面+值捕获+占位豁免+报告无夸大 | **不通过（N1）** | 扫描面 ✓（frontend/src 3 文件、frontend/dist 2 文件、reports/runs 21 文件，7 类后缀，空根跳过已核实非空）；值捕获正则 ✓（JWT 点值/标点密码实测命中）；占位豁免 ✓（命中值∉占位集合即断言失败）；**报告无夸大 ✗**："SECRET_KEY 语义词覆盖"实测不成立，且原 M2 指名盲区未消 |
| M3 与 production 联动（断言非回显） | **通过（附条件 C1）** | cookie_secure_for_environment("production") is True / ("development") is False 为行为断言非回显；无强制机制与误配负例 |
| M4 users 表实建 / CLI 持久化 / 重复名真实拒绝 | **通过（附条件 C2、N3）** | 三项均实测成立（见 §4）；DatabaseUserDirectory 组件损坏、调用文档缺 DATABASE_URL |
| M5 viewer / 会话哈希键 / permission_version / 伪造身份审计 / 角色权限区分 | **通过（附条件 N2、N4）** | 五子项全部实测存在（见 §5）；"不存明文"与"审计强制 trace_id"两处表述不实 |
| M6 filter_visible_rows | **通过** | 实现 + 测试断言 filter_visible_rows(scope, rows) == [0, 1, 3]，公共/私有按可见性分离 |

## 3. 发现清单

### 必须修复（needs_changes 依据，均为小改动）
- **N1（M2）报告夸大 + 指名盲区未消**：§6.9 称"正则增强（…JWT/SECRET_KEY 语义词覆盖）"。实测 `SECRET_KEY = 'supersecretvalue123'`、`secret_key: '…'` 对 secret_pattern 与 secret_value_pattern **均不命中**（alternation 中 "secret" 后须紧跟 \s*[:=]，遇 "_key" 即失败）；`DB_PASS = 'hunter2hunter2xx'` 与 <8 字符值（`token='aaaaaaaa'`）同样盲区。原 M2 明确指名的 SECRET_KEY 命名盲区依旧存在，而报告声称已覆盖——恰为 M2 验收项"报告无夸大"不成立。修复：正则按标识符语义词（secret[_-]?key|db[_-]?pass|pass 等）匹配命名形态并补负例自证，或如实改述 §6.9 并将该能力标 partial。
- **N2（M5 残留）"不存明文"不成立**：会话键=sha256(token) ✓（实测 key=sha256 且不含明文），但 SessionRecord.session_id 仍保存**明文 token**（实测 record.session_id == token）。合同"服务端保存hash"仍部分偏离，§6.9"（不存明文）"表述不实。修复：session_id 存哈希或删除该字段 + 负例断言记录内无明文。
- **N3（M4 残留）DatabaseUserDirectory 功能性损坏且误导报错**：add_precreated_user 未写 created_at（列 NOT NULL 无默认），任意插入都触发 IntegrityError 并被统一改写为 ValueError("username already exists")——**实测全新用户名插入也报"已存在"**；且该类 0 覆盖、无任何接线（服务构造参数标注 InMemoryUserDirectory，mypy 下无法接入）。修复：补 created_at、按异常类型区分错误、补至少 1 条单测；或删除该类并改述 §6.9。
- **N4（报告诚实）"审计强制 trace_id"不成立**：§6.9 M5 行称"审计强制 trace_id"，但 _append_audit 无 trace_id 校验（实测 _append_audit("probe_no_trace", {}) 成功写入无 trace_id 事件）。修复：_append_audit 拒绝缺 trace_id 的事件，或改述为"现有调用点均附 trace_id"。

### 条件/建议（不阻塞其余项判定，建议同批处理）
- **C1（M3）production 无强制**：helper 与断言达标，但 settings.py/服务构造期均无 production→secure 校验，production 传 cookie_secure=False 不会被拒，也无误配负例。建议构造期断言或 settings 校验 + 负例（原 M3"强制"语义仍为约定式）。
- **C2（M4）调用文档不完整**：docstring 调用方式未提 DATABASE_URL；仓库无 .env，按文档运行直接 MissingDatabaseUrlError traceback（实测）。建议 docstring 补 DATABASE_URL 要求并改为可读错误。
- **C3（M1 范围）scripts/admin_user.py 未过 ruff**：E501:3（修复批新增的调用方式行）、UP017:69（timezone.utc）与 format --check:80 失败，均为 M4 修复批引入；CI 门禁仅 backend 故不影响门禁。建议 ruff format + 两处修正。
- **C4（M4）错误输出回显 SQL 参数**：重复名报错的 stderr 含完整 SQL 参数（含 password_hash，无明文）。建议不回显参数。

### 过程观察（不判违规）
- **O1** integration 21/21 vs 声称 17/17：+4 来自 tests/integration/test_t05_persistence_and_raw_store.py（T05 轨道，不属本次复核）与 test_t03 文件；全部通过。
- **O2** models.py users 表缺迁移 0003 的 ck_users_role / ck_users_tenant_admin_requires_tenant（模型与迁移漂移；create_all 型库不受约束；实库约束齐全）。
- **O3** AuthenticationSessionService.__init__ 参数标注 InMemoryUserDirectory，DatabaseUserDirectory 无法在 mypy 下接入；后者用 engine: object + 2 处 type: ignore[attr-defined]（AGENTS §4 不建议以 ignore 掩盖合同不一致）。
- **O4** C03 的 forged_request_body 仍未进入 HTTP 层（/auth 路由未落地），record_identity_spoof_attempt 为手工入口——首轮 C3 结构性判断不变，待 HTTP 层补真实负例。
- **O5** permission_version 为模块常量默认注入（PERMISSION_VERSION=1），非按租户/策略版本下发；当前可接受，落地 /auth 时再核。

## 4. M4 实测记录（dev PostgreSQL 127.0.0.1:5432/ai_intel；探测行已清理，users 行数回到 0）

1. **users 表实建 ✓**：6 列（user_id/username/password_hash/tenant_id/role/created_at），users_pkey、users_username_key(unique)、ck_users_role、ck_users_tenant_admin_requires_tenant 齐全，alembic_version=0003_users。
2. **CLI 持久化 ✓**：首次创建 exit 0（created user_id=d5e5f318-…）；全新进程 find_by_username 读回 analyst/rt06-probe/$argon2id$v= 前缀——跨进程持久、只存哈希。
3. **重复名真实拒绝 ✓（实测两次创建）**：二次创建 exit 1，`ERROR username already exists: (psycopg.errors.UniqueViolation) … users_username_key`——真实唯一键拒绝（首轮 M4"分支不可达"已消除）。
4. **✗ N3**：DatabaseUserDirectory 新用户名插入也报 ValueError("username already exists")（created_at 缺失被误译）。
5. **✗ C2**：无 DATABASE_URL 时按 docstring 运行 → MissingDatabaseUrlError traceback。

## 5. M5 抽样实测（非仅读代码）

| 子项 | 实测 | 判定 |
|---|---|---|
| viewer 角色 | Role.VIEWER + 权限表 {read:public} + 测试 | ✓ |
| 会话哈希键 | key == sha256(token)、key 不含明文 | ✓（但记录存明文，N2） |
| permission_version | AccessScope.permission_version 字段 + 测试 | ✓ |
| 伪造身份审计 | identity_spoof_attempt 仅记字段名+trace_id，测试断言无值泄露 | ✓ |
| 角色权限区分 | manage:public_sources 仅 system_admin，tenant_admin ⊂ system_admin 严格子集断言 | ✓ |

## 6. 结论

**needs_changes（小改批）**

M4 三项验收点（users 表实建/CLI 持久化/重复名真实拒绝）经实测全部成立，M5 五子项、M6、M3 联动口径、M2 扫描面/值捕获/占位豁免、M1 backend 全 0 均达标，安全实质较首轮显著改进。但按逐项口径仍有 4 项必改：M2 的"报告无夸大"不成立且指名盲区（SECRET_KEY 命名）未消（N1）；"不存明文"不实（N2）；DatabaseUserDirectory 损坏且误导报错（N3）；"审计强制 trace_id"不实（N4）。三项均为报告表述/小实现修正，预计一次小改批即可转 accepted。

未运行项（not_run）：真实浏览器 CSRF 流、真实 IdP/LDAP、生产 HTTPS 端到端、渗透测试（继承 T06.md §5，非本次复核范围）。
