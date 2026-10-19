# R18 API-key post-lock expiry fix 2

状态：awaiting_review；本 Must fix 2 实现 complete，整 R18 仍 partial，未登记 accepted、阶段通过或 push。实际材料封存时点见本 run manifest；精确测试时点逐条见 receipt，不补造时间。

冻结基线为 CI fix1 material `c0428cb9801549c3bc778060153899e4b72028a2`，其凭据业务仍来自 `3c14df50cc3372df541ad1cbda36fe1485dcdf7a`。主控本轮 HEAD `17ab90e0a6b100530a3078dd525f9086813c9728`。新树 `D:/wt/r18-api-key-expiry-fix2`，分支 `codex/r18-api-key-expiry-fix2`；source `8e0485231bf9367d5b4b3a79802bdf346b1fb745`，tree `de786d07134564ec059c88ac1515ba58a1aea6f3`。最终 material SHA/tree 由封存后实际 HEAD 交接，manifest 单独绑定 source 与 raw/Git blob。

已读 AGENTS、执行索引、恢复 R18、前轮 T32/T40/T51 引用合同、冻结状态/交接、approved CR-R18_api_key_credential_seam、原凭据/CI fix1 报告，以及非作者 `G-E-R18-api-key-credential-review-1-recheck.md`。该复核 manifest 原字节 SHA256 `4705e2c71eeaf100f2fe53422359e80ae5e628eb584b9bd7567956b22c0a713f` 已核对。采用 Ponytail 5.2 full 与 diagnosing-bugs 原探针反馈流程；受主控资源程序约束先做离线红→绿，再获一个 heavy PG slot 后重放真实探针，未再委派。

改动源码仅 `backend/src/ai_intel/api/credentials.py`，直属新增测试为 `backend/tests/unit/test_r18_api_key_post_lock_time.py`、`backend/tests/integration/test_r18_api_key_post_lock_time_pg.py`，另为本报告及 `reports/runs/recovery_r18_api_key_expiry_fix2_20261016/`。原 PG20、offline49 各文件、模型、认证旧实现、0026、公开 routes/app、依赖锁、公共 schema、progress、root attrs、旧88/100材料、旧审查探针/日志、盲测/阈值/分母均未改。

## 根因与实现

原 `_lock_api_key` 在 SELECT 锁前把 now 绑定到 issued/expires 的 SQL 条件；真实 key/users 锁等待结束后仍使用旧时点，因此有效期内开始等待的三秒 key 可能在过期后获得 scope。当前代码仅用 token hash 找到并锁住 key/users；锁取得后从被锁行读取 resource、issued_at、expires_at、revoked_at，使用可信 server now 加实际 monotonic elapsed 检查，再根据当前 role/tenant 和 key scopes 交集返回 scope。

公共 `lock_authenticated_principal(connection, credential, now)`、`consume_api_key_rate_limit(...)` 的参数/返回签名未变。now 仍要求由可信服务端在调用时新鲜采样，不接受请求体时间；monotonic 只推进已经可信的时点，未使用数据库事务开始时间、未把客户端可自报 future time 引入权限权威，未新增时钟配置或 SQL clock 接口。该方式保持历史 fixture clock 与绝对 UTC/DST测试的兼容。私有 `_lock_api_key` 的第二返回项改为仍被事务锁住的 RowMapping，仅 principal/consume 两个内部调用受影响；公共返回仍为 AccessScope。

consume 从入口开始累计真实 elapsed，在 key/users 锁后和 bucket 锁后都验证有效期。最终时点跨分钟时，重新取得新分钟 bucket 再判配额，只在最终有效窗口加一；已满的旧分钟桶不会因此拒绝下一分钟请求，也不把等待后的消费写到旧分钟。旧分钟已有计数不变；途中创建的零计数桶遵循调用者事务的提交/失败回滚语义，没有另建业务真相或豁免配额。现有 read60/ask10、表主键、PG 原子锁和事务回滚合同不变。

SessionCredential 分支严格保留原 `lock_authenticated_scope`。源码核查该 legacy helper 也用入锁前 now 过滤 session expiry，这是共同时间假设；本轮授权明确保护旧实现，不能据本 key 修复声称 cookie 的跨 expiry 等待已解决。key 签发/撤销管理中的会话鉴权仍走此旧分支；主控需要另行处理其接线和最终事务时间规则。

## 实际验证

普通命令 cwd 为本 worktree/backend，Python 为 `D:/dianzi/backend/.venv/Scripts/python.exe`。`checks.py` 保存完整 argv、实际 +08:00 起止、退出码、HEAD、日志 SHA 与 JUnit 数量。PG runner 额外保存源文件开始 raw hash、运行期间字节不变、source root、完整 runner argv、实际 owned DB/schema/session 清理与秘密扫描。局部 `-o addopts=''` 只关闭全包覆盖率触发，不作为整仓覆盖率通过。

| label | 输入与实际命令范围 | 真实结果 |
|---|---|---|
| post_lock_time_red | 新 seam unit 五例，修复前 pytest | exit1；4 failed/1 passed，0 error/skip；两 expiry、quota expiry/分钟为原症状红，未过期阳例通过 |
| post_lock_time_green | 同五例，修复后 pytest | exit0；5 passed，0 fail/error/skip |
| offline57_source | 原49加新8 unit，同次 pytest | exit0；57 passed，0 fail/error/skip（unit34、contract17、pure security6） |
| ubuntu_fixture15_source | 真实 WSL Ubuntu3.12.13 subprocess，原 CI fixture contract | exit0；15 passed，0 fail/error/skip；合成 IO，不是 Linux PG execution |
| same_probe_red | 原 reviewer probe 原字节，显式 runner --baseline，child PYTHONPATH 指向 c042 frozen source | exit1；真实3秒 UTC expiry/pg_stat_activity Lock 后 authorized，再 fresh call denied；原 quota/role/tenant/revoke 断言仍执行，原红保留 |
| same_probe_green | 同原字节 probe，当前 source8e048523 | exit0；真实3秒 expiry Lock 等待后 denied，原3连接12ask=10 committed/2 limited、role/tenant、asset-only降权、撤销及幂等均通过 |
| new_pg4 | 直属新增 PG 四例，单条串行 pytest | exit0；4 passed，0 fail/error/skip；未跨expiry阳例、bucketwait跨expiry零消费、真实Lock跨fixture分钟、新3spawn12ask10/2 |
| original_pg20 | 原 integration 文件原字节，source8e048523 | exit0；20 passed，0 fail/error/skip；双向role/revoke真实Lock、两进程read60/ask10、重启、回滚、DST2160小时等原断言不变 |
| cookie_regression | 原 T06 authentication/scope 与 R02 input 文件 | exit1；23 passed/1 failed，0 error/skip；失败仍原 T06-C06形状扫描 |
| quality_final/type_final/quality_format | 一业务源、两新测试、两个runner helper | exit0；Ruff、format、mypy 5 files no issues |
| quality_material/type_material | 上述与四个自有材料 helpers，精确 argv见receipt | exit0；Ruff、mypy 7 files no issues；后续 format_material 为同范围格式检查 |
| frozen_audit | 固定allowlist审计，不读holdout | exit0；原88/100原始archive/Git hash、13保护、11锁caller、原PG20整段业务字节、公开函数签名、原review manifest/全部材料和原probe字节符合 |
| scanner_before_pg | 原 security_scan，在解本轮DPAPI前执行 | exit1；原14命中保留，另原样复制 reviewer probe 的合成CSRF literal产生2形状命中；扫描仍failed，未改分类表 |

真实 PG 共四次独有新库：same probe red `10:48:59.065071–10:49:04.570868+08:00`；green `10:49:21.298238–10:49:26.274724`；new4 `10:49:39.626292–10:49:46.846384`；original20 `10:49:55.030981–10:50:04.253152`。source SHA/tree与每次文件hash见receipt，不累计重复检查为额外用例。

原探针 `independent_pg_probe.py` 与输入/断言精确原字节保留，runner 仅选择 frozen/current source 并把各次生成 observation 另存独立 label，没有覆盖旧 red。冻结再现：passed_now `02:49:01.143172Z`，expires `02:49:04.083086Z`，received `02:49:04.192386Z`，authorized。新源再现：passed_now `02:49:22.902809Z`，expires `02:49:25.878724Z`，received `02:49:25.985879Z`，denied。两次均真实服务端 datetime.now 与实际 PG Lock，未修改系统时钟、expiry三秒或 probe 断言。

新增 minute PG 用例明确使用原 fixture 的可信历史 server epoch `NOW`、59.5秒和实际0.7秒锁等待；旧桶10保持、新分钟桶1。它证明 PG锁与时间推进/配额选择结合，不冒充当前墙钟整分钟观察。新增 bucket expiry 与未过期阳例使用真实 UTC墙钟；new unit 的两 DST offset边界测绝对UTC elapsed，新PG20继续保留原真实 America/New_York DDL边界。新增3spawn是真正三个进程共12次ask，独立原probe的3线程/连接另行记录，不混为进程证明。

PG由主控分配第二heavy slot，自己仅串行一个pytest/probe，前端占另一slot；未抢占、kill共享PG或提高limit。DPAPI仅显式自有runner opt-in、捕获内存；仅管理库创建 `test_dianzi_r18_expiry_fix2_<UUID>`，不读原开发/基准库。TEST_DATABASE_URL/DIANZI_TEST_RUN_ID只在子/本进程内，结束还原；NullPool、connect_timeout5及既有statement/lock timeout，schema只本次新UUID。四次均 schema0、ownedDB其他session0、ownedDB drop成功，全Engine dispose，slot已释放。真实DSN/password未写argv/stdout/env cache；原pytest SecretStr register hook保持，raw/JUnit exact命中均false；最终自有材料扫描另见final_secret_scan.json。

原14扫描路径/模式保持：asset-client4、asset-scope6、R07 probe1/red2、R17 red1。新2项来自未经修改的 reviewer probe 合成 `csrf_token`，原pattern与value-pattern各一；本轮不改分类、门槛或把失败改skip。cookie回归仍failed，不声称全仓秘密扫描通过。首次新unit红和格式长docstring失败均保留；未发生或未运行的检查不填数字。

CBM0.11对 fresh原源树先索引 `dianzi-r18-expiry-fix2-c042-20261016`，保留architecture/schema/_lock_api_key trace；最终源重新索引 `dianzi-r18-expiry-fix2-8e048523-20261016`并追consume。rg补足fast排除assets/cache并核源码/原测试/类型/公开函数签名和全部旧锁caller。当前seam仍未接公开HTTP/job，图不作为接线成功证据。

## 边界、偏差与交接

新run局部 `.gitattributes` 只将本目录原始 `.log/.xml/raw_artifacts.zip` 标为binary，保留真实红/生成空白字节；root attrs与原88/100材料不动。manifest分别列raw与实际Git blob SHA；archive保存原字节，不能将fresh checkout CRLF当作作者raw LF。此限定属性已由主控授权，不是全局禁用检查。

本切片 unit/contract/pure security 与真实PG24及原独立probe passed；旧cookie/security形状扫描failed。HTTP/job actor_ref、付费预算预约/幂等/两in-flight、Linux真实PG、GitHub hosted CI、全integration目录、frontend/e2e/live/manual均not_run；外部付费调用为0，本轮只访问授权本机PG。未变评分、gold、分母或合同公共接口；可信时间推进方案已向主控报两内部caller影响并获继续授权。

评分证据仅 E1/X1 的 key锁后时间拒绝、配额与有限回归；不签 A1/F3真实工具/问答或整R18/G-E。下一步由原非作者在fresh tree对本source+material定向复核，必须重跑同原真实expiry probe、原20与新增并发边界；之前任何not_run不能转通过。主控同步正式时间说明、独占0026/共享业务接线；本轮作者到awaiting_review停止。
