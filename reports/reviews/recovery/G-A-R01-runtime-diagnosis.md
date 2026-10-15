# G-A / R01 Docker Desktop 与 WSL 运行资源诊断

工作包状态：诊断产物 `awaiting_review`；Docker 引擎恢复 `blocked`。R01 整卡仍未完成，本报告不修改其进度或验收状态。

执行者：`/root/docker_runtime_diagnosis`。诊断窗口：2026-10-14T21:13:39+08:00—2026-10-14T21:22:55+08:00（Asia/Shanghai）。分支：`codex/full-delivery-recovery`；输入 HEAD：`b8199ce5dd0a7920ce5770e4f580fe23e0fe9f6b`。工作树有主控及其他工作包的恢复合同改动，均未覆盖。

## 1. 本轮输入、输出与边界

已读 `AGENTS.md`、执行地图、恢复计划第 5/9 节、R01 卡、原 T03 卡及其架构/运维合同、当前状态与交接、当前 Compose。使用 Ponytail 5.2.0。R00 独立审查前只执行已授权的独立资源准备，不改业务。

输入：已安装并由主控在 20:48:22+08:00 授权启动的 Docker Desktop、Windows/WSL 本地状态、Docker 当前启动日志和当前项目 Compose。

预期输出：引擎实际 ready；否则定位具体最小宿主障碍，提供真实复现、局部可逆动作与证据，不能只写“Docker 不可用”。实际输出：定位到旧 `dockerInference` AF_UNIX 运行时对象的 Windows 访问失败；可逆隔离和 Desktop 重启未成功，最终引擎探测仍超时。

本包只新增本报告和 `reports/runs/recovery_r01_runtime_diagnosis_20261014/` 中的诊断脚本、JSON、stdout/stderr 日志。未改源码、schema、依赖锁、Compose、进度；未 commit、push 或登记 accepted。未运行 Compose、迁移、downgrade、清库、下载镜像/大模型、读取 `.env`/凭据/秘密附件/其他项目资产。未修改 ACL、全局 WSL/网络配置、系统库或 Docker 数据卷。

## 2. 根因证据与实际状态

当前启动日志 `C:\Users\yinha\AppData\Local\Docker\log\host\com.docker.backend.exe.log` 第 1416 行记录 2026-10-14T12:49:01.070040900Z，即 20:49:01+08:00：`all local engines stopped`。第 1419 行记录 backend crashed，错误责任点为 `starting services: initializing Inference manager`，监听 `unix://<HOME>\AppData\Local\Docker\run\dockerInference` 时无法移除旧文件：`The file cannot be accessed by the system`；listener 同时报告路径语法错误。原始定位保存于 `root_cause_excerpt.json`，包含源路径、原行号和 UTC 时间。

可观察链路为：Desktop 后端启动 → API proxy 管道建立 → Inference manager 监听初始化失败 → 全部本地引擎停止 → Docker CLI 请求挂起。21:15/21:19 快照中 `dockerDesktopLinuxEngine` 等管道存在，但 `docker info` 没有返回 server；管道存在不等于 engine ready。`docker desktop status` 与 `restart` 也超时，未把进程存在、CLI 安装或 restart 请求当成启动成功。

旧对象的精确路径是 `C:\Users\yinha\AppData\Local\Docker\run\dockerInference`。`Resolve-Path -LiteralPath` 返回相同绝对路径；`run` 为普通 Directory；对象是 0 字节 `Archive, ReparsePoint`，LinkType/Target 均为空。`fsutil reparsepoint query` 返回 error 1920。随后仅通过 `FindFirstFileW` 读取元数据，得到 tag `0x80000023`、name-surrogate=false。该 tag 在 [Microsoft Reparse Tags](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fscc/c8e77b37-3909-4fe6-a4ea-2b9d423b1ee4) 中表示 UNIX domain socket；它不表示重定向路径。预检日志为 `socket_reparse_tag.stdout.log` 和 `socket_isolation_before.json`。

“旧对象访问失败使当前 Docker 启动终止”有直接日志和相同错误复现支持。为何 Windows 无法访问该特定旧对象、是否涉及驱动/文件系统历史状态，本轮尚未证实；不把未知原因写成权限或版本结论。Afd 驱动 RUNNING、Winsock `socket(AF_UNIX=1, SOCK_STREAM=1)` 创建成功且 WSA error=0，不能泛化成宿主完全不支持 AF_UNIX。该 API 检查未 bind，不证明旧对象可以删除、改名或重建。

## 3. 已执行的可逆恢复动作

1. 21:18:30+08:00，在主控明确授权并完成精确目录、非重定向 tag 与零字节预检后，尝试单一 PowerShell `Move-Item -LiteralPath`，目的为同一 `run` 目录内的 `dockerInference.backup-20261014T211830+0800`。退出 1，错误仍为 `The file cannot be accessed by the system`；原路径仍存在，backup 未创建。没有改变旧对象、删除文件或触碰 VHD/卷。
2. 21:19:17+08:00，基于日志确认 Docker 所有 engine stopped，执行 `docker desktop restart --detach --timeout 20`。外层 25 秒硬超时仍触发，未获得 restart 成功证据。21:22:15+08:00 的最终 `docker info --format "{{.ServerVersion}}"` 也在 25 秒超时；engine ready 仍为 false/未证实。

隔离动作没有成功，因此无实际 backup 需要恢复。若宿主之后允许该同目录改名，原计划恢复命令为：

```powershell
Move-Item -LiteralPath 'C:\Users\yinha\AppData\Local\Docker\run\dockerInference.backup-20261014T211830+0800' -Destination 'C:\Users\yinha\AppData\Local\Docker\run\dockerInference'
```

该命令本轮未执行；其前置是 Desktop 已停止、backup 实际存在、原路径不存在，不能覆盖新生成的监听对象。一次局部隔离和一次 Desktop restart 均无进展后，依 AGENTS 第 8 节停止扩大补丁；没有 factory reset、卷删除、WSL 全局 shutdown 或重装。

## 4. 容量、进程与 WSL

| 项目 | 真实观测 | 证据 |
|---|---|---|
| Docker Desktop / CLI | Desktop 4.60.1.218372；Docker CLI 29.2.0 build 0b9d198 | `host_snapshot_final_capacity.stdout.log`、`docker_version.stdout.log` |
| 宿主 | Windows 11 10.0.26200，WSL 输出补丁 9457；RAM 31.07 GiB，21:19 可用 13.63 GiB | 同上、`wsl_version.stdout.log` |
| WSL | 2.7.3.0；kernel 6.6.114.1-1；Ubuntu-22.04 与 docker-desktop 均 WSL2 | `wsl_version`、`wsl_inventory_utf16` |
| Ubuntu 容量 | `uname/free/df` 实际 exit 0；Mem 15520 MiB、available 14774 MiB；swap 4096 MiB；根分区可用 920G | `ubuntu_capacity.stdout.log` |
| Windows 磁盘 | C 可用 459.66 GiB；D 可用 482.61 GiB | `host_snapshot_final_capacity.stdout.log` |
| Docker 数据文件 | `docker_data.vhdx` 6056574976 bytes（5.64 GiB）；main ext4.vhdx 109051904 bytes（104 MiB），仅读元数据 | `socket_snapshot.stdout.log` |
| 服务/进程 | WslService、vmcompute Running；com.docker.service Stopped/Manual；2 个 backend、4 个 Desktop 进程存在 | `host_snapshot_final_capacity.stdout.log` |
| 最终 WSL 状态 | 21:20:18，Ubuntu-22.04 / docker-desktop 均 Stopped；Ubuntu 只读命令曾真实执行成功 | `wsl_inventory_final.stdout.log` |

当前证据不支持内存/磁盘不足是这次启动失败的原因。com.docker.service 的 Stopped 状态仅记录事实，未据此改服务配置或认定 WSL2 引擎必然需要该服务。当前 Compose 是旧本地开发 postgres/redis/opensearch 编排，尚非恢复卡要求的隔离测试项目；本轮未用其启动或连接数据库。

## 5. 命令、退出码与验证边界

所有诊断 CLI 经 `probe.ps1` 执行，直接启动的 CLI 进程硬超时 25 秒。超时命令记录 effective exit=124、实际被终止的 CLI exit=-1；外层 PowerShell 工具会显示 exit=1。Desktop 插件继承流未关闭时最多另等 2 秒并写明 stream 未关闭，未继续无限等待。`commands.json` 保留 25 次诊断 invocation 的完整参数、工作目录、开始/结束、退出码与 stdout/stderr 路径；25 次探测不是 25 个产品测试。

watchdog 的实际限制：初版只终止直接 CLI launcher，没有终止整棵进程树。收尾观察到本次 `desktop status` 的 `docker-desktop` 插件 PID 13848（StartTime=21:16:34.609+08:00，与该探测一致）仍存活。因此不能声称插件后代也在 25 秒内退出。为避免误停业务进程，新增收尾脚本先核对固定 PID、启动时间与 CLI-plugin 完整路径；21:27:06+08:00 执行时该 PID 已自行退出，记录 already_exited=true，未调用 Stop-Process。此命令 exit 0，日志为 `diagnostic_cli_child_cleanup.json/stdout.log`。不把仅 launcher 的 timeout 当成完整进程树 timeout；后续资源探测应使用能覆盖其自身 CLI 后代的 watchdog。

| Probe / 实际命令 | effective exit / 结果 |
|---|---|
| `docker --version` | 0，CLI 已安装 |
| `docker info --format "{{json .}}"` | 124，25 秒 timeout，无 server 结果 |
| `wsl --list --verbose`、`wsl --status` | 0；首轮流按错误编码读取，保留原日志；UTF-16 重读两条均 0 |
| `powershell -File host_snapshot.ps1`（2 次） | 0，容量/进程/管道快照 |
| `docker desktop --help`、`docker desktop restart --help` | 0，只核实本机可用语法 |
| `powershell -File socket_snapshot.ps1` | 0，只读 listener/VHD 元数据 |
| `fsutil reparsepoint query <exact listener path>` | 1，error 1920，原中文流存在解码限制 |
| `wsl --version` | 0 |
| `wsl -d Ubuntu-22.04 --exec timeout 20s sh -c "uname -r; free -m; df -h / /mnt/c /mnt/d"` | 0，真实 WSL 命令执行成功 |
| `docker desktop status` | 124，25 秒 timeout |
| `wsl -d Ubuntu-22.04 --exec timeout 20s stat -c "type=%F mode=%a size=%s name=%N" <exact listener path>` | 0，WSL 视角为 regular empty file；不以此覆盖 Windows reparse tag |
| `powershell -File reparse_tag.ps1` | 0，Windows FindFirstFileW 读取 tag 成功 |
| `powershell -File isolate_socket.ps1` | 1，同目录 Move 失败，原对象保留 |
| `docker desktop restart --detach --timeout 20` | 124，未获重启完成证据 |
| `wsl --list --verbose`（最终） | 0，2 个发行版 stopped |
| `sc query afd` | 0，Afd RUNNING |
| `python windows_af_unix_probe.py`（首次） | 1，AttributeError：当前 Python build 不暴露 AF_UNIX；host bind 未执行，不是业务失败 |
| 同一 Python probe（明确资源限制） | 2，`python_exposes_af_unix=false`，created/renamed=false；未创建 socket 文件 |
| `powershell -File af_unix_native_probe.ps1` | 0，Winsock AF_UNIX socket 创建/关闭成功，未 bind、未创建文件 |
| `docker info --format "{{.ServerVersion}}"`（最终） | 124，21:22:40+08:00 仍未 ready |

本轮仅作宿主诊断与局部恢复，unit/contract/security/frontend/e2e/live/manual 产品验收均 `not_run`；真实数据库 integration 仍 `blocked`。未运行原 T03-C01—C06，不能继承旧报告的 6 passed；未取得容器/镜像清单、数据库连接、重启持久化或业务性能证据。未安装 Python 扩展或把 Python 缺 API 当成宿主故障结论。

21:25:41+08:00，`python reports/runs/recovery_r01_runtime_diagnosis_20261014/verify_evidence.py` 经同一 25 秒 watchdog 实际 exit 0：核对 25 条诊断记录的唯一名称、+08:00 时间、日志存在、launcher 超时字段、旧 listener 未改变和 reparse tag。它是产物一致性检查，不是产品测试。`git status --short -- <本报告> <本运行目录>` 实际 exit 0，仅显示这两个允许范围为新增。此两条收尾检查分别保存 `evidence_validation.json`、`git_scope_status.json`，不混入 25 条诊断调用统计。诊断命令窗口截至 21:22:55+08:00；报告一致性检查及遗留 CLI-child 收尾截至 21:27:06+08:00。

## 6. 最小阻塞、独立可继续部分与交接

最小剩余宿主状态：需要 Windows 能访问并安全隔离上述**单一旧 AF_UNIX listener**，或由 Docker Desktop 在保留全部 Docker 数据的前提下恢复其 Inference manager 监听初始化。当前普通同目录 Move 和 Desktop restart 均未解决该状态。下一步由宿主/Docker 维护方处理这个精确对象的访问错误；需要管理员权限、系统重启、文件系统/驱动修复或改变全局设置时应另行确定影响范围，不能在本包自动执行。没有证据支持“改应用源码就能修复”或“升级某版本必然解决”。

可以继续的独立工作：R00 合同审查、R01 运行入口与质量命令的静态/单元准备、隔离测试 Compose 与专用 DSN 的实现审查；真实容器启动、PG integration、worker/scheduler 重启恢复及 G-A 数据链检查不能记为 passed。

合同/计划偏差：资源准备按主控的独立授权提前于 R00 生效，只产出资源证据；未越过 R01 前置开展业务实现。E1/R2 获得真实环境障碍和复现证据，尚未提供可启动部署验收；P1 没有业务性能数据。下一任务建议：在宿主状态修复后先复跑 `docker info` 返回 server，再由 R01 所有者启动**隔离测试项目**并执行专用数据库验收；保留本次失败历史。
