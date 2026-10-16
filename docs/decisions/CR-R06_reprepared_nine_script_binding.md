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
