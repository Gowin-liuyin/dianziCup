# R01-runtime-recovery-20261016 · 第二个异常中断恢复段

状态 `awaiting_review`；实现 `complete`；仅本恢复子包 integration smoke `passed`、静态检查 `passed`。业务 unit/contract/security/frontend/e2e、外部 live、人工验收均 `not_run`。不签 R01/R20 或阶段 accepted，不修改共享状态。执行者 `/root/r01_owned_runtime_recovery_20261016`，无新增子代理。

输入代码和交付观察均为 `c3a2abc9a5246993eabb351d26cfeb51d0270b31`；真实分支为 `codex/full-delivery-recovery`，与委派文字中的 main 不同，未切换分支。初查工作树已有 239 项修改/未跟踪文件，全部保留；未 commit/push。

## 输入输出与文件边界

已读 AGENTS、00 执行索引、09 运维合同、恢复 R01/R20 卡、task_state 的 R01/R20 条目、R01 资源/20261015 恢复及 R20 native CPU 报告、旧 recovery/restore/verify 和实际 launched supervisor。使用 diagnosing-bugs 的真实红/绿探针和 Ponytail 的复用原则。输入为原 owned runtime、持久容器 metadata、原 lifecycle 和根测试连接 JSON；输出为新有界 daemon 段、三个原根测试服务、健康/资源/数据身份/退出管理证据。

仓库写入仅本报告和 `reports/runs/recovery_r01_runtime_recovery_20261016/`。主要文件是复用原安全恢复脚本的 `recover_runtime.py`、限定根项目的 `restore_services.py`、`supervise_recovered_daemon.py`、隐藏 Windows 启动器 `launch.ps1`、原 `probe.ps1`、只读 readiness/verify/windows/exit guard/交付验证脚本，以及命令、日志和 JSON receipts。精确文件清单/哈希见 `artifact_hashes.json`。无业务、progress、lock、schema、迁移、认证、计分或盲测修改。

Linux 仅操作原 `/tmp/dianzi-docker-static-r01-20261014` runtime 的监督记录和失效执行状态、原项目 cgroup、三个旧容器的 start。没有新建容器、拉镜像、重建卷、Compose up/down、读取 provider/DPAPI/.env/附件/生产 DSN，或删除/移动持久数据。唯一秘密输入为原 test-services/connection.json，在内存中用于 Redis AUTH 和扫描本包输出，不输出 DSN/密码。

## 中断证据、恢复与资源

2026-10-16T00:30:31+08:00 preflight 真实 exit 0：当前 boot ID 为 `8ee1634d-0b2e-4279-8426-2ae855e3b997`，旧 lifecycle 的 boot ID 为 `a57bd35b-ffb0-4ad7-b249-77daa5fa5c0d`，旧 supervisor 18/daemon 25 不存在，本 runtime 所属进程为空；socket connect errno 111，无 Unix listener，原项目 cgroup 不存在，持久 metadata 有 17 容器。这不是只因观察超时判停。两 boot 不同证明运行环境发生过重启；触发原因和确切停止时刻仍 `unknown`，不把本次恢复当作停止根因诊断闭合。

00:31:31—32 prepare exit 0，复用旧安全机制：先核绝对路径、非 symlink、所有权和无活进程，再将旧 lifecycle/dockerd/supervisor 日志复制到私有 `/tmp/dianzi-docker-static-r01-20261014/recovery-archive-20261016T003132`；仅失效 PID/socket/exec 归档保存。持久 `runtime/data` 没有移动或清理，inode **392775** 不变。旧 logs 留在 Linux 私有目录，没有导出原始内容到仓库。复制件 hash 和移动件 inode 在 `preparation_evidence.json` 与 `delivery_validation.json` 复验。

新运行段真实 started_at **2026-10-16T00:32:57+08:00**，planned_end_at **2026-10-17T21:49:15+08:00**；沿用原截止，没有新开 72 小时。新 supervisor PID 13、daemon PID 17；分别记录 boot/start ticks/executable/cgroup。Windows `Start-Process -WindowStyle Hidden` 的 WSL launcher PID 48308 在交接时仍活着，不把启动 receipt 的 null exit 当完成退出。

资源仍为项目父级硬限额 **8 GiB memory / 2 GiB swap / 2 CPU / 2048 pids**。root PG/Redis/OS 原 HostConfig 未改，真实 PID→内核 cgroup 的 memory/cpu/pids/swap 逐项一致，父级及其他 sibling 原限额保留。daemon 总日志 cap 10,485,760 bytes；前两段累计 280,699 bytes，本段 cap 10,205,061 bytes，00:35:11 实测 45,263 bytes，预算没有重置。无安装、系统库/ACL/全局 WSL shutdown、用户进程终止或无限扩容。

只对精确原项目 `dianzi-test-r01_20261014` 的 PG、Redis、OpenSearch 三个旧 ID 执行 start。其他 quality/frontend/infra/TLS 栈不在本次恢复集合。恢复前/后 17 containers、28 images、20 volumes 及其名称、labels、mounts、image IDs/digests 完全一致。root PG/Redis/OS volume inode 分别 **408924 / 408926 / 422500**。旧数据被保留；本轮没有创建数据库备份，旧监督日志归档不能冒充 PG 备份或空环境恢复演练。

## 实际验证与失败

全部 commands、cwd、实际起止、timeout、exit、stdout/stderr 文件名在 run 下同名 JSON 和 `commands.json`。主执行前缀为 `wsl.exe -d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi/reports/runs/recovery_r01_runtime_recovery_20261016/…`，专用 Docker CLI 固定原 portable、client-config 和 Unix socket，不用默认 context。

| 检查 | 实际 +08:00 时间 | exit | 观察 |
|---|---|---:|---|
| preflight / prepare | 00:30:31 / 00:31:31—32 | 0 / 0 | 无 owned 活进程、失效 socket、安全归档、保留 data-root |
| start_daemon 首次 | 00:32:06—21 | 1 | readiness 15 秒失败；初版 supervisor 在 spawn daemon 前因旧 PID 18 被新 boot 复用而断言失败，原 traceback 留存 |
| start_daemon_retry_1 | 00:32:56—58 | 0 | 仅在同 boot 解释旧 PID，另检查所有 owned 命令、cgroup/endpoint；server 29.2.0、API 1.53，未杀复用 PID |
| restore_services | 00:33:05—20 | 0 | 三个旧 ID start，running 0→3，资源身份保留 |
| postgres_ready | 00:33:37—38 | 0 | pg_isready 实际 accepting connections |
| verify_health_persistence | 00:35:03—11 | 0 | 三服务 Docker healthy、内核限额、loopback、持久资源标记、只读计数 |
| windows_loopback | 00:35:26 | 0 | Windows 25432/26379/29200 实际连接，OS HTTP200/green |
| docker_help / dockerd_help | 00:35:26—27 | 0 / 0 | 实际二进制 help，专用选项核对 |
| ruff_initial | 00:35:56 | 1 | 一个 unused import 和 supervisor import 排序；不隐藏失败 |
| ruff_fix / format / final | 00:36:05—06 | 0 | 本包限定修正；实际启动字节另存 launched_supervisor.py.txt |
| exit_management_check | 00:36:52—53 | 0 | read-only `stop_owned.py --check` 真实匹配本段 boot、PID start ticks、命令和 cgroup |
| delivery_validation | 00:36:53—54 | 0 | 7 原归档条目、8 Python 源语法、启动源码、秘密输出扫描、当前进程身份 |
| format_delivery / ruff_delivery / format_delivery_check | 00:37:08—09 | 0 | 新 verifier/exit guard 全部格式和 Ruff 通过，8 files formatted |
| live_restore_mode / retry_1 | 00:39:09—10 / 00:39:31—32 | 1 / 0 | 首次 format 字符串漏引号导致 CLI 拒绝参数；正确引号复验 false，无资源变化 |
| delivery_validation_final | 00:39:32—33 | 0 | 归档/8源语法/启动源及94个本包文件秘密值扫描/当前监督进程复验通过 |
| format_seal / ruff_seal / delivery_validation_seal / git_diff_check | 00:40:03—05 | 0 | 含报告在内104文件秘密值扫描、归档与监督进程复验；静态/限定diff检查通过 |

PG 查询每次显式 `BEGIN READ ONLY`/`ROLLBACK`，仅现存数据库/表/测试 marker 计数和测试库身份：**34 个现存 test_dianzi_* 库、37 个 public 表、1 条原 resource marker**；不输出资产、盲测或正文。Redis 原密码 AUTH/PING 成功、旧 resource marker EXISTS=1；OpenSearch **2.17.0 / green**，旧 smoke marker found。所有服务真实 Local Address 为 127.0.0.1；OS transport 29300 也只 loopback。三个根服务端口为 PG25432、Redis26379、OS29200。

本轮没有业务 pytest：业务测试数 0、业务 unit/contract/security/frontend/e2e 均 `not_run`；上述为有限恢复 smoke，不计性能、正式持续采集或外部模型/来源 live。已经保留首次恢复失败与初始静态失败，不将其改为 skip。实际截止到期退出、强制停止/重启回归 `not_run`，避免中断主控/评审正在使用的服务。

## 退出管理、偏差与交接

原监督循环同时检查绝对墙钟截止和对应 monotonic 截止、log cap、显式 TERM/INT 和 daemon exit，并只对本 daemon 进程组 TERM，15 秒后必要 KILL，写本段 ended_at/exit_code。实际 `LiveRestoreEnabled=false` 已核验；截止管理代码存在，但未来到期效果未提前记 passed。需要提前停止时，仅使用本包 `stop_owned.py`，它先核本段 boot/start ticks/命令/cgroup，再 TERM supervisor；`--check` 已真实通过。不要重跑 prepare/launch/restore，不要 kill 仅数字 PID 或全局 shutdown。

原私有连接位置继续为 `/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json`，只捕获到内存并注入受控测试进程，不能 cat 到日志。主控和 core reviewer 已在 PG accepting connections 后立即获知，并在 Windows/完整 health 通过后获更新。运行环境管理权交回 `/root`，本子代理收口后不再 start/stop/restart。

合同/计划偏差：无公共合同、认证、主依赖、分母或盲测变更；实测分支与委派 main 文本不一致已明确记录。E1/R2 证据仅支持同持久身份的隔离环境恢复与资源管理，不替代 R20 全恢复演练、T54 连续观察或阶段审核。下一任务建议主控/非作者评审使用恢复后的原隔离 test DSN 继续已授权的小资源检查；WSL 异常停止原因和两个运行段间缺失区间继续登记 unknown，另行诊断。
