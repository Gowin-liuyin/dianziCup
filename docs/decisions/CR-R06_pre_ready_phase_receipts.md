# CR-R06 · pre-ready 阶段诊断回执

首次创建/本次写作开始/结束时间：2026-10-17T07:53:58+08:00
状态：awaiting_review；主控授权常规诊断修复，独立审查生效前不安装。

触发：冻结产品912d/CORE37/OPS810实际07:04:46至07:05:04首worker ready_timeout，无ready/control actor，现日志不能区分import、配置、DB初连；原15秒ready门槛不变。变更仅CORE既有deploy_runtime_entry.py增加固定阶段诊断，无新受信源码列表/产品功能/资源/收费调用/观测窗口。最多固定阶段集合、每项≤1KiB，自身PID及完整100ns birth绑定，授权前仅两个固定不含role/ENV的入口阶段，授权后角色只既有白名单；不记argv、ENV、URL、SQL、异常message或私密locals。固定pre_ready目录，独占临时文件、无覆写原子发布，写失败明确失败，禁止伪ready。

兼容：原CLI/ready文件四键/worker和beat真实授权顺序保持；新诊断文件不作authority或ready条件；此CORE源码变动使旧pin失效，必须完整新rawmanifest、新冻结独审、新helper三pin/版本transition和Root安装；不能旧audit给新控制源码背书。旧两次失败/原包保留，pre_ready新目录由Root另行版本化归档，不混control目录。迁移仅workspace外owned runtime cache，在fresh kernel关闭证明后原子更新；protected两源DB/COMMENT/ledger42/450与非source binding字段不变。回滚：只在Source和descendants真实held/kernel退出且无runtime启动后恢复备份20源、manifest和原binding，重新17项审计；不能边运行换包或删除失败证据。

任务/测试影响：R06/R20诊断切片，不接受整R06/G-C或同版本6h；author独占deploy_runtime_entry+directtests。新非作者审查正常、预授权、失败阶段、写拒绝、重复/并发、秘密负例及最大数量/字节；Root actual17项审计/新启动/稳定观察另行执行。六层：implementation in_progress；unit/contract/security待作者与独审；integration/live/manual尚未运行；frontend/e2e无此slice证明。若新证据改变根因，按真实phase继续修，不扩timeout掩盖。

## 2026-10-17T08:26:26+08:00 · 冻结兼容性精确补录

对比对象分开：当前安装CORE37ffe/OPS810到新CORE6b86只1项entry变化、19项原字节保持；相对旧d1ce冻结已有controlled_supervise.py、windows_actor.py、ops/configuration.py、ops/stop_owned.py四项更早审查变动，本CR仅新增第5项core/deploy_runtime_entry.py，不把旧74守卫的已有失配叫作本次全新问题。原其余16项精确清单如下，本CR授权其中entry新增诊断，其余15继续原字节：

- reports/runs/recovery_r06_activation_prep_20261016/candidate/core/authorization.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/core/guard_observability.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/core/runtime_limits.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/core/stop_controller.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/core/deploy_runtime_entry.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/core/runtime_controls.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/core/owned_stop_watcher.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/core/task_fence.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/core/run_binding.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/ops/source_entry.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/ops/guardian.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/ops/minio_segment.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/ops/stop_minio.py
- reports/runs/recovery_r06_activation_prep_20261016/candidate/ops/launch.ps1
- reports/runs/recovery_r06_activation_prep_20261016/candidate/ops/windows_preflight.ps1
- reports/runs/recovery_r06_activation_prep_20261016/candidate/ops/minio_controller.py

候选20源清单原SHA8021c07b6741307577264c336d214f550c3287bdd1bda10c84f0e37188e8cfac，source6b86f43e34f3ab406cf8136c7106c7f340fc198d，材料5e81224bb638c2ce74f45278333be7af6e2a7d15。诊断有限键空间11阶段×3状态：每generation最多33final与33pending，最大66KiB；正常21final。write/link失败保留pending且禁止继续/覆写ready。原74真实71通过/3失败，新增精确freeze4/独立native4另列，非旧74green。新非作者必须核对本补录与旧记录差异及此前package授权，不承担OPS新pin/新helper/真实安装或15秒ready放行。
