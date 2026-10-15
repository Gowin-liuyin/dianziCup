# G-A / R01 行为审查 1 · 定向复核

审查者：`/root/r01_independent_review`，原独立 reviewer，未参与修复实现。本轮开始核验 2026-10-15T00:22:09+08:00；最终证据快照 2026-10-15T00:36:06+08:00，Asia/Shanghai。

**原问题 1、2、3、6 的修复已通过本次定向行为复验；4、5 仍未关闭，整 R01/G-A 不签收。** 本候选尚无历史秘密误报分类实现，依赖升级与 CR-R10 授权/另一 reviewer 的审查也不属于本树。可继续集成这些已验证的修复、开展安全独立的后续准备；不能登记整 R01 前置通过。

固定候选 `fd4f1d42e1ad2e39ff7c80897fd50511c3faf299`，tree=`c566c881b5519bf024694ba8fcbfbc10bd91c013`；checkout=`C:\Users\yinha\.codex\worktrees\recovery-r01-recheck\dianzi`，branch=`codex/recovery-r01-recheck`。定向基线为上轮 `4a17ca7b967a10d6077ba5219984a2d1a74cf320`，原始基线仍为 `f0b154ee0e10100bc9a9d293ebeded13926d0a42`。开始、结束 Git status 均为空；两次 build 改写跟踪的 `frontend/tsconfig.tsbuildinfo` 后，只还原本次生成的该文件，保留各次命令记录，没有修改业务、状态、金标、阈值、分母或 push。

本轮沿用已读取的新版 ponytail-review；重读候选规范、执行地图/R01/R02 范围、状态、相关接口与认证合同、变更代码/调用方、作者质量报告和历史分类证据。固定文档/源树哈希见 [snapshot.json](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_recheck_20261015/snapshot.json)。作者真实资源自检日志只提供线索，不转记为本 reviewer 的 PG/worker 验证。

## 定向结论

| 原问题 | 独立输入与实际结果 | 结论 |
|---|---|---|
| 1，并发限流 | 同客户端 8 个 HTTP 错误密码；用 Event 延迟目录 IO，实际仅 5 次进入查询，结果 5×401 + 3×429 | 原子查询前占位有效；passed，仅单进程边界 |
| 2，非 ASCII CSRF | 正常会话，允许 Origin，原始头字节 FF；403 problem，`/me` 仍 200 | 输入拒绝有效，不撤销正常会话；passed |
| 3，身份/CSRF 混合 | A `/me` 一次读取返回 A 的 CSRF，实际账户只查询一次；换 Cookie B 后以旧 A 快照退出返回 403，B 仍认证。自主前端模拟也无单独 `/csrf` 请求、不注销 B、清除 A 身份并标撤销未确认 | 原混合路径已消除；passed，不声称跨标签 Cookie 变化能被立即感知 |
| 6，404/405 格式 | GET 未知 auth 路由 / GET login：404/405 `application/problem+json`、完整 problem/error/trace_id，405 保留 Allow=POST | passed |
| 4，依赖审计 | 本候选锁文件仍旧 Vitest；新 `npm ci` 报告 1 moderate / 2 critical | open；不评价另 SHA `497740a`，不把未应用升级计入本树 |
| 5，秘密扫描 | 本树全 security 32 passed / 1 failed；首个失败在固定历史 `atomic_secret_scan.log` 的合成 nonce | 误报已确认，分类尚未实施；仍 open/security failed |

实际实现核对：[authentication.py:340](C:/Users/yinha/.codex/worktrees/recovery-r01-recheck/dianzi/backend/src/ai_intel/api/authentication.py:340) 用短锁预留窗口计数，不把锁覆盖到 IO；成功登录不清除其他尝试。现策略计所有有效 Origin 的登录尝试，不再只在失败后记录，这个明确窗口限额没有被本报告说成跨进程共享限流。[authentication.py:313](C:/Users/yinha/.codex/worktrees/recovery-r01-recheck/dianzi/backend/src/ai_intel/api/authentication.py:313) 在 compare_digest 前拒绝非 ASCII。

[auth_routes.py:109](C:/Users/yinha/.codex/worktrees/recovery-r01-recheck/dianzi/backend/src/ai_intel/api/auth_routes.py:109) 从一次 authenticated_session 得到 Principal/SessionRecord，并从同一 Principal 构造权限。`/me` 新增的是已认证会话的 CSRF，不返回 session Cookie 或密码；前端 [client.ts:120](C:/Users/yinha/.codex/worktrees/recovery-r01-recheck/dianzi/frontend/src/api/client.ts:120) 把它放入私有 snapshot，公开 CurrentUser 不携带 nonce。恢复和登录均使用这个 snapshot；登录还核对 user_id。自主例另外验证旧 `/me` 晚到不恢复已退出身份、缺 nonce 不回退单独 CSRF、login 后换账户被拒绝、同一用户会话更换后使用新 snapshot nonce。它仍是 HTTP/组件边界证据，真实浏览器多标签 not_run。

## 实际命令与结果

完整实际 argv/cwd/开始结束秒级 +08:00/wall/exit/count/log 见 [commands.json](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_recheck_20261015/commands.json)，29 条捕获记录。B/F/R 分别是上述候选的 `backend`、`frontend`、仓库根；日志均在本轮新 run 目录，没有改写上轮原始日志。

| cwd / 实际命令 | exit | 数量/结果 | 日志 |
|---|---:|---|---|
| B `uv sync --locked` | 0 | 本 WT 锁定安装 | `backend_sync.log` |
| B `uv run --locked pytest tests/unit -q` | 0 | 57 passed，0 skip；63.83%，保留 unit 60% 门槛 | `backend_unit.log` |
| B `uv run --locked pytest tests/security -q --cov-fail-under=0` | 1 | 32 passed / 1 failed / 0 skip | `backend_security.log` |
| B `uv run --locked ruff check .` / `ruff format --check .` / `mypy src` | 各 0 | lint 正常，85 files formatted，48 source files 无类型错误 | `backend_ruff.log` / `backend_format.log` / `backend_mypy.log` |
| F `npm.cmd ci` | 0 | 安装成功，旧依赖审计告警保留 | `frontend_ci.log` |
| F `npm.cmd run lint` / `npm.cmd run typecheck` / `npm.cmd run build` | 各 0 | 静态检查及构建通过，30 modules | `frontend_lint.log` / `frontend_typecheck.log` / `frontend_build.log` |
| F `npm.cmd run test -- --run` | 0 | 5 files / 39 passed / 0 skip，1 worker | `frontend_test.log` |
| B `uv run --locked python <本 run/backend_recheck_probe.py>` | 0 | 自主 4 个测试通过；真实路由+合成内存账户/受控 IO 延迟 | `backend_recheck_probe.log` |
| F `node <候选 vitest/vitest.mjs> run --config <本 run/vitest.review.config.mjs> --reporter verbose` | 0 | 自主 5 个组件边界测试通过 | `frontend_recheck_probe.log` |
| R `backend\.venv\Scripts\python.exe scripts/dev.py check --scope contract --fixture-only --timeout-seconds 60` | 0 | 108 passed / 1 real_pg deselected / 0 skip；脚本报告 tests=108/errors=0/tool_exit=0 | `script_contract_fixture.log` |
| R 同一 Python `scripts/dev.py check --scope frontend --timeout-seconds 60`，调用者 `PYTHONIOENCODING=gbk` | 0 | lint/typecheck、39 tests、build 全跑，实际 Unicode ✓ 输出成功；脚本 tests=39/failed=0/errors=0/skipped=0 | `script_frontend_legacy_gbk.log` |
| R 同一 Python `<本 run/classification_evidence_probe.py>` | 0 | 2 日志/7 行/11 重叠匹配和 2 来源 blob/hash 符合；主仓上轮 review log 另 1 处已知合成匹配 | `classification_evidence.log` |
| R `git diff --check` | 0 | 无当前 diff；最终 status 空 | `source_boundary.log` / `snapshot.json` |

质量修复 [dev.py:394](C:/Users/yinha/.codex/worktrees/recovery-r01-recheck/dianzi/scripts/dev.py:394) 仅对 TextIOWrapper 设 UTF-8/backslashreplace，不改退出码、测试数量或 skip 判定。离线 contract 包含新增实际 ASCII/GBK CLI 中文 help 例，以及原来的资源 guard、零项/skip/error、超时与连接信息脱敏例；再用 GBK 调用者跑完整 frontend scope，确认不只 help 通过。没有因 fixture-only 的 1 项 deselected 宣称完整 PG 合同通过，也没有把非 unit 的覆盖率 override 当作降低 unit 冻结门槛。作者另行 PG/Compose/任务证据未独立复验，R03 的任务退避/租约缺陷没有在这里验收。

新 CBM 官方 CLI v0.11.0 缓存为 `/tmp/dianzi-cbm-r01-behavior-recheck-fd4f1d4-20261015`，未复用旧图。backend/src 524 nodes/1972 edges，frontend/src 60/171（fast 排除 4 个测试文件，已实际读取/运行），scripts 89/283；source tree listing SHA256=`11fec384696b3363b5ac4207546d2172c686cb8a97c68d09178289bdce2260b7`。help、schema、architecture、authenticated_session、AuthProvider、dev.main trace 与 `rg_callers.log` 均保留。`main` 首次查询返回三个同名函数的 ambiguous，改用工具返回的 qualified name 后才得到目标结果。认证图仍漏掉部分 router closure 边，源码/rg 和真实路由输入已交叉确认，不由图无边判断未接线。

## 历史秘密误报分类 · 独立意见

**这批具体匹配是已证实的测试合成值，不是已证实的真实泄漏。** 候选 `synthetic_occurrences.json` 的两个旧日志 raw SHA256、11 个匹配的模式/行/值，以及 b07596c 中两个测试源码的 Git blob 与 SHA256 均独立匹配；源码由固定 mockResponse/vi.stubGlobal(fetch) 构造 fixture HTTP 响应，nonce 没有生产授权能力。[classification_evidence.json](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_recheck_20261015/classification_evidence.json) 补充了实际 codepoint 匹配起止位置和模式指纹。

| 精确仓库相对路径 | raw SHA256 | 已知匹配 |
|---|---|---:|
| `reports/runs/recovery_r01_frontend_20261014/atomic_secret_scan.log` | `42a2e536b239a8a41b1c998366aa37bc522fd97a83abdf91c63adc3ad9eda71a` | 4 |
| `reports/runs/recovery_r01_frontend_20261014/recheck_rg_before.log` | `58e3053b3d3591ec8f6952efdbcefb353eed68f9fb22d2b4328bc8f164ce345c` | 7 |
| 主仓上轮 `reports/runs/recovery_r01_behavior_review_1_20261014/backend_security.log` | `80205b50cd48993b5c27930ce2fe06930c69a49b910bccf9008cc19afe338c98` | 1 |

最后一项在主仓、未包含于本冻结 WT；它的 traceback 指向 4a17 的 `frontend/src/api/client.test.ts:45` 固定合成响应字面值。它不会因为修改现行源码而从原始失败日志消失。本轮产生的安全失败证据也须保留；后续纳入主仓时，如有相同合成匹配，需要逐项审查新文件字节，不能自动扩展豁免范围。

**建议采用主控所述精确分类方案；不需要另建通用秘密分类框架。** 保留原扫描模式并扫描所有源码/构建/日志，每个命中只有同时满足“明确 repo-relative 路径、不可变 raw 文件 hash、固定模式 ID/指纹、匹配 span 与已核验合成值、来源 commit/blob/fixture 证据”时，记为 reviewed_synthetic；其他命中照常拒绝。表可以只是小型静态审查清单，不要按 nonce 字符串全球豁免、整行豁免、整文件跳过、报告目录跳过或失败改 skip。模式重叠分别登记即可，不需要为两个匹配再抽一套算法。当前清单里的作者旧 WT 绝对路径只是出处，执行时必须规范为已核对的仓库相对路径并确认落在扫描根内；span 的坐标单位应与固定 UTF-8 解码/Python re 一致。

真实授权 secret 的 exact-scan 应独立、优先执行：任一真实值命中即失败，即使误报表声明同值为 fixture 也不允许放行；检查至少包含此前真实 secret/连接串/密码的受控形式，输出只给脱敏路径与状态，不打印值。未知命中不能因为像 fixture 就归入合成。审批新 hash/新范围应来自证据核验，不让运行时输入或作者自动扩大清单。

最小必要回归是：固定历史命中被明确分类；旧日志改一字节、同一行/旁边插入新 credential、新文件复制旧 nonce、表外 span、模式版本不符仍拒绝；真实 exact 值即便与已审合成项冲突也拒绝。**这些分类实现回归现在 not_run，因为本候选还没有实现；本 reviewer 未读取真实秘密，实际授权 secret exact-scan 也 not_run。** 本次 hash/provenance 成功不是扫描通过，更不能替代这两个门。主控方案在这些约束下比修改 regex、改后缀或重写原始日志更小且可审计；没有更简单、同时保留历史证据与全部真实秘密拒绝边界的全局字符串白名单。

## 剩余边界与交付

只对本冻结树的早期 HTTP/前端修复和检查脚本给上述意见。PG 会话/共享限流、事务与重启、worker/scheduler、Compose、浏览器 E2E、外部 live、人工视检、完整私有对象读搜导出/历史有效性均 not_run。本报告不为主控另行实施的新 runtime 或依赖升级候选背书；内存 Session/审计/计数不是 R02 完成证据。

本轮输出仅本报告与 `reports/runs/recovery_r01_behavior_review_1_recheck_20261015/` 内复验脚本、原始日志、命令、历史证据核对、源树快照。没有实施秘密分类。E1/R2 可引用锁安装、静态检查、实际脚本和已修行为；没有计算评分或签整卡 accepted。

**定向复核：关闭原问题 1/2/3/6 的修复验证；4/5 保持 open，本切片整体仍 needs_changes。** 下一步是独立核验分类实现与秘密 exact-scan，再与获批且已经应用的新依赖树、runtime 候选合并复验；阶段验收另行完成。
