# RV-G1B2 · T06/T07 终审快查

日期: 本回合复跑 | 评审范围: T06 安全、T07 jobs/outbox

## 1. 复跑命令与退出码

- `uv run pytest tests/security tests/integration/test_t07_jobs_and_outbox.py -q --cov-fail-under=0` → **退出码 0**, 18 passed (2.49s), coverage TOTAL 46%(未设门槛)。
- `uv run mypy src` → **退出码 0**, "Success: no issues found in 18 source files"。

## 2. 三项断言抽查

1. **SessionRecord 不存明文 token — 通过。** `backend/src/ai_intel/api/authentication.py:67` 的 SessionRecord 仅含 session_id/user_id/expires_at/csrf_token/revoked; session_id 为 `_session_key`(L309-312) 的 sha256(token) 哈希, 明文 session token 只返回给客户端、不入内存/落库。(备注: csrf_token 明文存储, 系双提交比对所需, 非会话凭证。)
2. **cancel 先可见性后权限 — 通过。** `backend/src/ai_intel/workers/jobs.py:129` `cancel_job_with_scope`: job 不存在或跨租户 → `CrossTenantAccessError("resource not found")`(404 语义), 之后才 `scope.requires(WRITE_ASSET)` 权限校验, 顺序正确且不泄露任务参数。
3. **C06 全仓扫描(frontend+logs) — 通过(带一句备注)。** `backend/tests/security/test_t06_authentication_and_scope.py:138` `test_audit_and_sources_carry_no_secret_values_t06_c06` 覆盖审计事件无密码/token + 源码扫描, scan_roots 含 backend/src、scripts、frontend/src、frontend/dist、reports/runs, 后缀过滤含 `.log`/js/ts/tsx/html/json/py, 并对 dev 占位符白名单显式放行。备注: 仓库当前不存在独立 logs/ 目录, 日志以 `.log` 后缀纳入扫描, 属事实覆盖而非缺项。

## 3. 结论

- **T06 = accepted** — 理由: 安全套件全过且 SessionRecord 哈希存储、C06 无秘密扫描(frontend+日志后缀)均实证成立, mypy 0 错误。
- **T07 = accepted** — 理由: T07 集成测试全过, cancel 严格遵循 404 可见性在前、权限在后的顺序, 不泄露跨租户资源存在性。

复跑退出码: pytest **0** (18 passed); mypy **0**。
