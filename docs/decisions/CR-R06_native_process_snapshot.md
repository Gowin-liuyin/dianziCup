# CR-R06 · 以原生进程快照修复 CIM 三秒超时

文档首次创建时间：2026-10-17T05:47:50.620+08:00
状态：approved_for_implementation；非作者审查和实际 native 边界通过前不安装实际控制包。

原固定 process_tree 整机 CIM 在独立初审和后续诊断均超过原三秒；系统 no-op 1.860 秒、限定父子 2.937 秒不证明全量可用。2026-10-17T05:46:27.164115+08:00 的最后单次对照中，原全量、三字段全量、名称两字段全量均超时，完整 Windows 峰6/自有残余0。增加 -Property 或更换 shell 没有达门证据；不继续扩大同根因探针。见 reports/tasks/R06-windows-actor-cim-diagnosis.md 和其原始收据。

用户完整实施授权包含启动、关闭及身份核验缺陷修复。本记录允许在已审 CORE 2ee7f509727e9fe37f31bba671083ac4aa07c123 / OPS f75b0ccf3d2ea51fb6083c47cd1078e82b64a816 之上，以标准 Windows Toolhelp32 进程快照和 GetProcessTimes/QueryFullProcessImageName 的最小实现替换 process_tree 的 PowerShell/CIM IO，并替换 stop_owned 的独立名称查询为同一原生快照。作者必须先给出精确返回字段和未知创建时间语义，不能静默丢弃疑似自有进程；不能将枚举、访问或 birth 失败返回空成功。公开业务 API、PG 数据、来源额度、模型、评测原则均不改变。

允许修改 candidate/core/windows_actor.py 中 process_tree 及必要的私有原生结构/导入，candidate/ops/stop_owned.py 中独立名称查询及必要导入；如果原生快照需要改变绑定或终止判断，必须先提交精确理由和 diff 由 Root 记录，当前不授权随意改 WindowsOwnedActor 其他判断。原三秒/15秒 readiness、进程与内存/CPU 限额、PID+birth、Job membership、launcher ancestry/generation、稳定 held handle、退出 ACK、KILL_ON_CLOSE 和未知闭锁均保持。

新冻结明确在旧两处恢复生命周期之外增加上述两条源码路径，其他十六个控制源码原字节不变；保留旧 74 oracle、既有新 freeze 及全部原红，在新候选验收中登记新增精确源码/hash/pins，不能改旧断言假称旧版本绿。控制源码总数与路径以旧清单实核，不凭本记录补造。验收须包含原 unit/contract、原生 wrong birth、foreign Job、wrong ancestry、正确 parent、真实 exit23、停止名称核验和已退出/访问失败负例。

无新依赖、无数据库迁移。实际安装仍由 Root 唯一执行，固定旧 binding/数据库 OID+COMMENT/nonce/ledger/累计 CPU 和第一次失败原字节；新候选需新审计/七门登记。回滚先确认候选 Job 和后代真实关闭，再恢复已归档固定控制包，不清理事实/历史/账本。旧 CIM 缺陷和旧 failed-bootstrap 失败保留，回滚不等于 ready。R06/G-C 仍 partial，六小时观察尚未开始。

## 2026-10-17T05:54:41.512+08:00 · 原生关闭的定向根因修复

作者首次 harmless-native 单窗2.368秒/Windows峰7/remaining0/held ACKtrue；六项身份、名称与退出边界通过，但 owned_tree_shutdown 在真实 actor已 exit70 后因全系统无出生时间的 unrelated orphan 行解析 created=None而失败。此红保留，不能据注册通过签关闭通过。

允许在同一 windows_actor.py 的 kill_owned_tree 残余孤儿分支增加一个窄判断：QueryInformationJobObject(JobObjectBasicProcessIdList) 取得完整当前自有Job PID名单，只有内核完整查询证明该无出生时间的、与已绑定代次无关的孤儿 PID 当前不属于本Job时，才可跳过其 generation解析；该PID不会被发信号。查询失败、名单截断/数量不一致、PID仍属于本Job、已绑定actor/已知后代的未知birth一律OwnershipError，不伪装关闭。其他 birth/membership/ancestry/held ACK 判断保持。作者须先提交精确diff、调用方和PID重用/名单变化负例；独立审查再核内核证明边界及完整名单，不可用argv或空列表替代。仍不增加CIM fallback、预算或第三处控制源码路径。

## 2026-10-17T06:16:41.590+08:00 · 未知出生时间的错误类型一致性

新独审指出_bound generation调用 str(None) 后原 _snapshot_ticks 抛 ValueError，上层通用Exception闭锁，没有已证越权，但与本记录OwnershipError错误分类不一致。授权唯一作者仅在 _snapshot_ticks 对无效/缺失出生时间的解析错误统一抛 OwnershipError，合法ISO/微秒和100ns比较语义不变。作者新增unknownbirth负例可按此原合同修正期望类型，历史oracle保持；新CORE及OPS精确pin/23映射/4changed16same重新冻结，由当前未参与实现的独审定向复核。c8及a70原native/旧测试记录保留，不把旧SHA通过给新SHA背书。

## 2026-10-17T06:19:22.073+08:00 · 关闭后已绑定 PID 的未知出生时间

新非作者亲复四个定向负例：初始actor/descendant未知出生时间为错误类型差异；关闭后remaining中已绑定actor或已绑定descendant的created=None且其parent仍存在时，可绕过orphan guard并正常return。后两例为真正Must fix，不能据原生七项和多代通过消除。授权唯一作者在remaining循环头独立检查 created=None且PID已绑定或parent为已绑定代次，立即OwnershipError，再进入既有foreign orphan分支；禁止发布descendants_exited成功。PID/Job/birth/退出门不变，原c8四红/原生/多代证据保留。交新CORE与OPS pin，原独审定向复验这四例及正常关闭。
