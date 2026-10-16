# R06 · 固定 Product912 第二次真实启动只读诊断

本轮 reports-only；Root 状态仍为 `needs_changes / partial`，未修改任务状态、实现、installed controls、依赖、gates、数据库、账本或秘密。应用 diagnosing-bugs 的证据分类及 Ponytail 的最小探针原则；已读执行地图、R06 恢复卡、任务状态、交接、九脚本/failed-bootstrap/native snapshot 变更合同及第一次诊断。

**已证明的直接失败是首个 worker 在 15 秒内未发布 ready 身份；尚未证明它停在哪个 ready 前阶段。** 新类型化收据已经排除“只知道 RuntimeError、不知道 timeout 或 exit”的旧信息缺口。这次没有证据把失败归为首次缺 `langchain_core`，也没有证据把快照的 100ns→microsecond 转换登记为缺陷。三个冷进程的独立离线前缀测试没有复现超过 15 秒的单进程阻塞，但不覆盖历史并发、真实配置加载及 PostgreSQL 阶段；因此不宣称根因已完全关闭。

## 固定对象及实际失败

| 对象 | 亲读身份 / 实际字段 |
|---|---|
| Root / Product | `3fd9cd68f292afcd1b88ca55f218c4e869e8f706` / `912d8b381eaab9260ead30d68f49b88fa8078384` |
| Product checkout | `D:/wt/r06-product-912-runtime-20261017`；rev-parse 正确，tracked status clean |
| 实际 CORE / OPS | `37ffe6da1d9a258359363d42488d236b7c00ad87` / `81053fd680dbfb275bfcc511ae44f573340efd56` |
| Actual binding SHA256 | `9e3066565a0fe45fed58574a77baee0e9492651baa3ed953a610abe2b5b5e8fd` |
| Observation | `3233d991ff8b47f78116d112fed4c818` |
| source / worker launcher | source45388 / birth134366654864337020；worker22240 / birth134366654894972549 |
| 实际墙钟 | `07:04:46.381897–07:05:04.712013+08:00`，18.330116秒；guardian reason `source_owner_exit` |
| 启动失败 | `RuntimeError / ready_timeout / actor_ready_wait / role=worker`；`actual_phase=unknown_before_ready`、`actual_identity=null`、`registered_roles=[]` |

失败收据记录 API47428、worker22240、beat46508 的 launcher poll 均为 null。API/worker/beat 三日志及 supervisor stdout/stderr 均为0字节；CORE/control、runtime_start、runtime_end、observer.log 均不存在。日志只读取原位置进行大小/hash/静态异常 token 分类；未复制或输出 raw traceback、SQL、环境、cookie、key。保存记录中的“仍运行 launcher”只限定超时分支，不能补造 actual interpreter PID/birth。

`controlled_supervise.py:321–331` 在完成三个 Popen 后设置固定 15 秒 deadline，按 worker→beat 等 ready 文件；worker 首先超时。`333–344` 只有文件存在后才读取 ready receipt、登记实际身份、构造 WindowsOwnedActor。observer 的 `348` 行尚未执行。`563–582` 发现 worker/beat 仍在运行且未登记，写 `owned_stop_failure` 并终止自有 Job；`actual_actor_stop=[]` 是没有已登记角色，不是 producer ACK 成功。

## 关闭证据的实际范围

guardian_end 有 `actual_source_kernel_exit_ack=true`、`source_job_kill_on_close_required=true`；同时明确 `descendant_exit_confirmation=requires_final_actual_kernel_check`。因此 source 的 held exit ACK 不能替代 worker/beat 实际对象及后代关闭核查。`owned_stop_failure` 仍为 `observer_terminal_guaranteed=false`，不能写成正常停止、observer 终态或干净 namespace 已独立证明。

MinIO 结束于 `07:05:04.542313`，exit0、pidfd ACK true、cleanup/descriptor error null；controller 结束于 `07:05:04.565115`，target_inode26071、target_empty=true、helper pidfd ACK true、whole_tree_cleanup_guaranteed=true、error_types=[]。这是已有保存回执。本轮没有执行 WSL、同 boot/inode 的 fresh kernel audit 或停止任何原 PID；Root 的恢复合同仍要求另外取得新鲜关闭证明。本轮四个离线探针自身的 remaining_owned=0/held ACK true，只证明这些探针清理，不证明原 Source 的后代关闭。

## 两个候选及反证

1. **出生时间第七位截断不是这次 timeout 的解释。** `windows_actor.py:49–50` 的快照确输出微秒；launcher211–212、descendant241、actor259、parent323–324的 snapshot 比较均在两边 `//10`。held identity195/253保持完整100ns比较。实际 worker ready 的 `owned_stop_watcher.py:109–114` 直接从 GetProcessTimes 生成整数身份。尤其本次尚未进入 WindowsOwnedActor 构造、control 目录未生成；不可能由其后置 snapshot 比较把 ready 文件等待变成超时。未新增“精度缺陷”、未修改原断言。
2. **冷导入/重复 Git 核验是可测成本，历史因果仍未证明。** worker/beat 的共同 ready 前路径是 Celery CLI → verify_live_binding → 产品 database/settings 导入 → settings 校验 → service URL/PG 只读验证 → watcher mkdir/publish。单独新 Python 进程测得该前缀到配置拒绝约6秒，当前 binding Git 核验约2.5–2.9秒。API fixture 导入约7.7–9.8秒。原三进程同时启动、Source Job 的实际 CPU20% host/2GiB 与本轮探针2CPU/1GiB不同；不能用此时长签原并发15秒通过，也不能据此断言原并发必然超时。
3. **真实 settings/PG 阶段仍未观察。** `deploy_runtime_entry.py:36–52` 完成配置加载、连接、事务只读声明与两条身份/版本读取后才发布 ready。原日志无这几处 phase receipt。本轮不读取实际 secret env，不建立数据库连接；不能以未测替换成“PG 正常”或“PG 是根因”。若仍需修复，应先补齐能区分这些阶段的证据。

目录缺失进一步限定故障位于 watcher mkdir 之前；它不证明某一个更早的函数已卡死，也不能排除历史并发启动压力。产品 `workers.runtime` 的导入在 ready 发布之后，不能用其潜在导入成本解释本次没有 control 目录。

## 真实命令及结果

自有目录 `D:/dianzi/reports/runs/recovery_r06_second_912_start_diagnosis_20261017`。Root 明确批准三个独立≤60秒 offline 组；API 同组因 hook 异常被库吞掉做了一次边界复核，两次外层合计19.297秒。没有超时后重置预算或拼接为 live。所有探针使用原 runtime_env 解释器、固定 Product912 和已安装 CORE，外层执行器复用既有原生 Job 实现。继承环境按平台白名单清除，再显式设置 test/fixture、不启用 source/generation；hook 拒绝秘密/.env/KEYS/holdout读取、connect/bind、非只读 Git 子进程；`load_owned_application` 在49行引擎创建/数据库/ready边界前强拒绝。

精确通用命令：

`BASE -B OWN/run_owned_offline.py LABEL OWN/cold_entry_smoke.py ROLE`

BASE 为 `C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe`，OWN 为上述自有目录。实际 child argv 为 `D:/dianzi-runtime-cache/r06-live-restart-20261016/runtime_env/.venv/Scripts/python.exe -B OWN/cold_entry_smoke.py ROLE`，实际 cwd 固定 `D:/wt/r06-product-912-runtime-20261017/backend`；每项完整公开 argv/hash/时间/资源在对应 command.json。

| LABEL / ROLE | +08亲跑起止 / outer wall | child exit / wrapper exit / 结果 | 完整 Windows 观察峰 |
|---|---|---|---|
| cold_worker / worker |07:11:40.188109–46.670628 /6.485s|2 /1；fixture配置明确拒绝，非ready成功；inner6.031s|8/10|
| cold_beat / beat |07:11:51.561954–58.389058 /6.828s|2 /1；fixture配置明确拒绝，非ready成功；inner6.437s|8/10|
| cold_api / api，原仪器 |07:12:12.447087–20.998402 /8.563s|0 /0；导入返回，但hook记录一次bind被吞，不能计纯offline通过|6/10|
| cold_api_boundary_retry1 / api |07:13:22.054304–32.774566 /10.734s|2 /1；显式unsupported_offline_operation_caught_by_dependency，inner9.781s|6/10|

API bind 已由源码定位为 `urllib3/util/connection.py:114–137` 的 import-time `_has_ipv6('::1')`：127行尝试bind本机端口0，129行 `except Exception` 捕获拒绝。不涉及外部连接；不为让 smoke 变绿放宽 hook。原exit0、原JSON和第二次拒绝均保留；初始API JSON另存 `api_cold_entry_initial.json`。worker/beat的实际库导入及固定 binding 核验没有缺依赖异常，但真正 live PG/ready 后链未跑。

执行器原生亲核：512MiB/process、1GiB/Job、active_limit10、24逻辑CPU×rate833=约1.9992核、KILL_ON_CLOSE true；每组 native usage active1仅执行器，remaining_owned=[]、child held kernel ACK true，stderr0字节。完整工具祖先另做有界只读采样；它们不全部属于这个 Job，不把 Source 的20% host/2GiB限制与探针限额混称。

仪器更正保留：原三项 command.json 的 cwd 字段继承旧 helper 的元数据笔误写 Product 根，实际 Popen 源码始终为 ROOT/backend；第二次API的 child `os.getcwd()` 已亲核 backend。原收据不覆写，封存 manifest 单列其实际 cwd 和更正原因。最初一条 PowerShell foreach 管道语法错误exit1、一条CRLF精确文本替换找不到exit1均发生在探针启动前，不计业务失败或通过。

其他亲跑：`BASE -B OWN/collect_readonly.py` exit0，6份失败/生命周期回执和8份日志分类，确认保存的 worker ready_timeout；这不是再次 live 复现。Product rev-parse/status exit0/0，clean。普通只读 rg/Get-Content exit0；错误目录查找/无匹配的rg非零只属静态检索。封存器检查20安装源码、14原失败/日志文件hash保持及6份仪器Python语法，不生成pycache；具体结果见 artifact_manifest.json。

## 最小方案、缺测及交接

本轮没有修改公共合同、冻结控制源码、固定15秒、资源/六小时/预算/分母/算法。只新增本文与自有仪器/脱敏证据；无Git提交/push/accepted、无Source/WSL/PG服务启动、无模型/付费调用。单位/合同/产品integration/live回归均未运行，新增业务测试0；两个真实短段都失败，完整同版本21600秒仍未开始。

当前最小下一步是先由 Root 按恢复合同完成新鲜实际 kernel closure；然后以新的冻结诊断切片在 `deploy_runtime_entry.load_owned_application` 加少量固定 phase 字段，覆盖授权核验前后、产品基础导入后、settings后、PG connect/身份校验前后和ready发布，保持所有原身份/文件/15秒门与秘密边界。只写静态阶段、角色、精确自身PID/birth与时刻，不写异常message、SQL、DSN或环境。该入口目前属于“其余十六份源码原字节保持”的冻结范围，因此新增这条路径需 Root 明确变更记录与新的非作者精确冻结审查；本报告不擅自修改。

如果新的实测定位到导入或重复核验，可以在相同身份和验证语义下做具体最小优化；若定位到PG，则修真实可复现的连接/校验路径。不先加长ready、不调整资源，也不再重复安装已审依赖。当同根因连续两次补丁无进展时停止扩补丁、交根因与最小复现。R06/E1/F1/P1仅新增故障证据，不换算为评分通过；未知实际阶段与未观察到的actual actor身份继续明确保留。
