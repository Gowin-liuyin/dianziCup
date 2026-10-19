# G-E R18 API-key 凭据切片独立复核 1 / expiry fix2

What this change does: fix2 在 key/users 锁取得后，以可信 server now 加真实 monotonic elapsed 重新校验 key 时间状态；配额桶锁等待后再次检查过期和分钟，仅在最终有效桶加一次。公共签名、原 20 输入与断言、metadata、旧 cookie 实现和生产接口保持原范围。

**有界结论：Ship，仅 API-key credential seam 与 fix1/fix2 范围。** 原 Must fix 1（CI 资源入口）与 Must fix 2（真实锁等待跨 expiry 仍授权）闭合；没有新增确定 Must/Should finding。本 reviewer 不写 accepted，不签整 R18、整 T 卡或 G-E，不修改 progress，不 commit/push。

## 冻结、合同与保护

全新树 `D:/wt/r18-api-key-review1-fix2`，分支 `codex/r18-api-key-review1-fix2`，实际 HEAD/material `34af66115a80c3cbedcb10a6d5a349a8af4d4822`。source 为 `8e0485231bf9367d5b4b3a79802bdf346b1fb745`，实际 tree `de786d07134564ec059c88ac1515ba58a1aea6f3`。source 仅 credentials.py 和两个新增直属测试；reviewer 仅写本报告与 `reports/runs/recovery_r18_api_key_review1_fix2_20261016/`。未再委派，未访问 holdout。

沿用已读的 AGENTS、Ponytail 5.2 review、R18/T40/T41/T42 及相关合同，本次重新核 fix2 报告、冻结状态/执行索引、source/tests 和主控正式 CR。主控 `CR-R18_api_key_credential_seam.md` 的 **2026-10-16T11:02:05+08:00 锁后时间修订**实际读取并保存 `approved_cr_snapshot.md`：保持公共签名/可信 aware now/DST语义，用真实 monotonic 推进锁等待，重验 key/user/rate，最终分钟只消费一次；legacy cookie 同根因留 R20 后续缺口，未扩大本包。

`frozen_audit` 独立确认原 88、CI fix1 100、fix2 85 项材料的 raw archive 与 Git blob hash，13 保护文件、11 锁调用文件（credentials 为本次明确允许变更）、原 PG20 全业务 test 至 EOF 字节、公开函数签名和前 review 所有材料。前 reviewer manifest `4705e2c71eeaf100f2fe53422359e80ae5e628eb584b9bd7567956b22c0a713f` 与原探针精确字节保持。fix2 manifest Git SHA256 为 `54594f79a57e33f1948fbbc2b292dec88084ced8f5567517b6f341cf94da19ff`。工作树 CRLF/raw 与 Git text filter 的口径分别记在 `new_material_audit.json`；没有 trim、修改 root attrs、旧日志、金标、门槛或分母。作者局部 run binary attrs 经审查只用于新 `.log/.xml/zip` 保留原字节。

## 源码与锁检查

`credentials.py:180–249` 去除锁前时间/resource/revoked SQL 筛选，先按唯一 token hash 对 key/users 取得 SHARE 锁，随后验证锁住的 resource、issued、expiry、revoked，并以当前 owner role/tenant 与 key scopes 交集返回 scope。owner 不存在的 JOIN 仍返回拒绝。`_advance_server_time` 推进服务端可信时点，不引入请求体或数据库事务开始时间作为第二权威；入口先转 UTC，因此 DST 的绝对时间语义保持。

`credentials.py:278–315` 从 consume 入口记录总 elapsed，key/user 锁后及桶锁后都验证；跨分钟只重取递增的新分钟桶，最终仅一个 UPDATE。被锁 key/users 行不能在中途改变 role/tenant/revoked/scopes，桶 FOR UPDATE 保证 count 无 lost update。计数与业务事务同提交/回滚；旧 full 桶不拒绝下一分钟。锁窗口按单调推进顺序前进，未建立反向桶锁路径；没有增加锁等级或进程内计数。

正常 principal 仍一条锁查询，正常 consume 仍 key 查询/插桶/锁桶/加一四个语句；时间校验为 Python 标准库调用。跨分钟仅增加相应新桶读取，未增加网络/模型 IO。此次没有吞吐/延迟 benchmark，不能把源码观察当性能指标通过。

CBM0.11 新索引 `dianzi-r18-review1-fix2-34af-20261016`：1862 nodes/10144 edges，architecture/schema/consume trace 均有 receipt。fast 排除 assets/cache；rg 补核全部实际 source 调用，私有 RowMapping 仅 principal/consume 两 caller 使用。既有 answering/assessment/inventory/routes 仍走旧 session 锁，图不作为公开接线成功证据。

## 亲跑证据

Python `D:/dianzi/backend/.venv/Scripts/python.exe`；普通 cwd 为本 fresh tree/backend。每个 checks receipt 有完整 argv、真实 +08:00 起止、退出码、HEAD、日志 SHA/JUnit 数；PG receipt 另记 source hash/不变性、runner argv/source root、actual owned resource/清理和 exact secrets。`-o addopts=''` 只关闭局部测试触发的全包 coverage 门，不代表全仓 coverage 通过。

| label | 真实范围 | 结果 |
|---|---|---|
| offline57 | 原49 + 新8 unit，同条 pytest | exit0；57 passed，0 fail/error/skip；unit34、metadata/fixture contract17、pure security6 |
| ubuntu_fixture15 | 真实 WSL Ubuntu3.12，原合法 CI marker/25436 fixture入口 | exit0；15 passed，0 fail/error/skip；合成 PG IO，不是 Linux PG execution |
| ubuntu_pg24_collect | WSL 原20 + 新4 collect-only | exit0；24 collected，非 PG execution |
| microsecond_boundary | reviewer 独立一微秒 expiry/受控 monotonic 浮点边界，合成IO unit | exit0；2 passed；0.4μs 保持有效，1μs 到期拒绝 |
| original_pg20 | 真实隔离 PG，原文件/输入/断言不改 | exit0；20 passed，0 fail/error/skip；11:07:50.242750–11:08:02.415414+08 |
| new_pg4 | 真实隔离 PG，新 key/bucket 时间与并发边界 | exit0；4 passed，0 fail/error/skip；11:08:03.609311–11:08:10.682687+08 |
| same_probe_recheck | 原 4705 独立脚本精确原字节、真实三秒 expiry/Lock | exit0；status passed；11:09:46.298916–11:09:51.292482+08；各原断言执行 |
| cookie_regression | 原 T06 authentication/scope + R02 input | exit1；23 passed/1 failed，0 error/skip，扫描红保留 |
| scanner_diagnosis | 解 DPAPI 前诊断原 scanner findings | 诊断 exit0；scanner 仍 failed，18 shapes=原14+原字节 probe 两份各2 |
| quality / format / mypy | credentials + 两新测试精确范围 | 均 exit0；mypy3 files no issues |
| frozen_audit | 固定 source/material allowlist | exit0；88/100/85、13/11、20字节/公开签名/4705 probe符合 |

原三秒探针本轮传入 now **2026-10-16T11:09:48.034795+08:00**，expires **11:09:51.001975**，实际 Lock 后于 **11:09:51.107533** 返回 **denied**，fresh call也denied。前轮同原输入形状的 authorized 红/所有 raw receipt 均受 4705 hash 保护，没有改三秒、系统时钟或断言。该脚本同时保留并通过原三连接 12 ask=10 committed/2 limited、wait期间当前 role/tenant交集、asset-only降权拒绝、等待撤销及幂等撤销。

new_pg4 亲跑：未跨 expiry 的真实 owner 锁阳例返回当前 tenant；真实 bucket Lock 跨 expiry 后拒绝、原 count=0；历史可信 server epoch 的59.5秒加实际0.7秒等待跨分钟，旧 full bucket=10 保持，新 bucket=1；三个真正 spawn 进程的12 ask共享 PG，10成功/2限流。历史 minute 用例不称当前墙钟整分钟性能观察。原 PG20 同时通过 read60/ask10 跨进程、重启同桶、两租户/owner/URN/hash、当前角色/租户、双向撤销/降权真实锁、故障回滚、约束及真实 PG America/New_York 的2160小时 DST限制。

## 资源、失败与秘密边界

主控在 R14 释放后分配第二 heavy slot；R12 占第一。本 reviewer 只串行 probe/pytest，NullPool、连接5秒、statement12秒/lock8秒未扩大，每次新标记库 `test_dianzi_r18_rev_fix2_<UUID>`/新schema，只从当前授权本机管理库创建自有资源。DPAPI仅显式 runner opt-in捕获内存，实际 user/database匹配；未读原业务测试库、未对共享会话 kill。

首 same_probe 的业务 status passed、schema清理完且观察其他session0，但 DROP DATABASE 被 statement_timeout取消，finally异常使原 runner raw/receipt 未封存。此为实际清理失败，`initial_cleanup_tool_excerpt.log` 保存实际工具异常摘录，`same_probe_observation.json` 保留，不补造原命令精确起止/退出回执；`initial_cleanup_receipt.json` 实际于11:09:44.923622–11:09:45.667429核对确切自有库 exists=true/session0并drop，exists_after=false。仅自有 runner增加记录清理 OperationalError并保持非零的外层诊断，未改被审代码或提高超时；重跑相同原探针使用另一个新库，完整业务/清理 receipt均通过。

`pg_release_receipt.json` 覆盖三个完整 runner 的 schema0/session0/drop=true/dispose，以及首部分失败库的后续 exists_after=false；heavy slot已回报主控释放。零值只针对各自 owned DB 的实际观察时点，不是共享全局连接数。

每个完整 PG runner 的 raw/JUnit exact DSN/password 命中均 false，最终仅本 reviewer明确报告/run allowlist进行精确值扫描，无 broad scan/holdout访问。既有真实 SecretStr登记 hook实际用于原/新增 PG fixtures，源码与前轮强制失败的真实 DSN/password脱敏证据由13保护/4705完整材料核对保持；本轮未再制造新的强制失败测试，不把原 fail算业务通过。首清理异常工具输出只含自有库名和SQL异常，无DSN/password。

旧 scanner 14/14路径/模式与cd91基线同内容，仍属前述 asset合成CSRF/R07 probe和red/R17 red；作者及 reviewer原字节probe复制各加2个合成CSRF形状，共18，均独立对照。没有改分类表、删命中或把cookie23/1抹绿；广域扫描在本轮DPAPI前执行。

## 验证限制与交接

unit/metadata与fixture contract/pure security passed，独立 microsecond passed，隔离真实 PG24与原same probe passed；旧 cookie/security scanner回归failed。legacy cookie锁前 now 在正式CR列为R20已知后续缺口，key管理中的SessionCredential仍走旧锁；本有限Ship不称全认证已修复。

生产0026/完整迁移链、公开HTTP、key async actor_ref、MCP/SDK/真实客户端、job重放/409/预算/两个in-flight、paid IO、Linux真实PG、GitHub hosted CI、全integration目录、frontend/e2e/live/manual均not_run。consume须在外部付费IO前与共享job幂等/预算同一短事务消费一次，重放不重复；当前seam未接HTTP/job，未当实际产品通过。没有调用付费API，费用unknown；评分只登记有限E1/X1证据，不签整R18/G-E或A1/F3问答工具链。

下一建议：主控依据本有限Ship登记该切片，继续其独占0026与共享服务/job/公开入口接线；旧cookie时间与最终事务验证另经正式R20范围修复/复核。无新必须修复项。

Verdict: Ship. 仅本冻结 API-key credential seam；整R18/G-E未签。
