# R06 · 固定912首次启动独立诊断

本轮为 reports-only 只读诊断；R06 保持 `needs_changes / partial`，不改状态、不写 accepted。2026-10-17T03:37:31.7037003+08:00 已读取本地时钟；诊断进程核查实际为 03:41:46.124402–03:41:47.238158+08:00，依赖最小复现为 03:42:01.946491–03:42:01.987581+08:00。此前逐项工具结果以实际 exit/wall 为准，未补造未记录的开始秒。

**已证明的部署根因：真正 launch 的 Python 环境仍是旧依赖包，未覆盖固定 Product912 的依赖闭包，API 因缺少 `langchain_core` 在 import 阶段退出。** 同时，外层 `supervisor_error_RuntimeError / actual_actor_stop=[]` 已定位到首个 worker 的 ready 身份交接尚未完成；现存收据无法区分其 15 秒超时和 launcher 提前退出。不能把 API 缺依赖直接宣称为这条 ready 异常的唯一共同根因，也不能宣称补齐依赖后已通过五 actor 启动。

已读 AGENTS、执行地图、R06 卡、状态、CR-R06 的九脚本绑定/预持收尾合同及 fix5 独审；应用 Ponytail 5.3.1 review。fix5 仅签固定 Source/资源的激活前置条件，正文明确首次五 actor、全部连接峰值、停止 ACK 和 observer 终态属于随后运行，不能把此次失败倒推为独审已签 full runtime。

## 固定对象和原始失败

| 对象 | 本次固定身份 |
|---|---|
| Product / clean checkout | `912d8b381eaab9260ead30d68f49b88fa8078384` / `D:/wt/r06-product-912-runtime-20261017` |
| CORE / OPS source | `984c270a6240140a82acf875061e9d31d3201d39` / `3c27d6e00a4d31b0821e171bf431fc3ffeaef8fc` |
| material | `d1ce4c26b7abb8749470af82d48bdd498f18e6cc` |
| actual runtime SHA256 | `2a32f6ac2a817c18e2018cafc53f6ea2e39b23684c2772dc094789478a8e6158`，03:42:04 再核未变 |
| 累计 ledger SHA256 | `2604347a4559d3353a045a57393ea632f90ba74fd2c98615400751672e0d03b9`，未 reset/改写 |
| 新库 / OID | `test_dianzi_r06_912_20261017_f15191e6ea74` / `10451302`，本轮不连接、不修改 |
| 原 RUN / nonce | `r06_nine_script_20261016` / `ea89c345e404475d94de02cbe67874e3`，未改 |

Root 启动材料保存在 `reports/runs/recovery_source_912_start_20261017`。本次实际 OPS guardian_start 记录 03:34:02.196146+08:00；guardian PID46012、source launcher21340、actual source43976 / FILETIME134366528422524978。guardian_end 于 03:34:22.012818，reason `source_owner_exit`、actual source kernel exit ACK true。MinIO 于 03:34:22.436294 结束，reason `owned_stop_or_collector_end`、exit0。所有 formal_six_hour_pass 为 false；这不是六小时成功，也不拼接任何旧段。

CORE/control 目录、runtime_start.json 和 runtime_end.json 均不存在。API 日志3598字节；worker、beat 和 supervisor stdout/stderr 均0字节。原始日志未直接打印；仅在本地抽取异常类型、模块文件/行号、已知静态 reason 和白名单生命周期字段。

## 1. 必须修复：实际启动解释器缺少锁内依赖

实际 OPS `launch.ps1:4` 固定使用 `D:/dianzi-runtime-cache/r06-live-restart-20261016/runtime_env/.venv/Scripts/python.exe`（3.12.13）；独审 fix5 执行检查使用 `D:/dianzi/backend/.venv/Scripts/python.exe`。launch 的 PYTHONPATH/cwd 已指向正确912产品，但这只替换业务源码，没有替换该解释器的已安装依赖。

API 白名单 traceback 为 `api/app.py:31 → investigation_routes.py:46 → investigation/runtime.py:11 → workflow_service.py:20`，最后一项为 `from langchain_core.runnables import RunnableConfig`；实际错误类型 `ModuleNotFoundError`，missing module identifier `langchain_core`。实际解释器纯 `find_spec` 对 langchain_core/langgraph 都为 false；直接 `import langchain_core` 在没有应用导入/网络/数据库连接时再次得到同一异常。

运行环境 pyproject 比912 pyproject 少以下七条直接依赖，实际 distribution metadata 也全部不存在：`packageurl-python==0.17.6`、`pyyaml==6.0.3`、`neo4j==6.4.0`、`mcp==2.3.0`、`tiktoken==0.14.0`、`langgraph==1.2.15`、`langgraph-checkpoint-postgres==3.2.0`。langchain_core 属于 LangGraph 依赖链，不能用删除产品导入、替换算法或忽略异常来规避。

最小修复是让实际 launch 解释器的依赖安装来自固定912的 pyproject/uv.lock，保持锁中版本及产品/控制源码不变；先核库存缓存与完整依赖集合，再在已授权的 runtime 范围同步。补齐后，用同一解释器、同一产品 src 路径做不建立连接的模块 smoke，并记环境 manifest/lock 与 installed distribution 证据。此前“主库 .venv 能导入”不能替代这项核查。本诊断未安装包或改 launch。

## 2. 必须区分：首个 worker ready 失败的信息被截断

实际调用链为 OPS `guardian.py:60–68` Popen source_entry → `source_entry.py:18,38–41` runpy 装载 CORE supervisor 并调用 main → `controlled_supervise.py:234–250` 先 Popen API/worker/beat → `251–255` 等待首个 worker ready。worker/beat 都通过 `-A deploy_runtime_entry:celery_app` 导入同一入口。

两个角色在 ready 前共同执行 `deploy_runtime_entry.py:21–52` 的授权、产品 database/settings 模块导入、配置/URL和 PG 验证，随后 `53–56` 安装 watcher；watcher `owned_stop_watcher.py:109–114` 才创建 control 并发布 ready。`deploy_runtime_entry.py:58` 的产品 workers.runtime 导入发生在 ready 发布后，因此它的潜在缺依赖不能解释本次 control 目录都未产生这一事实。

supervisor 的角色顺序为 worker→beat，两个角色共用从全部 Popen 后起算的15秒 deadline。`controlled_supervise.py:254–255` 把“worker launcher 已退出”和“ready 超时”合并为同一个 RuntimeError；`437–438` 又只留下异常类。正常 ready receipt 合同已检查整数身份；成功登记首个 actor 后 finally 至少会产生一条 stop receipt。因此 actual_actor_stop=[] 与 control不存在将事件限定在首个 worker ready/登记之前，不能解释成 WindowsOwnedActor 身份拒绝（该类异常为 OwnershipError）。

授权校验也位于共同 ready 前链：run_binding:784 的 frozen 核查先执行两个 checkout 的 rev-parse/status，再逐项20控制 Git blob及3 observer blob。两个 Celery进程与API在 supervisor 的20% host CPU Job内共享启动预算。**这是需要复验的超时条件，不是已证明的历史根因。** 本轮单个未置于原 Job 的只读 verify_live_binding 实跑2.312秒、passed；没有据此推算或宣称原并发三进程能在15秒完成。

最小补充在 `controlled_supervise.py:254–255,437–438`：分别保存固定 role、launcher PID、poll/exit状态与 `ready_timeout` 或 `launcher_exit` 的静态原因，异常只记类型/静态源码 phase。若仍未到 watcher，入口可用少量有界阶段字段记录 auth/import/settings/PG-validation/ready；不要记录 DSN、环境、payload 或任意异常 message。保持15秒、身份检查和全部原资源限制；这是补诊断字段，不是新增运行框架或放宽验收。现存原收据无法恢复首次进程栈/phase，这个缺口必须保留。

## 实际命令、结果和证据

ownrun 为 `D:/dianzi/reports/runs/recovery_r06_first_912_start_diagnosis_20261017`。仅新增本文和 ownrun 仪器/脱敏证据/公共源码副本；未改代码、状态、installed controls、秘密材料、数据库、历史原文、cursor或队列。

| 实际执行 | exit / 实际结果 |
|---|---|
| 静态 Get-Content/rg，沿上述固定模块读 caller | 0；源合同与错误分支定位，部分“未找到文件名”的rg exit1仅属查找无结果 |
| 实际 launch Python `-B` + stdlib/importlib.metadata/find_spec | 0；七直接 distribution missing，langchain_core/langgraph false，celery/uvicorn true |
| 同实际 Python `import langchain_core`，在本地捕获类型 | wrapper0；真实 import failed / ModuleNotFoundError；业务测试0，不伪称成功启动 |
| 实际 launch Python `verify_live_binding()`，只FS/Git | 0；passed，2.312秒；未连接PG/Redis/来源 |
| 主库 Python `-B diagnose_readonly.py` | 0；15条白名单证据，control/start/end均不存在 |
| 主库 Python `-B check_process_identity.py` | 0；03:41:46–47 Win/WSL只读进程核查；记录的5个WinPID均不存在，Win scope0/WSL scope0 |
| 官方 portable CBM v0.11 `cli --help` | 0；先亲核help，不运行daemon/service |
| `-B cbm_readonly.py` 的官方 cli --json index/schema/query | 0/0/0；12.312秒；20公共控制源码，303nodes/1381edges；windows_preflight.ps1 13/15/16行 partial1保留，未称全解析 |
| Product912 `git status --porcelain=v1 --untracked-files=no` / rev-parse | 0 / 0；clean，HEAD912d8b381eaab9260ead30d68f49b88fa8078384 |

CBM 使用外部独立cache，索引自有目录内复制的11 CORE+9 OPS公共源码；未索引任何日志、JSON、env、secret、holdout或其他用户材料。动态 runpy/Popen 调用由上述源码 rg 实际补核。该窗口 Root授予独占cap16；完整Win scope peak6、Linux scope peak2，保守总8≤16；Linux descendants after0，Windows WSLwrapper wait ACK true/exit0，独占已归还。普通只读进程检查没有继续服务。

进程证据不夸大：guardian46012/source_launcher21340/actual_source43976/guardian_launcher27652/minio_wsl_launcher9228均已不存在；全Win/WSL命令行仅在本地匹配已知scope，未输出命令行。API/worker/beat尚无 ready 身份收据，故其 exact PID+birth 无法在本轮恢复；MinIO cgroup events0/inode 的最终独立实核没有执行，end字段与“未找到scope进程”不能替代该kernel验证。

| 原失败文件 | SHA256 |
|---|---|
| CORE/api.log | `697d693b813d8a58d460d3ba7ce706566b94d1388d53e513c9c4b2d254f07539` |
| CORE/owned_stop_failure.json | `b5ddc7afa825e234e4a7db70f0a48d3aea8f1e7bd7f7ab6493e9f6e7d1557ace` |
| CORE/worker.log、beat.log，OPS/supervisor.stdout/stderr.log | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0字节） |
| OPS/guardian_start.json | `8fd6aed5b79eb75a68ef21e221fb669b4fbe30a585e311ffc5e26b951b8700de` |
| OPS/guardian_end.json | `24fc7fe6f68aed3327f8da5b7a235c7b553f8689d338186a43d6a2af2d7383df` |
| OPS/minio_end.json | `aae4131fd3056009f75ad837e62fcf01f0449e160831ff4030f40931d4630e65` |

完整白名单文件/hash在 sanitized_actual_evidence.json。原日志字节保留；没有读取附录KEYS/.env、秘密文件、holdout，未下载模型/调用paid/浏览器/扫描第三方。

## 未验证、影响与交接

unit/contract/产品integration未运行；新增业务测试0。live 首次启动实际失败，完整五actor、真实Source消费、全部连接峰值、停止ACK、observer终态和21600秒窗口均未通过。本轮没有建立PG/Redis/外部HTTPS连接，费用/模型调用0。R06/F1/P1/E1仍存在真实运行缺口；本文是部署故障证据，不能换算为评分通过。

合同/计划偏差：无阈值、分母、算法、身份/权限或公共合同变更。未扩大patch，未推送/提交、未accepted。当前库和历史42/450 ledger继续保留。

下一步建议：Root按已授权范围固定912锁内运行环境，独立核实际解释器的无IO模块smoke；先亲核本次终态/自有cgroup身份，保留失败材料，再按原 restart合同准备下一 observation。若再次 actor-ready失败，必须取得分开的timeout/exit/phase证据再修该共因；不能仅补API包便把未知 ready异常标关闭，也不能将两次修复无进展继续扩大为新框架。正式复验仍需单一同版本真实五actor与完整21600秒，失败即原样记录。
