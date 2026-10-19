# R10-owned-neo4j-runtime-fix1 · CAP_KILL 与同卷恢复

状态 `awaiting_review`，本修复实现 `complete`；guard unit、合成权限对照、有限资源 integration/live smoke 与实际 graceful shutdown `passed`。Must1 的独立关闭仍等待原非作者 reviewer，未签资源安全门、整张 R10、R20、G-C 或 accepted。运行管理已交回 root，未 commit/push，未改业务、公共合同、依赖锁、迁移、progress、计分或盲测。

本轮 checkout 为 `codex/full-delivery-recovery@5b29b3e8c6ea1d10ca50cf2d2006f8460b53253c`。读取原项目规范、执行索引/架构/运维/恢复 R10 卡及当前状态；继续应用 Ponytail full。唯一问题依据是非作者初审 [G-C-R10-owned-runtime-review-1](D:/wt/r10-owned-runtime-review1/reports/reviews/recovery/G-C-R10-owned-runtime-review-1.md)，实际 SHA `65ab2924982e2dcb27c90e2dea27fd4d50dc23a5f02f8f1a73ff869b4b3ec330`，review evidence commit `f76caefe10d357798986e8b0eff07a020b6455f6`。该初审证实五能力 0xcb 跨 UID TERM 得 EPERM，单添 KILL 的 0xeb 成功；没有把原 Docker stop 0/container exit 1 当作优雅停机。

## 边界、原封包与变更

只新增本报告与 `reports/runs/recovery_r10_owned_neo4j_runtime_fix1_20261016/`；外部 ops 为 `/tmp/dianzi-r10-neo4j-operations-fix1-20261016`、Windows cache 为 `D:/dianzi-runtime-cache/r10-neo4j-operations-fix1-20261016`。新 runtime 从已审 core 的窄 helper 复用，去掉本次不需要的 pull、首次创建、旧修复 CLI，只保留固定实例的监督/guardian/身份检查/stop。没有修改正在运行的旧 core、原作者报告或原 manifest。

08:23 操作前逐项核对原 manifest `614305594e9f5073511aaaed4396fc247045a350f5b9200e98d74979813342a6` 的 **143 个成员** bytes/hash 相等，见 `original_seal_proof.json`。原停止会更新的四个 named lifecycle 成员先逐字节存入 `original_live_lifecycle_before_switch/` 并记 hash：termination.json 与 stop_supervisor_signal_15 的 command/stdout/stderr。原 143 封包另有 reviewer 的冻结 input tree；允许的 live lifecycle 更新不覆盖原报告、manifest 或源码。原四能力 FOWNER 启动错误、旧 CID 心跳误停、五能力 tini EPERM 红证据全部保留，没有改写历史 exit 或连续窗口。

业务作者与 root 均明确给出无写窗口 ACK；其全部 Neo4j 写入/查询结束后才 stop，ACK 在 `business_window_ack.json`。工具源码先于资源 mutation 冻结在 `tools_preparation.json`，frozen_at **08:23:10.042767+08:00**。原 core SHA d78da438… 不变；新实际运行 core SHA **261968fab9be60733d4d2043b05926c0be3805b5741bd495252a7f78a9bf7179**。

只加第六项 `CAP_KILL`；能力集合精确 CHOWN/SETUID/SETGID/DAC_OVERRIDE/FOWNER/KILL，drop ALL 后显式加入。官方镜像仍 `docker.io/library/neo4j@sha256:57ecb62bbb0c41c98fb69e08ee014c959926f3bd16ee8ef466c4a1e298f6157c`、Linux/amd64，没有新 pull、升级或替代组件。使用的环境字段沿用已核 [Neo4j 5 配置](https://neo4j.com/docs/operations-manual/5/configuration/configuration-settings/) 和 [Docker 变量变换](https://neo4j.com/docs/operations-manual/current/docker/configuration/)；usage reporting 明确 false。KILL 的信号用途见 [Docker capabilities](https://docs.docker.com/engine/containers/run/)、[Linux kill(2)](https://man7.org/linux/man-pages/man2/kill.2.html)。Community GPL v3、root 安装的官方 driver 6.4.0 Apache 2.0 均沿用，没有许可或 dependency 变更。

## 真实代际切换与当前身份

旧 CID `c0d49f69954c9d7b5d3ab0420347b99d96e9fdbeaf87ece3032b8c3430cd41ab` 先核原 stop --check、creator、boot、mount/卷 inode、supervisor/guardian/tini/Java 创建身份及当时内核四限额。原 supervisor 收 TERM 后停止旧 CID，实际 FinishedAt **08:23:30.910666+08:00**、exit **1**，08:23:35 确認 Running false/Pid0 与所有旧进程身份消失。这个旧五能力失败没有改成成功。随后仅 `docker rm` 精确已退出旧 CID，无 force、无删卷；名字及两个回环端口确已释放后 create 新 CID。

当前 name/resource ID 仍 `dianzi-r10-neo4j-test-20261016`；CID 为 **2cbf8058a220f4b3bc0d4da779f06ddaa314f7a87feeac32ab64b18d0735bf99**，创建时间 `2026-10-16T00:23:37.140365729Z`；creator 仍 `1c406c2c-8349-48ed-af73-482936223968`，boot `8ee1634d-0b2e-4279-8426-2ae855e3b997`。新增固定 runtime_generation `r10-owned-runtime-fix1-20261016` 标签与心跳字段。卷仍 `dianzi-r10-neo4j-test-20261016-data`，inode **701675**，原 mountpoint/data 未删或重建。

新 CID 首次段 started_at **08:24:10.277562+08:00**；实际停于 **08:25:31.682788+08:00**。同一新 CID 恢复段 started_at **08:25:58.274807+08:00**。所有段独立记录，不拼成连续运行。原不可续期 deadline 仍 **2026-10-16T19:35:43.312788+08:00**，从首次 07:35:43 准备最多 12 小时，未重置或延长。

08:27 当前 supervisor PID12505/startticks2877274、guardian PID12518/startticks2877323、tini PID12562/startticks2877364；这些是观察值，停止入口仍每次重查全身份，不能按数字 PID 单独操作。六能力 tini CapEff/CapBnd **0xeb**，Java UID/GID7474、CapEff0、CapBnd0xeb；NNP1/seccomp2、容器与宿主 PID namespace 不同。Java owned listener 仅 IPv4-mapped **127.0.0.1:27687 / 27474**。

HostConfig 和内核 memory **1,610,612,736** bytes、memory+swap 同值（swap max0）、CPU1/pids128；heap initial/max/pagecache 各512MiB、transaction3s/lock2s、HTTPS/routing false、usage reporting false、restart=no、日志10MiB单文件。未变其他 caps、host PID namespace、daemon、端口、卷、密码或 WSL 资源。

## 实际停机与同卷 sentinel

先用 driver6.4.0 真实认证及 11 设置验证，再创建一个参数化 `R10RuntimeFixSentinel`，限定 `runtime_key=r10-owned-runtime-fix1-20261016` 与新 CID；写前 count0，写后 counters.nodes_created1，没有修改任何业务节点。

08:25:24.853539 向匹配的自有 supervisor 请求 TERM。实际 `docker stop --time 15` 命令 exit0，时长 **5.650104 秒**；容器 exit0、OOMKilled false、Running false/Pid0，所有同段 owned 进程身份消失。新 CID 日志有 Neo4j **INFO Stopping... / INFO Stopped.**，没有 FATAL tini 或 Operation not permitted；因此这次 `graceful_shutdown=passed`，依据不只是 Docker exit0。实际检查在 `graceful_stop.json`、`graceful_verified.json` 与脱敏启动/关闭日志。

在 graceful 验证通过后，仅同新 CID 一次 restart。08:27:12–14 读回同卷 sentinel，payload 匹配；随后仅删除此 owned 节点，counters.nodes_deleted1、remaining0。业务图/PG 真值、模型、来源、其他 namespace 均未查询或修改。没有把这一 sentinel 当作正式备份恢复或完整业务恢复演练。

一次内部通信误写 stop 耗时3.999秒，读取 receipt 后立即向 root 明确更正为 **5.650104**；JSON/日志从未记录3.999，报告只引用真实值。

## 命令、数量与结果

完整 argv/cwd/timeout/起止/exit/raw stdout/stderr 在新 run 同名 `*.command.json`。Windows driver使用 root `.venv`，没有 pip/锁修改；Linux标准前缀为 `wsl.exe -d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_fix1_20261016/`。两次实际 `Start-Process -WindowStyle Hidden` launcher 的 null exit 表示后台 supervisor 仍运行，不是完成退出。

| 检查 | 实际 +08:00 起止 | exit / 数量 | 事实 |
|---|---|---|---|
| 原 guard | 08:19:46.281–46.714 | 0 /14 | 原案例与失败边界保留，仅 fixture 新增代际字段 |
| 独立 guard | 08:19:46.854–47.683 | 0 /17，0skip | 原13 +新4：伪owner、旧runtime、旧supervisor、旧代际；JUnit留存 |
| synthetic_signals | 08:19:47.816–48.052 | 0 /3 | 独立自有短命子进程 cb→EPERM/eb→成功/同UIDcap0→成功，真实服务信号0 |
| Ruff/format preparation | 08:23:00–07 | 各0 | --no-cache；修复工具在真实mutation前冻结 |
| 同原DPAPI auth staging | 08:23:22–23 | 0 | 原密码/截止保留；新700 ops、临时600 envfile，create后删除 |
| 原封包核验+单次CID switch | 08:23:25.668–37.634 | 0 /143 | 旧身份/内核/进程结束核验、精确rm、新cap6 create同卷 |
| 新段HTTP/auth/kernel/stop check | 08:24:37–51 | 各0 | 真实5.26.32/community/Bolt5.8、usage=false、maskeb与原限额 |
| own sentinel create | 08:24:53.841–55.631 | 0 /1节点 | 参数化写，仅own namespace |
| graceful stop probe | 08:25:24.043–35.059 | 0 | docker0/container0/所有旧代进程消失 |
| logs actual-secret scan / graceful validate | 08:25:50–53 | 各0 | 完整Neo4j关闭、无tini错误、5.650104秒<15 |
| sameCID restored launch | 08:25:56 / started08:25:58 | launcher0 | 同卷、同密码、同旧deadline，新PID代际 |
| 恢复HTTP/auth/kernel/stop check | 08:26:56–08:27:09 | 各0 | 再次真实认证/11设置/限额/权限/回环监听 |
| own sentinel recovered+delete | 08:27:12.311–14.422 | 0 | payload matched、只删own1节点、remaining0 |

31 guard（原14+原13+新增4）是资源边界单元，3合成例是权限诊断；不重复累计复跑，不计为 R10 业务测试/关系质量/正式 live 性能。root与业务作者已收到新稳定资源 ACK；业务作者的125业务/probe通过属于其固定材料，不由本报告代签。

准备仪器的真实红：一次 PowerShell/Python -c 引号导致 SyntaxError、两次 apply_patch 上下文不匹配，均发生于 resource mutation 前；原 Ruff I001 与 sentinel 嵌套 with SIM117 exit1 日志已保存并修正，没有降低检查。所有 live 功能检查首次执行通过，没有第二次同根因重试或扩大 caps。Windows pytest本人新建的 __pycache__ 经绝对路径、非链接、创建时间、仅pyc内容核验后移到外部 owned cache，见 `owned_instrument_cache_move.json`；Ruff全程 --no-cache，无全局忽略。

## 秘密、缺测与交接

仍只有原当前用户 DPAPI `D:/dianzi-private/r10-neo4j-test-20261016.dpapi`，字段 NEO4J_TEST_BOLT_URL/USERNAME/PASSWORD/resource_id/deadline，只在内存解密；Neo4j username/database固定 neo4j、URL bolt://127.0.0.1:27687。没有生成第二密码、秘密别名或供应商key，没有打印配置/Config.Env/full inspect/凭据。原始日志仓外，公开日志先扫描/脱敏；最终 actual value/指定编码形式扫描覆盖新report、named raw日志、JUnit与新制品，结果见 final seal。0模型/付费调用。

当前停止入口改为：`wsl.exe -d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_fix1_20261016/runtime.py stop --check`。去掉 --check 才是提前停止当前精确新 CID。旧入口引用已移除旧 CID，必须 fail closed，不应再使用。监督/guardian保持5秒轮询、原45秒心跳门、双时钟截止；心跳同时绑定 CID/creator/boot+supervisor PID/startticks/runtime generation。当前服务真实在有限 deadline 内运行，没有会话外工作承诺。

缺测仍为未来原deadline实际收尾、最终版 guardian/supervisor故障注入、daemon/宿主掉电、正式全库备份空环境恢复、完整R20与完整R10/G-C。资源边界与本次关闭/恢复是 E1/R2 的有限证据，不能替代 A1/F2/P2 业务、阶段门或 T54 连续观察。合同与评分分母未变；新增cap和一次CID切换均有root明确授权。下一动作由原非作者 reviewer 对此新工具/manifest/CID定向复核，root独占后续运行/Git/进度管理；本执行者不自行提升 accepted。
