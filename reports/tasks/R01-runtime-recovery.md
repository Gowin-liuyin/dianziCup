# R01 · 受控 WSL runtime 异常中断恢复

本恢复子包：`awaiting_review / complete`；不签 R01、原 T03 或 G-A 的 accepted。执行者 `/root/r01_runtime_recovery`；只读安全复核 `/root/r01_runtime_recovery/recovery_safety_check`。输入代码 b099483b4f2be3d21b3fd3e7e4327912ba75cae2，实际分支 `codex/full-delivery-recovery`。本次操作窗口为 2026-10-15T09:56:43+08:00 起，daemon 恢复发生在 09:59:13—14，14 个既有容器恢复发生在 10:01:11—41。报告初次落盘实际时间见 `delivery_files.json`，不把此前工具执行或中断时间计为写作时长。异常停止时刻未知；中断期间不计持续采集或实际写作时间。

## 范围与输入输出

已读 AGENTS、执行地图、09 运维合同、恢复 R01 卡、状态、R01/resource/socket-root-cause 报告及旧监督器/委派脚本。复用 Ponytail 的已有实现优先原则、标准库和已经核验的 Docker 29.2.0 portable；没有下载替代引擎、换 data-root、重建卷或实施业务。受控输入为原私有 runtime、持久 metadata 和原 lifecycle；输出为保存原异常证据的新恢复段、相同容器/镜像/卷、内核额度和实际健康验证。

文件改动只在 `reports/runs/recovery_r01_runtime_recovery_20261015/` 和本报告；未动业务、迁移、锁、progress、其它 run、Docker context、用户 global ACL、Windows Desktop 旧 AF_UNIX 或已有仓库文件。主控 app.py/stage 等未提交修改保留。不 commit/push。私有连接只在受控内存解析用于 AUTH，未输出其值；未读 `.env`、DPAPI/providerkey 或 holdout。

## 中断观察与原证据

09:56:43 实际观察：WSL boot ID `a57bd35b-ffb0-4ad7-b249-77daa5fa5c0d`，uptime 284.76 秒。旧 lifecycle 为 started_at `2026-10-14T21:54:08+08:00`、supervisor 221、dockerd 222、ended_at null。旧 boot ID 未记入该 lifecycle，不能补造。09:58:12 和 09:59:06 的命令记录证明旧两 PID 不存在，无本 runtime 所属进程，Unix socket connect errno 111（ECONNREFUSED），`/proc/net/unix` 无此 runtime 监听；原 cgroup 已不存在，root cgroup 挂载 rw、subtree_control 空。这些观察支持新恢复段，不确定实际停止时刻和触发原因。旧日志最后一条为 02:41:09 的 TLS 容器事件，也不当作停止时间。

09:59:06 原字节归档至 Linux 自有私有目录 `/tmp/dianzi-docker-static-r01-20261014/recovery-archive-20261015T095906`：原 lifecycle、daemon/supervisor log；stale supervisor.pid、dockerd.pid、socket 和 exec 目录移动保存。先验证目录绝对路径和非 symlink，再归档；原 data 完全保留，exec 在同一位置重建。每项原所有权、mode、inode、mtime/size 和文件 SHA256 见 `preparation_evidence.json`。原 lifecycle `ended_at=null` 原样保留；其 SHA256 为 `579d50e22511cb6eab3b777a2045348f5f48588243a89c0cd28f2f2c0a72afa2`。旧日志原件留在私有目录；仓库只导出精确代理值过滤后的日志。

## 恢复行为与期限

旧监督器不原样重跑：它只接受正常 SIGTERM 结束，并会重写配置/日志。新监督器复用原 command，保持同一 `runtime/data`、`runtime/exec`、Unix endpoint 和 `bridge=none / iptables=false / ip6tables=false / ip-forward=false / ip-masq=false`。没有重写 client config 或 daemon.json。新 segment started_at `2026-10-15T09:59:13+08:00`，supervisor PID 18、dockerd PID 25；最终取证确认两进程仍活着，父 PID/启动 ticks/executable/cgroup 见 `evidence_validation.json`。

原总期限仍 **2026-10-17T21:49:15+08:00**，没有新开 72 小时。监督器同时检查原绝对截止与对应 monotonic 剩余时间，显式 TERM/INT、daemon exit 或预算耗尽均有本段停止原因；退出时只停止此 daemon 进程组。原 daemon log 149,664 bytes 从 10,485,760-byte 总预算扣除，本段预算 10,336,096 bytes；10:06:08 新日志 71,444 bytes，未重置预算。容器原 local log 配置保留。

重建本项目 cgroup、memory/cpu/pids 委派和监督器子组。必须补的 root subtree controllers 为 memory/cpu/pids；保存原空委派与所有既有 parent/sibling limits，再核实它们未被改动。父级硬限额仍 memory 8,589,934,592、swap 2,147,483,648、cpu `200000 100000`、pids 2048。每个容器经 PID→内核 cgroup→实际限制核验，不只读 Docker 声明。裸服务原 swap=0；Compose 原 HostConfig 未设总 swap 时允许额外 swap，这次原样保留，父级 swap 总上限仍 2 GiB，未改容器资源合同。

恢复前持久 metadata 共 17 既有 container。仅匹配完整 ID、名称、镜像、labels、原 Running=true 的精确本任务集合：root PG/Redis/OpenSearch、quality PG/Redis、frontend PG/Redis，以及 infra 七服务。实际 start 14 个旧 ID。原 hello 和失败 `agitated_nightingale` 保持 stopped；独占 TLS 项目在任何 start 前排除并即刻交给 TLS reviewer。TLS 后续被其它获授权操作链运行；本脚本没有对它 start/stop。无 Compose up/down/recreate、无新镜像/卷/同名副本。恢复前后 17 完整 ID、28 images、12 volumes、各 mount 和 digest 保留。

## 实际核验

14 个本脚本恢复的容器全部 healthy；kernel limits 与原 HostConfig 相符；全部监听是 127.0.0.1（包含 IPv4-mapped loopback 的规范化检查）。infra 七服务沿用原 `32d16a4` 冻结镜像，不能称最新主仓 UI。root PG/Redis/Search 的原 marker 仍可读取，Search 2.17.0/green；quality、frontend PG 身份与已有 public table 数分别 13、0，root 原库 public tables 32。root 实际数据库清单仍含 `test_dianzi_r01_20261014`、`test_dianzi_r02_auth_20261015`、`test_dianzi_r02_knowledge_20261015`；未清库或迁移。

infra 原 `t03_volume_probe` 的 `survives-down-up` 保留，alembic 仍 `0005_runtime_observations`。10:06 的 worker/scheduler 真正 observed_at 晚于本次恢复、年龄约 3 秒（≤45 秒）；API 28201 ready 且全部依赖 ready，frontend 25201 HTTP200。没有创建新观测结果冒充恢复。Windows 10:07:28—30 实际连接 12 个服务 loopback 端口并读取 API/frontend；28000 仍不监听，未重启已停止的主控 Windows API/b504 段。

完整命令、cwd、实际起止、timeout、exit、stdout/stderr 路径在各 `<probe>.json` 与 `commands.json`。主入口为本目录 `probe.ps1` 调用 `wsl.exe -d Ubuntu-22.04 -u root --exec python3 -B ...`。专用 CLI 前缀：

```powershell
wsl.exe -d Ubuntu-22.04 -u root --exec /tmp/dianzi-docker-static-r01-20261014/portable/docker/docker --config /tmp/dianzi-docker-static-r01-20261014/runtime/client-config --host unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock
```

| probe | 实际 +08 时刻 | exit | 结果 |
|---|---|---:|---|
| preflight | 09:58:12 | 0 | 旧身份/socket/metadata 可安全恢复；初次详细预检在 prepare 再采集，初次命令 receipt/stdout 保留 |
| prepare | 09:59:06 | 0 | 原记录归档、同 data-root、委派与额度恢复 |
| start_daemon | 09:59:13—14 | 0 | 首个 daemon 恢复 attempt 实际返回 server 29.2.0/API1.53 |
| restore_services | 10:00:25—29 | 1 | 空 HostConfig.CgroupParent 的预检断言过严；失败发生在任何 start 前 |
| restore_services_retry_1 | 10:01:11—41 | 0 | 依据 daemon parent 继承和真实内核归属修正预检，14 个旧 ID start |
| verify_health_persistence | 10:04:54—10:05:02 | 1 | Python3.10 ISO parser 不接受 PG 的缩写 +00 |
| verify_health_persistence_retry_1 | 10:05:23—30 | 1 | 补时区后仍不接受 PG 的 5 位小数；失败保留 |
| verify_health_persistence_retry_2 | 10:06:00—08 | 0 | 标准 strptime 接受两实际格式；14 healthy、持久 marker、观测、额度/loopback 通过 |
| windows_loopback | 10:07:28—30 | 0 | Windows 12 端口/HTTP实际连通，28000保持停止 |
| ruff | 10:07:55 | 1 | 10 个检查项（import/unused/explicit check/timezone） |
| ruff_fix / format / ruff_final | 10:08:31 / 33 / 36 | 0 | scoped 修复与格式；最终检查通过 |
| evidence_validation | 10:09:30 | 0 | 6 源语法、2 parser assertions、旧归档 hash、17 IDs/14 starts、现进程/原期限 |
| validate_static_fix / validate_format / ruff_all_final / evidence_validation_final | 10:11:10 / 32 / 34 / 37 | 0 | 新 verifier 格式与全部 6 源静态检查、最终 hash/进程证据通过 |

业务 pytest/完整 unit/contract/security/frontend/e2e、外部 live 和 manual：`not_run`。本包真实恢复 integration smoke：`passed`；parser self-checks 2 passed / 0 failed / 0 skip，不当作 2 个业务 pytest。没有制造测试数量、性能、持续采集时长或来源/模型效果。daemon log 中 image inspect 产生 `failed to validate image signature / expected image index descriptor` 条目；CLI inspect 返回0、实际服务健康，此观察保留，不声称签名核验通过，未放宽验证。

## 偏差、评分证据与交接

无公共业务合同、依赖主版本、认证、分母或盲测变更。E1/R2 提供异常恢复、限额、真实持久服务与健康证据，不能替代原 T03/R01/G-A 全验收或 T54 连续运行。停止时间仍 unknown，旧/新运行段分开，不能拼成持续采集。

主控管理权在本包收口后明确交回 `/root`；本子代理不再 start/stop/restart daemon、资源或业务进程。当前带原期限的监督器实际持续运行，绝不宣称子代理在会话外继续工作。后续只用显式专用 CLI；首次 `prepare/start/restore` 不应在现运行状态重跑。必要停止须核对实际 lifecycle/PID/命令/boot 后对 supervisor 发 TERM；不要清数据或删 cgroup 的在用子组。恢复期间 TLS 已即时通知独占 reviewer；其验收由对应审查报告负责。下一任务建议主控使用恢复后的独立 test DSN 继续已授权 R02/R01 验证，并把本次中断与未知缺失区间如实记入交接。

10:11 后主控明确接回管理权，并要求释放槽位。只读安全子代理被要求停止后已释放活动槽位；它已于 10:11:39—43 实际写入 `independent_readonly_verification.json`，核对归档、原期限、同 data-root inode、17 IDs/28 images/12 volumes、14 healthy、内核额度/loopback和TLS排除 start，verification_status=passed、failed_checks=[]、task_acceptance=not_assessed。其先前 filtered CLI 失败尝试也保留在 preserved_prior_attempts。它没有独立重跑含凭据的持久查询、TLS PKI、受控停止或真实期限到期、业务/live；作者持久证据仅核对已留记录，不混成独立复跑。真实精确文件清单见 `delivery_files.json`；本包仍 awaiting_review。
