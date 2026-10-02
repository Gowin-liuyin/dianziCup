# G1 结转闭合批次 · 终态报告（主控直接执行）

背景：两任修复 subagent 均无产出（均已按兜底中断）；批 b 曾正确升级 ④ 路径冲突（scripts/admin_user.py vs 保护清单），主控裁决授权后由主控直接执行。

## 逐项终态
- ① README 容器表述：**closed（前提修正）**——README 中 not_implemented 实为 scripts/dev.py scope 退出码语义（退出码 3，绝不打印 PASS），非 T03 容器表述；核实范围：README 全部 not_implemented 命中行。
- ② T03 C03 容器态回归留痕：**未闭**——test_t03 文件内无预期 marker，未强行插入；下一步：在 tests/integration/test_t03_development_services.py 文件头 docstring 注明容器态回归纳入 CI。
- ③ T04 DTO/空 validator：**部分**——records.py 现有 6 个 DTO（StrictRecord/SourceRecord/DocumentRecord/EvidenceRecord/ClaimRecord/AssessmentRecord，G2-GATE 报"5 DTO"已过时）；空操作 validator 清理 not_run。
- ④ T06 docstring+IntegrityError：**closed**——docstring "而非 traceback" 改为如实（输出可行动错误消息含缺失键名）；IntegrityError 拆两分支（唯一约束 username 冲突 vs 其他完整性错误，各自消息）；提交 201283d；复跑 156/156、mypy 0、ruff 0。
- ⑤ T07 retry_wait 用例：**未闭**——下一步：tests/contract/ 补 1 例（失败→retry_wait 挂起不立即重试→恢复后仅一次）。
- ⑥ T08 重定向判别用例：**未闭**——下一步：tests/contract/ 补 1 例（重定向到未注册 host 抛错不放行）。

## 门禁（201283d 时刻）
uv run pytest tests/unit tests/contract tests/integration -q --cov-fail-under=60 → 156 passed，exit 0；mypy src → 0 issues（46 文件）；ruff → 全过。

## 结论
6 项中 2 项 closed（①前提修正、④）、1 项部分（③）、3 项未闭（②⑤⑥，均为测试/留痕级，已给精确下一步）。G2-GATE 附条件"6 项一次小修批次闭合"未完全满足——如实登记，G3 gate 检查时按未闭项判定，不得视为已满足。
- ② T03 容器态回归留痕：**closed**（G1-CLOSE-c 追加）——tests/integration/test_t03_development_services.py 首个 def test_ 之前插入模块级说明"容器态回归纳入 CI（tests/integration）"（原文件无类似说明，新增 1 行注释）；门禁 uv run ruff format/check + mypy src + pytest tests/unit tests/contract tests/integration -q --cov-fail-under=60 → 158 passed，exit 0（覆盖率 89.99%）。
- ⑤ T07 jobs retry_wait 用例：**closed**（G1-CLOSE-c 追加）——tests/contract/ 新建 test_t07_jobs_outbox.py 1 例（照搬 tests/integration/test_t07_jobs_and_outbox.py 的 migrated_engine/DSN/blocked-skip fixture 风格；原 contract/ 下无该文件）：瞬时失败→schedule_retry_or_fail 返回并写入 JobStatus.RETRY_WAIT（retry_wait 等待态存在、lease_owner 清空、不立即重试）→恢复认领后仅重试一次（观察重试次数 attempt_count-1 == 1，且此后 claim_next_job 为 None）；158 passed，exit 0。
- ⑥ T08 network 重定向用例：**closed**（G1-CLOSE-c 追加）——tests/contract/ 新建 test_t08_network_redirects.py 1 例（照搬 tests/security/test_t08_network_and_sources.py 的 FakeResponse/NetworkPolicy 注入式网关写法；原 contract/ 下无 test_t08_*.py）：已注册 host 302 到未注册 host → 抛 NetworkPolicyViolation（"domain not in allowlist"）且未注册 host 从未被 transport 放行（fetched 仅含已注册起始 URL）；158 passed，exit 0。