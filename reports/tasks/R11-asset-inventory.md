# R11 / T24 · 私有资产PG与独立API切片

状态：awaiting_review。该切片实现complete；整R11/T24仍partial，原C01–C06、SBOM扩展及恢复卡验收未删。代码冻结`6f82c68075dde808da9c92e3a49ad2e605e6b5a8`；表提案`4b15c77`；前置合入`6088ff5`。worktree `D:/wt/r11-asset-inventory`、分支`codex/r11-asset-inventory`，从主控指定`8a1b04d48346d8550f0326a77f003246a0ebbab5`创建。未push、未登记accepted、未修改progress。

## 前置、边界与合同

已读AGENTS、00执行图、12/R11、T24全C01–C06、03/04/05/06、冻结progress/交接、公开v2、Ponytail 5.2 full及parser独立复核。parser代码`64dcd946601cd0e0f7435f59019ee709e3738a35`、材料`37e492b4e26fc5b6197b60d2494926d4181a21c3`在此WT合入；不是8a后代，首`--ff-only` exit1后授权范围内`--no-ff`合并，唯一.gitattributes冲突取双方证据规则并集。原主仓未提交修改未触碰。

本轮源码为assets目录的新inventory_models.py、inventory.py、inventory_contracts.py、inventory_routes.py；测试为unit/test_r11_inventory.py、contract/test_r11_inventory_contracts.py、security/test_r11_inventory_boundary.py、integration/test_t24_asset_inventory.py。CR见[CR-R11_asset_inventory](../../docs/decisions/CR-R11_asset_inventory.md)。不改app、auth/access、公共schema、现有parser、富化、迁移、依赖、全局配置或状态。

05旧REST写入角色analyst与实际ROLE_PERMISSIONS存在矛盾：analyst只有READ_ASSET，本切片真实服务/路由严格WRITE_ASSET，不自行grant。public_api_v2实际没有AssetSnapshot定义，新增DTO完整映射03 AssetSnapshot和组件字段；公开Component五字段投影用原schema检查，不冒称完整public v2 AssetSnapshot适配已存在。

## 实现与输入输出

三个私有PG表保存资产身份/current指针、不可变历史snapshot、tenant+actor+固定route+key导入收据。正文canonicalhash复用已独立审核parser，JSON/CSV相同业务内容一致；rawhash仅追溯和请求比较，不作快照业务唯一。A→B→A新增版本，旧快照仍可按ID读取。源时间必需并由parser规范UTC，未提供或无偏移不自动填now。

snapshot保留完整规范payload、清单完整性/声明范围、组件生态/版本/摘要/来源定位、配置与权限/输入渠道/网络字段的None未知值，actor、parser/schema/source版本及原manifest bytes/hash。未列组件不产生排除证据。raw_input为私有BYTEA≤1MiB，GET安全DTO不返回原字节、内部路径或连接信息。

资产名仅创建时设置；既有asset_id的display_name不同明确AssetNameConflictError/409，不静默修改，不创建部分snapshot/receipt/change。明确改名操作留后续有界批次。

同key同正文/参数跨连接重放返回原snapshot，不恢复已旧current；不同raw、asset、display_name、mapping、source_version或观察时间409。固定route和主体分区，别tenant没有收据存在性信息。同asset同current canonical内容复用，无额外change/epoch/job/outbox提醒。

所有新snapshot、current、receipt、scope epoch、既有change_events/job_runs/outbox/publication_receipts同一Session事务。锁序为auth session/user→tenant请求advisory→asset advisory→assets FOR UPDATE→knowledge-publication advisory/scope epoch。直接服务不内部commit，HTTP工厂同事务复鉴权，CSRF/Origin验证，撤销/角色变化与提交有明确锁序；服务缺失返回503，不fallback内存fixture。

独立工厂直挂POST `/asset-snapshots`、POST `/asset-imports`、GET `/assets`、`/assets/{id}`、`/assets/{id}/snapshots`、指定history snapshot。二进制uploads流式限制1MiB，JSON/CSV交给原parser（其自身10MiB/10000组件上限仍保持）。asset-snapshots为JSON envelope，保存的是snapshot字段序列化后的manifest bytes/hash，未声称其为整个HTTP envelope的wire hash；需要精确上传原字节时asset-imports直传binary bytes，经真实PG断言原bytes/hash一致。错误仅固定代码与受控行/字段定位，不回显正文。

POST imports当前同步解析返回201；05原202异步任务协议、长上传、生产app接线和0018迁移留主控，不能算原API全部满足。资产列表用不变created_at+asset_id keyset；历史按snapshot_number倒序，游标绑定tenant、查询/asset，指针或新版本变化不重复旧页。

## 真实环境与命令

仅从授权WSL `/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json`捕获连接配置到进程内存；无stdout/argv/仓库DSN或口令。Windows独立venv由`C:/Users/yinha/.local/bin/uv.exe sync --frozen --offline --no-progress`建立，exit0，CPython3.12.13、80包来自本地缓存。此后解释器均为`D:/wt/r11-asset-inventory/backend/.venv/Scripts/python.exe`。

所有PG连接loopback `127.0.0.1:25432`，真实PostgreSQL16.14。每次检查创建独立`test_dianzi_r11_inventory_<时间runid>`库，最终`test_dianzi_r11_inventory_20261016_040900`。仅前向实际迁移到`0016_source_response_receipts`后显式metadata.create_all三个资产表，记录`create_tables_not_production_migration`；不downgrade、不删库、不清用户数据。生产0018未运行，本轮不将create_tables当生产迁移通过。

最终命令收据[attempt_6/commands.json](../runs/recovery_r11_asset_inventory_20261016/attempt_6/commands.json)记录完整argv/cwd、+08开始结束与退出码。测试cwd为本WT/backend，`--no-cov`是定向验证，不代表工程覆盖率门。

| 最终检查 | 实际命令核心 | exit / 结果 |
|---|---|---|
| 新unit/contract/security | `python -m pytest tests/unit/test_r11_inventory.py tests/contract/test_r11_inventory_contracts.py tests/security/test_r11_inventory_boundary.py --no-cov -q --junitxml=...` | 0；26 passed，0 fail/error/skip |
| T24真实PG/API | `python -m pytest tests/integration/test_t24_asset_inventory.py --no-cov -q --junitxml=...` | 0；46 passed，0 fail/error/skip，4.18秒pytest运行 |
| 原parser相关 | 原unit parser、identity_time、candidate contract、boundary security四文件 | 0；101 passed，0 fail/error/skip |
| domain/auth/outbox相关 | t04_domain_contracts、t06_access_scope_boundaries、r02_auth_state_inputs、r02_auth_state_boundaries、t07_jobs_outbox五文件 | 0；33 passed，0 fail/error/skip，含既有真实PG鉴权/outbox案例 |
| Ruff / format | `python -m ruff check`及`format --check`4源码+4直接测试 | 均0，8文件通过 |
| 类型 | `python -m mypy src/ai_intel` | 0，111源文件无问题 |
| diff | `git diff --check`及冻结前`git diff --cached --check` | 均0 |

新测试按文件分层15 unit、5 contract、6 security；PG46含安全与并发案例，不与新security6重复计数。最终合计206独立现有/新增用例通过；前面重复复跑不叠加测试数。pytest1–2条既有Starlette/httpx弃用warning保持，不降级错误或skip。

## 红日志与修复历史

原首轮26新测试为25passed/2errors：大bytes参数生成超32767字符PYTEST_CURRENT_TEST，Windows环境setup/teardown拒绝，未执行该业务case。首轮PG为34passed/2failed/4errors：同一超长ID环境问题；新CSV映射夹具未映射全部列，未符合原parser合同；新404断言误用顶层code（实际error.code）。只修正新tests显式短IDs、合法完整映射/等业务quote字节和正确错误结构，未改原parser/原测试/金标/分母/skip。首轮logs/XML逐原bytes归档可还原。

attempt_2为26新+38PG+101parser通过；主控名称变更约束加入后attempt_3为26新+40PG通过；并发/FK新增后attempt_4为25新+46PG通过，Ruff仅新增测试长bytes字面量失败；将等值bytes分行，未变输入。attempt_5为26新+46PG+101parser通过，相关回归26passed/7环境errors：既有fixture拒绝带query options的TEST_DATABASE_URL。仅调整新harness：裸专用DSN，连接options从connect_args提供；attempt_6相关33通过。全部原红日志保留，不改为skip或伪装业务失败。

原parser独立CSV探索38例37passed/1failed仍是历史事实，本轮未再运行或修复，不声称已绿。其冻结材料和初审/复核引用仍保留。没有全suite运行，旧CPU四失败不由本轮关闭。

材料harness额外root Ruff初检exit1：导入排序、runid未显式timezone、subprocess check参数和宽泛异常捕获4条；只修材料脚本（显式Asia/Shanghai、check=False、已知环境/子进程/PG异常）。修后format初检exit1只要求异常tuple展开，格式化后Ruff及format最终均exit0。原初检日志保留；此前已执行测试的命令、时间、输入和结果不重写。

## T24与评分证据

| 原案例 | 本切片真实证据 |
|---|---|
| C01 | JSON/CSV同asset规范hash/ID相同，第二份复用；PG保留首manifest原bytes/hash |
| C02 | 同key跨连接重放、同内容不同key、4连接同request及2连接同current皆只一份snapshot/提醒；变化后旧key重放不回退current |
| C03 | 版本1→2→1保存1/2/3并正确current与previous，历史API固定ID/游标；4并发版本形成连续序列 |
| C04 | 未知完整性/空范围/None配置/缺版本保留，安全DTO无排除状态 |
| C05 | 10001行、坏CSV列、1MiB+1、额外路径字段拒绝且零部分事实；行定位源自原parser |
| C06 | 跨tenant/不存在统一不可见；body tenant/role/path拒绝；WRITE_ASSET、CSRF、Origin、同事务锁鉴权及撤销验证 |

额外真实PG验证snapshot UPDATE/DELETE拒绝、成功commit current非空、current/predecessor/receipt联合FK、actor删除不cascade历史、发布失败回滚全部新事实与current、asset→scope锁序没有与模拟assessment反转。

F2/F3/P2只有受控授权清单输入、PG版本可追溯和租户权限的切片证据。没有产品真值、四态研判准确率、富化/问答性能或持续运行数值；不依据这些测试称评分项完整或优秀。

## 调用链与证据封存

CBM首先实际cli help，独立XDG `/tmp/dianzi-r11-inventory-cbm`，初始backend/src索引1501节点/7622边；assets单独108/396，避免默认assets排除误读。完成后的assets独立154/605，not_indexed/parse_partial/parse_unusable均0，仅__pycache__排除。schema/parser入向/import_manifest入向已追踪；源码/测试全rg交叉核验。生产API/app当前没有build_inventory_router caller；新router和新tests是实际caller，不把静态图当主app接线通过。CBM各命令时间未逐条捕获，明确不编造。

[artifact_manifest.json](../runs/recovery_r11_asset_inventory_20261016/artifact_manifest.json)记录每个新artifact bytes/SHA256、原logs/XML/txt/JSON/材料脚本原bytes/hash与对应gzip bytes/hash、源码冻结Git blob证明、各轮JUnit真实fail/error/skip/耗时。gzip逐字节还原原文件，raw本地原件保持；材料commit的权威原bytes全部在gzip，不将未过滤JSON视图的Git换行表示误算原运行证据。脚本捕获允许连接配置在内存逐项扫描新证据，发现配置秘密0。未导出实际私有上传清单。

本次manifest本体显式LF，原bytes SHA256为`d453b93dde90abe18d4241bf4a55d778d689110b20625d36d10bf1c13a171c0e`，94 gzip artifact与93原证据条目；源码按冻结Git blob并校验工作树Git过滤对象相同，不将源码LF/CRLF表示差异当原运行证据改变。

首次材料`429f432`在Git逐blob核验时发现12份commands/database JSON的Windows CRLF被清洁过滤为LF，因此该旧材料raw artifact校验未通过；首次材料diff检查为exit2（3份CBM原输出的额外EOF空行）。新材料将全部原JSON/脚本也gzip归档，manifest本体显式LF，6份CBM未过滤视图只从Git索引移除，原本地文件与原bytes gzip完整保留；不改.gitattributes或原证据字节。旧manifest原bytes SHA256 `20133131988398d83d114a923f254bae9c0d49cd2347efc6eb0b4bd91c1411e1`保存在artifact_manifest_before_raw_fix.json.gz，旧Git材料及实际诊断日志保留，不能把旧材料称已通过。最终新材料各gzip逐Git blob与解压原bytes匹配，diff检查通过。

## 八层状态与交接

unit/contract/security passed，仅本切片；integration passed，仅0016基底+3资产表create与独立router实PG路径。frontend/e2e/live/manual均not_run。生产0018迁移、正式app路由挂接与完整原API行为not_run。

下一步由主控唯一写0017→0018迁移并指派新独立reviewer，作者随后对生产迁移版本复跑T24；主控处理analyst权限兼容与05异步imports协议。T24选择一种核验SBOM适配仍未完成，不能宣称CycloneDX/SPDX支持。完整R11还需条件/资产研判/证据包、3→5产品真值与UI闭环；本报告不替代整卡验收。

未检查：完整生产接线/0018、frontend/e2e/live/manual、全suite/旧CPU问题、SBOM/OpenVEX及真实资产完整性；风险为当前单tenant写入串行化和1MiB同步入口限制，正式吞吐未测。
