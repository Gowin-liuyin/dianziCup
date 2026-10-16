# CR-R06 · 新九脚本准备包与旧运行材料隔离

文档首次创建时间：2026-10-16T16:14:10+08:00
本次写作开始时间：2026-10-16T16:14:10+08:00
状态：approved_for_implementation；仅准备/核验，不代表启动或整阶段放行。

旧configuration.SCRIPT_NAMES固定8项，已独立复核的MinIO controller新增为第9项；旧prepared元数据也只绑定8hash。原87faa控制器修复已有限PREP Ship，但用原8项冻结给新9项背书无效。新建单独operations/deployment/run/nonce/queue与marked来源库，原8ops/10core及全部历史raw只读保留，绝不原地覆盖旧私有准备包。

唯一指定准备集成人在新worktree内调整configuration/prepare_deployment及必要保护检查：9script exact Gitblob+SHA绑定，包括最终minio_controller@87faa，固定产品backend基线1cdb9e7d99b7d24f702f5f19309a56d5afedd526、原CoreTool804e65ee4ae9b7b9968351b2b26eb8ffa94e52be。新路径、RUN_ID、brokerprefix和db identity都明确；现有migration只前向至0029，旧库name/OID仅保护登记不写。9脚本执行/字段不漏，新private副本符合独立review的精确代码，不接受缺项hash默许。

资源仍源窗口21600秒、关闭900秒共22500秒，现有父期限2026-10-17T21:49:15+08不延长；总source jobs上限450包含旧11，预停410/solo最大发418，5page/max3attempt/35100保守HTTPS上界；0产品model/FOFA/Hunter/Quake/ZoomEye/RESTsubmit，成本未知仍unknown。Windows每process512MiB/总2GiB/20%host/1200CPU秒，LinuxMinIO aggregate512MiB/1CPU/128PID/swap0，预持14FD<=16、scope132、错误可见和原sharedhardEnd不改；单组件日志8MiB/observer16MiB不扩。

准备先actual resource/identity/port/known-old-owned-queue/磁盘/新库PGRedisOS检查，不杀他人、不flush/drop旧资源，不从附件读取keys或打印DSN。私有凭据仅仓外加密引用在进程内传递；新段原对象目录可只读校验复用且保留原文。准备阶段七activation flags均false、readyfalse。根主控取得新非作者整个新9script/config/deploy/实际identity检查意见后，才根据已有授权写activation并启动具名新run；准备作者不得自行开始采集或说6小时完成。

兼容/回滚：新增独立包和库不影响旧facts/history/cursor，原core行为保持；准备失败只关闭自有新资源，保留失败材料，不清理用户文件/原准备包，不downgrade。测试包含8→9遗漏拒绝、finalcontroller hash变更拒绝、未知PID/nonce/boot/DB/queue拒绝、父期限/预算/同version检测、真实只读依赖探测与原保护校验。各类证据层分列，新独立review必须固定source/material/tree，不能把3个历史运行段拼6小时。

本次写作结束时间：2026-10-16T16:14:10+08:00
最后更新时间：2026-10-16T16:14:10+08:00

## 核心绑定兼容修订 · 2026-10-16T16:35:50+08:00

本次写作开始时间：2026-10-16T16:35:50+08:00；修订人：/root。

实际只读核查发现原Core804并不支持配置换绑：authorization.py固定PRODUCT_SHA=e310；controlled_supervise.py固定产品目录、e310、旧sourceDB/0016与旧queue；deploy_runtime_entry.py固定旧Redis prefix/queue。新9脚本仅改configuration会被拒绝，或仍指旧资源。本条纠正此前“原core行为保持”适用于新包的错误兼容判断；旧10core物理字节和历史8ops包仍只读保留。

批准指定独立核心集成人在新worktree/new-core目录为上述三个入口增加唯一固定运行绑定适配，必要时新增一个小run_binding.py，不对旧文件原地改写。新绑定精确包含产品1cdb9e7d99b7d24f702f5f19309a56d5afedd526及clean checkout、marked新库name/OID/0029_recommendation_receipts、新queue/Redis15 prefix、新RUN/nonce/OPS/DEPLOY路径、原observer与9ops/新core全部hash。绑定来自root准备后冻结并独立复核的文件，字段缺失/未知/不一致在外部IO前拒绝；不得把schema检查取消、把任意body/path/URL变为配置自由度或静默兼容旧queue。

所有资源caps、父期限、七activation=false和ready=false保持。新core所有变更要连同9ops/config/prepare/deploy重新固定source/material与总manifest审查，旧804的Ship不自动背书新core。准备作者唯一写9ops/config，核心作者唯一写新core及直属tests，root负责公共变更、库创建/0030不纳入本采集基线和最终启动。原sourceDB只读保护，无游标/事实迁移的默认许可；新段如不迁移，必须注明从新的可证起点观察，不能声称延续旧段。

测试影响：重复键/未知字段、产品/表head/DBname+OID+marker/queue/prefix/run/nonce任一变更、旧8hash缺controller、corehash漂移、父期限/预算、activation缺失全部拒绝；正例只能准备成功，不能假造live启动。回滚只停新自有资源/保留材料与新库，不清旧库/旧queue、不downgrade/改全局权限。此为已授权持续采集运行入口的必要兼容修复，无新增范围、评分或费用授权变化。

本次修订写作结束时间：2026-10-16T16:35:50+08:00
最后更新时间：2026-10-16T16:35:50+08:00

## 联合身份、原生marker和累计额度修订 · 2026-10-16T18:21:19+08:00

本次写作开始时间：2026-10-16T18:21:19+08:00；批准实现/准备，独立激活门未过。实际旧ToolRoot804e clean依赖要求与新core直接复制矛盾，因此明确双身份：旧ToolRootDEPLOY@804e保持clean与旧observer，独立固定CORE目录D:/dianzi-runtime-cache/r06-nine-script-core-20261016只放新source440346十一Gitblobs，OPS55a九Gitblobs。准备启动时ToolRoot必须全clean；运行中仅固定currentnonce原observer root_live_gate.json与live_RUN_ID未跟踪输出允许，tracked/HEAD/其他变化拒绝。原gate14fields不加nonce，通过segment_id='segment_'+nonce绑定。

新库test_dianzi_r06_nine_script_20261016只前向0029；OID/marker尚None不启用。root实际创建后原生COMMENT ON DATABASE/读取shobj_description确认strictJSON exactproject/kind/run_id/owner/product_sha/maximum_seconds/queue/redis_prefix/created_at和rawSHA，不拿旁表metadata自称身份。旧OID3680428/旧facts/cursors不变，不默认clone。公开冻结OPS/core互相引用hash不要求文档自提交SHA，避免自引用循环。

累计budget ledger42经旧初11subset+旧close42+fresh42同ID/type/time/provenance并集去重亲只读验证，source_budget_ledger SHA2604347a4559d3353a045a57393ea632f90ba74fd2c98615400751672e0d03b9；总450/prestop410/solo418不扩，对应remaining408/368/376。21600+900/父deadline/其他资源cap不改，真实wire/cost unknown。准备finalprivate/newcore安装/新库/activation不因临时WSL正例记live。兼容回滚仅停止新自有资源，保留旧包/旧库/失败证据，绝不清全WSL/用户资料。新fresh reviewer完整20文件冻结亲复后root再做实际OID/marker/端口/预算/权限资源门，6h不能拼历史段。评分/原分母/gold不变。

本次写作结束/最后更新时间：2026-10-16T18:21:20+08:00；修订人/root。
