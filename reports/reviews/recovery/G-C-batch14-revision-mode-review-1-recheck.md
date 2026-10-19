# G-C · 批次14修订模式 M01 定向复核

文档创建：2026-10-17T04:24:34.643+08:00（Windows文件ctime实读）；最终封存时间与报告hash见 recheck_sealed_delivery_secret_scan.json。

真实复核窗口：2026-10-17T04:20:03.102–04:20:34.308+08:00。

结论：**Ship，仅本模式读取兼容切片及 M01 测试输入修复**。M01 在新测试 source 下已亲复关闭；不改变首次 `48f96b5b` 报告的 needs_changes 和原 6 pass/2 fail。整 R06、R07、R17 或 G-C 均不因此 accepted，不修改 progress。

What this change does: 修复把 `(bytes, content_type)` tuple 错传给 SourceResponse.body 的两例测试输入，只解包并使用 bytes。原生产模式分类、API/proof 围栏、共享 fixture、原8 PG用例及10条 assert、NVD URI、原24诊断保持。

## 固定来源与本次文件

- 实际产品：`48f96b5ba35d19f5e26868a2bccd5b124afb2bd0`。
- 最小测试 source：`6bb19fcdbf5c8242142c3f61e338b98a29bc5501`；材料：`81840ea42ae1425dfa1468eafed7edb49b440357`。两版与产品48的 `backend/src`、真实 `backend/migrations`、contracts/progress/frontend/docs均无差异。
- 原独立 WT 的业务树保持48 exact；HEAD `04da910b5217def869d03800a7144967d8d520c6` 只增加首次报告/helper/evidence。新测试从6bb的 Git blob逐字节拷到 own report run，不写任何业务文件。
- 修正 PG test raw SHA256 `cf2bcd21007f5c3a2d857aba793e739ff0ccd4dc446871f6a05ad074ad73d9f9`。默认探针的冻结材料是04da，指纹/源码不变；探针自身 tuple 输入修正已在04da保留，原失败日志未覆盖。
- 本次变更只有本复核报告、直属 helper/new-label/raw，旧首次报告 raw SHA256仍为 `c3bc6648a1b1dcec23f3130163bdc614486a4f97f5749e7cc6bdb77fb9f2a0b1`。

## 实际结果、命令与去重

| 层/来源 | 实际命令与结果 |
|---|---|
| 新固定 source 的 PG8 | own `pg_controller.py --fixed-recheck`，argv为 pytest `-p pg_backend_plugin test_fixed_revision_mode_read_pg.py test_default_mode_pg.py --no-cov -q --junitxml=.../recheck_modes_and_default.xml`；**8 passed / 0 fail/error/skip** |
| 审查人默认应用探针 | 同一真实 PG 命令，额外1例；**1 passed / 0 fail/error/skip**，不归到作者 PG8中 |
| 新 bytes 输入正例合同 | `review_checks.py recheck_contract`，实际 pytest冻结正例副本；exit0，**1 passed / 0 fail/error/skip**，无PG连接 |
| 既有 unit/contract/static | 未重复运行。首次产品48的312 distinct fixture、22文件Ruff/format、194源码mypy结果沿用同一生产来源；不把它们叫本次新执行 |
| 其他旧PG、R07并发/锁、完整security、frontend/e2e/live/manual | **not_run**。本轮 source/model/FOFA/paid/browser 调用0，真实PG与ASGI默认路由不能当来源或模型live |

组合日志是9 passed in 26.62s、pytest exit0；controller端到端31.203s。XML按 classname拆分作者固定PG8与own probe1；与首次组合的9个 case name相同，属于定向复跑，不把新9加到旧9作18独立例。合同正例另计。精确源码绑定、counts/case names和rawhash在 `recheck_counts_and_rawhash.json`。

本次 stdout SHA256：`0efdddd74b5b54c22374ce122a4b4c4c3dcb0c6e773a634bd09f6b901304d6ad`。

本次 XML SHA256：`7f0a61956dbba0e67561ff1ee10550990761cd799d80007a05ef1162b038d38e`。

二者均为 own run `reports/runs/g_c_batch14_mode_review_1_20261017/recheck_modes_and_default.*` 原始字节；完整argv/+08起止/退出、PID/birth、SQL backend创建phase/caller、父sampler与全部client行、清理证据在 `recheck_pg_controller.command.json`、`recheck_pg_backend_creation.jsonl`，未改任何旧outcome。运行时backend记录追加到了同一journal；封存时核04da原字节前缀后，将新增nonce行逐字节分存新label并恢复旧journal原字节，两份与分存hash/count保留。

## 默认实际装配与被到达的断言

实际 `create_application(settings=...)` 使用默认 `build_engine`、DatabaseUserDirectory、PgAuthenticationStateStore及两公开router，没有注入 Engine、auth service、reader结果或mock成功。用户名、密码、session/CSRF是隔离测试生成，仅敏感失败登记；正式服务与浏览器未启动。

- `/v1` 和 `/api/v1` 匿名知识/文档/证据请求401；真实PG登录成功；权限移除403；实际PG注销后文档和事件都401。
- live配置下当前文档live、选择明确fixture历史返回fixture；未知修订和混合历史整页503；1条历史分页的next_offset保持1/2，未知页503而非过滤为空。固定fixture证据指向正确旧revision和fixture模式；读取前后paper source_metadata相同。
- private文档属于另一个tenant时，document detail/revisions和evidence都404；恢复公开是审查fixture setup，产品读取没有写历史。
- 两条当前document的真实limit1 cursor产生下一页，第二页没有next_cursor且两页ID不同；更换过滤条件复用cursor得到422。原坏cursor、对象不存在分别422/404。
- inactive的fixture或unknown事件历史依然让detail503；active摘要只按它实际使用的可见修订分类。恢复合成setup的同质live后，2000历史及active关联完整返回200；加入第2001后detail与list都503，没有伪items/next_cursor，PG中历史关联数仍为2001。
- PG8另外确认同质fixture/live事件详情、未知非空列表失败、真正空筛选保持空、内部live证据reader拒fixture，以及unknown/fixture/live原历史元数据不被读取改写。

所有输入均为显式合成/本地记录夹具；DTO的live在这些测试中只是被保存的可信测试模式，不是实际联网来源证明。R07 mode/指纹/强证明的生产源码没有变化，首次静态与unit围栏核验保持；没有用本9例代替其整套真实并发证明。

## 真实资源与 Source 绑定

主控授予新的60秒B独占，50秒停止业务、预留10秒清理。本次31.203秒内正常结束，无deadline/cap异常。

唯一自有库：`test_dianzi_r06_mode_f47b2a40a8194a`，native OID **10501286**，exact9原COMMENT SHA256 **37ccbc313527459d49b8d6c88d7932b9529d0fe785dbea95cdceb9a97d703f0d**，product_sha=48、maximum_seconds=60、queue/redis_prefix=not_used。每schema真实迁移head0030。数据库身份来自native catalog，不使用schema内同名关系。

亲核 role superuser=true、rolconnlimit=-1、server max_connections=50；profile2仍是soft业务预算。目标业务峰2、父sampler1，真实owned总峰3。全部client行和count包含sampler；采样控制树Win+Linux峰6/16，无自有Linux服务。nativebackend PID/birth与创建caller逐条保留，未宣称物理硬连接2。

04:20:34.166+08清理前 target_sessions=[]，all-client只剩父sampler PID6001；只在 native OID+原COMMENT全文均相同后DROP自nonce库，随后验证库不存在，关闭父connection。新子进程残留0，精确DSN/password/8字符片段扫描0；补验B于04:20:34.308+08交回，之后没有再开PG。

Source只通过父库native catalog只读核绑定，前后相同：旧10434264 marker SHA `faf3bfac90479085d6462bfb6689e70a4828a7024dfab66345fc4d14f1a797ab`；当前10451302 marker SHA `cae93d1ce7798f01a8e370f8dfa99128a83038cdb978b5d321cfa8fd18022c14`。不连接Source业务库，不改父服务/角色/Source/Redis/MinIO，不paid，不降级或强制结束其他连接。

## 材料限制与下一步

新contract是正确解包的 bytes 输入正例；它没有调用原PG测试函数，单独回退PG的两行修复不会使该contract失败。直接证明原tuple调用已经修好的证据是本轮事件fixture/live两例真实PG，两例均已执行并通过，不能仅以正例合同称原反例回归。

作者 `verify_fixture_fix.py:46` 的辅助路径写为backend/alembic，实际是backend/migrations。本审没有沿用该迁移检查结果，已独立核对真实目录与48无差异；当前无实际越界，后续复用该辅助校验应修目录名。材料仍准确标此前只collect8、不算PG/live，未修改其历史。

无合同、依赖、迁移、认证规则、金标或指标分母变更。F1/E1的模式真实性/ACL/历史和失败边界有本切片真实PG证据；F2/P2强证明没有放宽，但不计富化准确率或完整验收。

下一步由Root按新source+actual product组合登记本切片并整合其他独立审查；本审不推进下一任务或签整卡/阶段。Root783、其他budget/graph/R01完整PG及来源持续采集仍按各自实测范围处理。

Verdict: **Ship，本定向切片**。Not checked: 上表所有not_run项保持。
