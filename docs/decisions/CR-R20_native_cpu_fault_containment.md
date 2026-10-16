# CR-R20 · Windows 采样守卫故障时的CPU限制修复

文档首次创建时间：2026-10-16T14:57:02+08:00
本次写作开始时间：2026-10-16T14:57:02+08:00
状态：approved_for_implementation；已授权R20安全/恢复原CPU门的实现修复，不改变数值门槛。

真实诊断77ee56报告保存两原红1.109375/1.15625秒，当前产品守卫死亡后0.4秒窗口采样中止；清树成功无法追回已用CPU。产品没有Job CPU rate；24逻辑核平台rate2000只是整机20%，不能当0.2核。诊断rate83的一个对照不能替代严格累计预算证明。

批准在已有process_limits/已批准early bootstrap两个共享位置内最小修复：在可信worker业务/重依赖导入前设置并读回所需原生Job限制、保护守卫生命周期，使用Windows官方能力与已测平台核数校准。native memory/user CPU与user+kernel采样边界均保留；异常失败关闭运行，不伪装限额成功。rate如采用，应说明整机计量与多processor-group处理、保证原累计CPU红例的真实结果，不能只输出rate配置数字。原1秒累计门不放宽，不扣启动CPU，不把预估/采样当最终GetProcessTimes；错误/超时/进程树逃逸/guard失联都实际测。

允许修改新独立WT里的backend/src/ai_intel/infrastructure/process_limits.py、现有受控early bootstrap实际文件和直属unit/security/native tests。所有调用者/启动入口先CBM+rg核实，不建立另一个平行限额框架。主控/别的Agent不能同时改这些共享文件。公共资源配置/锁/评测指标/默认model/service/秘密不改。

测试限额：最多12个主要native dummy启动，每个parent hard deadline<=8秒、CPU/memory原预算、自有Job句柄/PID proof/cleanup，严禁业务collector/paid/PG作为dummy。原两CPU红、6旧启动红与诊断原日志保持；修复后同输入复跑，并独立测试guard死亡/初始化失败/多thread native GIL/子树回收、实际限额读回。控制异常不吞，不能改skip/阈值或释放全局Windows权限。若同根因两次无进展，停止扩大补丁交新diagnostic。

兼容：公开bound_process_resources签名与Linux已有rlimit语义保持；Windows既有合法启动与默认消费者继续走共享入口。回滚独立source增量保留全部失败证据，未通过限额不启动相关受控live。无需数据库迁移或新增依赖；如API不可实现原要求，明确限制与最小可行平台选项交root，而非虚假成功。新非作者review复跑固定源码后仅可局部Ship。

本次写作结束时间：2026-10-16T14:57:02+08:00
最后更新时间：2026-10-16T14:57:02+08:00
