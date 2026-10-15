# G-A / R01 原问题 5、登录占位与 C06 状态 · 最终定向复核

审查者：`/root/r01_independent_review`，原独立 reviewer，未参与实现。开始：2026-10-15T01:25:36+08:00；最终源树快照：2026-10-15T01:51:48+08:00，Asia/Shanghai。

**本轮原问题 5 的技术修复、成功登录占位回归及 C06 前端状态修复通过定向复核，可继续集成。原问题 4 仍 open；整 R01、整 T06/T40 和 G-A 不签收。** 没有新确认阻断缺陷。真实秘密扫描与真实认证浏览器证据由主控执行，本 reviewer 只核对，绝不登记为自主实跑。

固定候选 `d30eeab1d723080decea5f64a992b909a0d834c2`，tree=`86162477cdeea61cfb94b501bc6d8e427efaf1bb`，分支 `codex/recovery-r01-recheck-final`，checkout=`C:\Users\yinha\.codex\worktrees\recovery-r01-recheck-final\dianzi`；定向基线 `fd4f1d42e1ad2e39ff7c80897fd50511c3faf299`。初始/最终 Git status 均为空；只还原本次 build 生成的跟踪文件 `frontend/tsconfig.tsbuildinfo`。未改候选源码、HEAD、分类表、状态、阈值、金标、原始历史日志，未 push。输出仅本报告和新 `reports/runs/recovery_r01_behavior_review_1_final_recheck_20261015/`；临时合成夹具在系统临时目录创建并清理，没有把 node_modules 或 replay 树保存到报告目录。

## 原问题 5：分类边界与证据

[security_scan.py:186](C:/Users/yinha/.codex/worktrees/recovery-r01-recheck-final/dianzi/scripts/security_scan.py:186) 保留原两套正则及 16/6 长度、五个扫描根和七种后缀。分类只匹配 path/raw SHA256/pattern ID/start/end/value 的完整 tuple，既不免检整行，也不免检整文件或目录；表外匹配仍拒绝。原始字节用于 SHA256 和 exact 检测；正则坐标使用 UTF-8 errors=ignore 解码、CRLF/CR 统一为 LF 后的 Unicode code point，左闭右开。新自主中文+CRLF 输入确认 code point 坐标可分类，错误字节坐标不能分类。

36 条记录、7 个目标路径的原始字节 hash、具体 span/value、来源 Git blob/源 hash、源行字面值及 review report hash 全部独立吻合，分类表 raw SHA256=`ab87ee5b9f7b9d8b5dc227a789644326659510049dbf7dd2e705a03646d839ac`。[classification_provenance.json](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_final_recheck_20261015/classification_provenance.json) 保留逐条核对：19 条目标位于候选，17 条是主仓保留的历史证据，部分旧 review 文件未随 worktree checkout 出现。第一次只查候选因此 FileNotFoundError 的日志保留，随后直接只读主仓的同相对路径并核对固定 hash，没有复制或改写历史文件。7 个命中目标及其来源已核对，不宣称重新逐字节核验全部非命中历史目录。

[loader:110](C:/Users/yinha/.codex/worktrees/recovery-r01-recheck-final/dianzi/scripts/security_scan.py:110) 校验路径 containment、hash 格式、模式版本/指纹、严格整数 span、fixture 类别和来源描述格式；这些是格式校验，**不是运行时重新读取 Git/report 证明其内容**。内容来源由本次独立核对建立，后续分类表扩展仍须独立审查。当前固定来源都证明合成输入，没有把 fixture 当 live，也没有把未知命中归为已知秘密或合成值。

自主 8 个分类测试方法包含实际参数负例：旧字节变动、同一行/旁边插入新凭据、复制到新文件、表外 span、六种路径逃逸/离开允许根、模式版本/指纹/类型与 live 来源拒绝、每个原根中的未知凭据、中文/CRLF 坐标，以及 CLI exact 优先、无回显、缺 exact 输入必须 not_run。测试输入和期望独立构造，没有修改生产分类表。原模式/根/后缀也与冻结规范逐字断言。详见 [independent_security_and_login_probe.log](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_final_recheck_20261015/independent_security_and_login_probe.log)。这是合成边界测试，不是实际秘密调用。

[exact 检测:209](C:/Users/yinha/.codex/worktrees/recovery-r01-recheck-final/dianzi/scripts/security_scan.py:209) 先检测真实值原始字节，再进行正则分类；命中 exact_secret_match 不会被随后 safe 分类抵消。自主把同一个合成值同时设为“已审 fixture”和 CLI exact 输入，得到 exit 1/completed 且输出无该值；缺输入得到 exit 2/not_run。输出仅路径、模式、类别。

主控的真实执行 receipt：2026-10-15T01:22:13–01:22:15+08:00，candidate=d30eeab，6 个受控秘密引用（5 个 API key + 测试密码），exit 0，exact_scan=completed，credential_values_in_output=false；读取的是脱敏结果/schema/命令 receipt，没有读取 DPAPI 密文内容或明文值。[controller_receipts.json](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_final_recheck_20261015/controller_receipts.json) 固定了原 receipt 文件 hash。**本 reviewer 实际秘密 exact-scan 为 not_run；主控的 completed 单列，不能改写执行者。** 本候选完整 security 63 项/0 失败/0 skip，原 C06 已不再因这些历史合成匹配失败。

## 成功占位与 C06 行为

[authentication.py:232](C:/Users/yinha/.codex/worktrees/recovery-r01-recheck-final/dianzi/backend/src/ai_intel/api/authentication.py:232) 为每次尝试预留 UUID；[成功路径:255](C:/Users/yinha/.codex/worktrees/recovery-r01-recheck-final/dianzi/backend/src/ai_intel/api/authentication.py:255) 只释放自己的 UUID，不清空其他失败/在途尝试。自主真实 router + 内存 fixture 输入结果：

- 同客户端 6 次登录/退出均 200，不再把成功次数累积成 15 分钟锁定。
- 4 次失败→成功→第 5 次失败→下一次，结果 `[401,401,401,401,200,401,429]`，失败 cap 仍为 5。
- 8 次受控慢目录并发，只有 5 次进入查询，5×401 + 3×429。
- 4 次失败仍在途时成功登录，只释放自身；第 5 个失败仍可进入，第 6 个被 429，原 4 个最终均 401。

4 个登录方法和 8 个分类方法共 12 个 unittest 方法全部通过；参数子例不冒充额外独立总数。尚未证明跨进程限流、PG Session durability，仍属 R02 边界。

前端 fixture 42 项通过；新 worker `not_observed_or_stale` 明确显示“待观测 / 已过期”，scheduler unavailable 显示“不可用”，没有标为 ready。末次键盘修复 [r01_auth.spec.ts:49](C:/Users/yinha/.codex/worktrees/recovery-r01-recheck-final/dianzi/frontend/e2e/r01_auth.spec.ts:49) 等待刷新按钮 enabled 再真实 Tab，没有 sleep 或放宽焦点断言，另两认证/掉线用例未弱化。

自主浏览器使用此 WT 的 Vite，专用 loopback 25179，Chrome Headless **156.0.8078.4**，新空 browser context、无认证密码/会话输入；HTTP 路由受控延迟，不接主控 API。两个实际浏览器例通过：慢健康响应期间 disabled 刷新按钮被 Tab 跳过；释放响应、按钮 enabled 后 native Tab 正确聚焦；worker/scheduler 文案保留失败/过期语义，无“全部依赖就绪”，访客无私有权限，390px 无水平溢出、浏览器存储为空。trace/video/screenshots 全 off。[visitor_browser_receipt.json](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_final_recheck_20261015/visitor_browser_receipt.json) 明确模式。初次默认浏览器缓存缺 headless 1248，0 UI 例/exit 1 保留；仅改用已有私有缓存后复跑成功，没有下载或修改浏览器环境。

主控真实账号 3 个 E2E：2026-10-15T01:23:06–01:23:11+08:00，XML=3/0 failure/0 error/0 skip、exit 0，frontend=9334fad、backend=b504c23，trace/video/failure screenshot off，凭据为主控受控注入。这里只核对 receipt/XML/stdout 与 source：本树 frontend/src/e2e/tests 与 9334fad 无差异，auth 两文件与 b504c23 无差异；前端 package/lock 有主控中央依赖接入差异，不能声称整棵树相同。真实认证 3 例仍**不是我的自主实跑**，不能替代当前树的完整独立认证浏览器复跑。原失败日志没有删除或重写。

## 实际复跑与范围

全部实际 argv/cwd/开始结束秒级 +08:00/wall/exit/count/log 在 [commands.json](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_final_recheck_20261015/commands.json)，28 条捕获记录。B/F/R 是上述候选 backend/frontend/根目录；下列日志都在本轮新 run 目录。

| cwd / 命令 | exit | 真实结果 | 日志 |
|---|---:|---|---|
| B `uv sync --locked` | 0 | 本 WT 安装 | `backend_sync.log` |
| B `uv run --locked pytest tests/unit -q` | 0 | **59 passed，cov 64.00%，保留 60% unit 门槛** | `backend_unit.log` |
| B `uv run --locked pytest tests/security -q --cov-fail-under=0` | 0 | **63 passed，0 skip** | `backend_security.log` |
| B `uv run --locked pytest tests/contract -q -m "not real_pg" --cov-fail-under=0` | 0 | 108 passed，1 real_pg deselected，0 skip，非完整 PG 合同 | `backend_contract_fixture.log` |
| B `uv run --locked ruff check .` / `ruff format --check .` / `mypy src` | 各 0 | lint 正常；91 formatted；50 source files 无类型错误 | `backend_ruff.log` / `backend_format.log` / `backend_mypy.log` |
| F `npm.cmd ci` | 0 | 安装成功，仍报告 1 moderate + 2 critical | `frontend_ci.log` |
| F `npm.cmd run lint` / `typecheck` / `build` | 各 0 | 静态/构建通过 | `frontend_lint.log` / `frontend_typecheck.log` / `frontend_build.log` |
| F `npm.cmd run test -- --run` | 0 | 42 passed / 5 files / 0 skip | `frontend_test.log` |
| B `uv run --locked python <本 run/independent_security_and_login_probe.py>` | 0 | 自主 12 方法通过，无真实 PG | `independent_security_and_login_probe.log` |
| R 本 WT Python `<本 run/verify_classification_provenance.py>` | 首次 1，后 0 | 初次缺历史 WT 文件；随后只读主仓 hash-pinned 原件，36 条/7 路径证据全匹配 | `classification_provenance*.log` |
| F `node <本 run/visitor_browser_probe.mjs>` | 首次 1，后 0 | 初次缺默认 browser；已有 cache 下 2 访客 UI 例通过，受控 HTTP | `visitor_browser_probe*.log` |
| R `git diff --quiet` 相关源版本 / `git diff --check` | 源匹配 0；含 package 的比较 1；diff 检查 0 | 差异查明为 package/lock；最终 status 空 | `*_matches_root_browser_version.log` / `source_boundary.log` |

本候选的新全 unit 是 59/cov64.00%，没有拿主控其他组合命令的 75/cov69.89% 套用，也没有合计重复运行数量。非 unit 覆盖 override 沿用原约定，unit 冻结值未改。

CBM 新缓存 `/tmp/dianzi-cbm-r01-final-d30eeab-20261015`，独立三个项目：backend/src 539 nodes/2038 edges，frontend/src 60/171，scripts 110/366。schema 和 scan_repository/_reserve_login_attempt trace 与 [rg_callers.log](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_final_recheck_20261015/rg_callers.log) 交叉核对，测试调用方以源码及实际执行补核。源树 blob 清单 SHA256=`9cda104cbf38a92cdac655af97d8dc0f5b20b477881add356fe7d57fbd4d9fbe`；[snapshot.json](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_final_recheck_20261015/snapshot.json) 绑定本 SHA/tree，不复用旧图。

unit、离线 contract、此切片 security、frontend fixture、访客自动浏览器的范围上述明确；真实 PG/Redis/search/worker/跨进程/持久化 integration、真实认证 E2E 自主复跑、外部 provider/source live、人工视检均 not_run by reviewer。主控真实 secret/auth receipt 独立列示，不改成 reviewer passed。TLS/Linux/tmpfs 部署、f497865 和后续 quality 集成不在 d30 的本轮审查意见中。

**结论：原问题 5、成功占位和 C06 状态这次修复可继续技术集成；原 1/2/3/6 的既有定向意见不扩张，原 4 继续 open。** CR-R10 在本候选仍 proposed，Vitest 4 未应用；单独 runtime 审查和阶段集成仍需完成。没有用源码存在、receipt 阅读或 fixture 通过签整 R01/G-A，也没有折算评分。下一步是获批依赖树与 runtime 各自复核后，冻结集成树再做阶段检查。
