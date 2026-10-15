# G-A / R01 · Windows AF_UNIX 旧对象根因与等价运行资源

首次创建/写作开始：2026-10-14T21:45:26+08:00。执行者：`/root/docker_socket_root_cause`。输入分支 `codex/full-delivery-recovery`；HEAD `d752fe0c8f14dd4c35b39863cfba0d1c902fffae`。实际探针从 2026-10-14T21:28:58+08:00 开始；此前规范读取与只读取证已执行。原诊断的日志与报告只读保留。

诊断产物状态：`awaiting_review`；本包实现 `complete`。**独立 Linux daemon 已真实 ready，官方 hello 镜像运行退出0；原 Docker Desktop 旧对象障碍仍未解决。** 本报告不修改 R01/T03 的状态，不代表整卡验收。

最后更新/本次写作结束/证据截止：2026-10-14T22:00:38+08:00。引擎实际启动窗口与文档写作时间分开记录，不声称已持续运行72h。

## 1. 范围与输入输出

已读 AGENTS、执行地图、R01/T03、架构/运维合同、状态/交接、用户完整执行提示词、Ponytail 插件 5.2.0、上一诊断报告及原始日志。根任务授权本项目运行资源；主控给本包的初始范围是单一旧 socket 的只读/native API 诊断与可逆改名，之后明确批准专用 Ubuntu Docker static 29.2.0 缓存和隔离 daemon。后续授权不代表原 Desktop 被修复。

输入为明确旧对象 `C:\Users\yinha\AppData\Local\Docker\run\dockerInference`；预期输出为最小复现、Windows 错误含义、局部可逆动作的可行性及实际 engine ready，或已证实的特定宿主缺口。只新增本报告与 `reports/runs/recovery_r01_socket_root_cause_20261014/`；另在新授权的 Ubuntu `/tmp/dianzi-docker-static-r01-20261014/` 保存工具与隔离运行状态。

未改业务源码、公共合同、Compose、依赖锁、全局 Docker context/settings、ACL、系统库、Windows/WSL服务配置；未读秘密、`.env`、DPAPI 或盲测答案；未运行 PoC/扫描；未删除/迁移 Desktop 数据、卷、VHDX 或用户文件；未 commit/push/登记 accepted。唯一删除是本包自己创建的两枚控制 socket，精确路径、归属和 tag 验证见各清理日志。WSL运行时有单次、明确授权的 root subtree_control 委派与项目新节点赋额，见第5节，不把该变化隐藏在“不改全局配置”表述中。

## 2. 已证实的错误层级

上轮实际启动责任点是 2026-10-14T12:49:01.070040900Z，即 **2026-10-14T20:49:01+08:00**，不是 21:49。原 `root_cause_excerpt.json` 保存 backend 日志第 1416/1419 行：Inference manager 清理旧 endpoint 收到 error 1920，随后全部 local engines stopped、backend crashed。旧 CLI 超时与管道存在并不能证明 server ready。

本轮最小复现 `native_open_probe.py` 使用 Windows `CreateFileW`，`OPEN_EXISTING`、share read/write/delete，全程不读取对象内容、不写 reparse data。相同旧对象五种组合均得到 **Win32 1920 + NTSTATUS 0xC0000279**：普通 FILE_READ_ATTRIBUTES；OPEN_REPARSE_POINT + FILE_READ_ATTRIBUTES；OPEN_REPARSE_POINT + DELETE/FILE_READ_ATTRIBUTES；OPEN_REPARSE_POINT + BACKUP_SEMANTICS；OPEN_REPARSE_POINT + zero desired access。所需 rename 句柄未取得，未调用 SetFileInformationByHandle 修改旧对象。

[Microsoft NTSTATUS 表](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-erref/596a1078-e883-4972-9bbc-49e60bebca55) 将 0xC0000279 定义为 `STATUS_IO_REPARSE_TAG_NOT_HANDLED`：对应 tag 的分层文件系统驱动在所需时未处理该请求。该结果不是 `ACCESS_DENIED` 或 `SHARING_VIOLATION`，不能直接写成“ACL 权限不足”“进程必然锁定”或“文件损坏”。

[CreateFileW 官方合同](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew) 说明 OPEN_REPARSE_POINT 应直接打开 reparse 对象、避开普通 reparse 解析。实测表明这条最小 no-follow 路线在旧对象仍失败，而父目录链全部为普通 Directory，无重定向路径。驱动 `sc query afunix` 实际 RUNNING，`afunix.sys` 文件版本 10.0.26100.8972；不从 Afd 状态推导 AF_UNIX 已完全可用。

## 3. 对照与可逆动作结论

2026-10-14T21:31:18+08:00，新建本报告目录内独立 AF_UNIX 控制对象，Windows 原生 `socket/bind` 成功，tag 0x80000023、0 byte；普通打开也为 1920，但 OPEN_REPARSE_POINT 和附 BACKUP_SEMANTICS 打开均成功，`SetFileInformationByHandle(FileRenameInfo)` 在同目录备份名称改名成功，随后精确删除本包控制对象成功。普通诊断源文件三种 flags 均打开成功，因此 API 参数与 no-follow/rename 实现有正对照。该控制在 D:，未在 C: 或 Desktop runtime 目录创建新对象，不能排除卷/目录相关差异。

[Microsoft AF_UNIX 实现说明](https://devblogs.microsoft.com/commandline/af_unix-comes-to-windows/) 解释 socket file 为 NTFS 自定义 reparse point，由 afunix.sys 实现；[FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info) 允许设置 ReplaceIfExists=false，目标存在时拒绝替换。这条机制在控制对象可用，但旧对象的句柄前置不成立，因此本包没有盲试第二次 Move/Remove 或旧对象 native rename，也不存在需还原的旧 socket backup。

安全恢复模板仍为：先核实旧对象精确绝对路径/父目录/tag/零字节、成功取得 no-follow + DELETE 句柄，再以不替换既有目标的同目录唯一 backup 名称 rename；恢复时验证同一 backup 身份及原名称不存在，再反向 rename。当前必须先让 Windows 重新允许取得该旧对象句柄，才可执行。不得因为上述机制在控制对象成功就宣称旧对象已可隔离。

2026-10-14T21:32:39+08:00 快照仍见两枚 com.docker.backend 及 Desktop GUI 进程。本轮未判断它们各自拥有旧对象句柄，未强制停止它们。runtime 目录另有 `userAnalyticsOtlpHttp.sock`，同为 0 byte/1056；整个父目录改名将影响第二个对象，超出本包单 socket 初始范围，未执行。

[Docker 官方仓 issue #625](https://github.com/docker/desktop-feedback/issues/625) 有相同错误类与 no-follow 失败报告；维护者 2026-09-30 表示 4.92 在此领域发布了修复。该信息只提供供应商调查方向，未在本机验证升级，不能视为修复承诺。未采纳网页中的父目录迁移、关闭推理、重启或清理动作作为授权。

## 4. 等价 Linux 运行资源的实际准备

准确发行版为 `Ubuntu-22.04`；首次使用简称 Ubuntu 的两个调用收到 WSL_E_DISTRO_NOT_FOUND，保留失败日志，随后从原清单读取正确名称修正，不把名称错误写成 Ubuntu 启动失败。默认用户 uid1000，WSL root `id` 成功；root 新 mount namespace exit0，普通用户 unshare EPERM 不是资源永久缺失。

实际 kernel 6.6.114.1-microsoft-standard-WSL2 x86_64；`iptables` 1.8.7、git/xz/procps/curl/tar 已安装，overlay 可用；cgroup2 挂载 rw。缺 `dockerd/containerd/runc/ctr`，仅 docker client 指向 Windows Desktop 路径，`/var/run/docker.sock` 不存在、无 dockerd/containerd 进程。

主控 2026-10-14 当前轮明确批准官方 [static binary 安装方式](https://docs.docker.com/engine/install/binaries/) 的 29.2.0，仅解包到专用 cache；不复制到系统路径。准确来源 `https://download.docker.com/linux/static/stable/x86_64/docker-29.2.0.tgz`。下载第1次 20s 超时保留 52,466,146 bytes；第2次正常 TLS 校验下断点续传完成 84,236,913 bytes，exit0。完整头保存 `portable_download_initial_headers.log` 与 `portable_download_resume_headers.log`。

本地 SHA256：`1beacd5cebec16bf857d557d3ce3e7e20fc692639cd36e0cfb3877def06b1e7c`。这是已获取字节的本地标识，**不是发布者参考 hash 校验**；官方索引未发现 sha256 清单，另版本 .tgz.sha256 HEAD 返回404不等于已遍历所有供应商校验机制。主控已明确接受该披露的 HTTPS 官方来源验证范围。tar 清单 9 项均为 dir/regular file，拒绝绝对、..、links/devices/FIFO 与越界路径；提取专用 portable，exit0。

实测 binary：Docker client 29.2.0 build 0b9d198；dockerd 29.2.0 build 9c623849；containerd v2.2.1；runc1.3.4，libseccomp2.5.4。这些是实际 --version 输出，不是仅按包名推测。

## 5. 当前隔离 daemon 前置与最小必要裁决

专用预定 runtime `/tmp/dianzi-docker-static-r01-20261014/runtime`，独立 Unix socket/data-root/exec-root/PID/config file/空 client config，bridge=none、iptables=false；未改主机全局 firewall，未暴露 daemon TCP。监督器设计为最长72h、daemon日志10MiB、容器local日志3×10MiB。项目资源要求新 cgroup 8GiB/2CPU/2048pids，主控随后明确限定只改自己的节点、不改父级。

2026-10-14T21:40:09+08:00 launcher shell exit0只表示后台监督器已提交；监督器在创建自己的 cgroup 后写 memory.max 收到 PermissionError13，**尚未启动 dockerd**。21:41:49+08:00只读核验：root `cgroup.controllers` 有 cpu/memory/pids，但 root `cgroup.subtree_control` 空；新 `dianzi-r01-20261014` controllers/subtree_control 空、procs0，没有 memory.max/cpu.max/pids.max。因此是上游尚未委派控制器，不能写成内存容量不足或 Docker daemon 自身启动失败。root cgroup controllers 向新子节点的委派需要改父级 subtree_control，而当前主控明确禁止；本包没有执行这项父级变更，也没有擅自关闭资源检查后启动。

首次 `docker info` 除 socket absent 外还因本包模板 `{{json.}}` 缺空格返回模板解析错误(exit64)。这是探针调用错误，不能计为 Docker 业务测试失败；下一步使用固定脚本正确模板。该调用不能作为 engine ready 或正式集成验收。

主控随后批准仅向 root subtree_control 添加 +memory/+cpu/+pids，禁止修改父级limit、迁移原PID或永久启动配置。2026-10-14T21:46:38—43+08:00预检在任何委派写入前失败：此前存在的项目cgroup已经不存在。21:47:40+08:00独立只读检查再次确认该节点不存在、root subtree_control仍为空；这是WSL运行时层状态改变，实际发生机制未确认，本包未执行WSL shutdown。尚未写root配置，已向主控报告如何创建全新空节点后复核，遵守失败先停止与范围裁决。

主控裁决该写操作前状态变化不计同根因修复失败；要求创建/预检/赋额/持久Supervisor置于同一WSL调用。本轮按该顺序执行，2026-10-14T21:49:13+08:00精确 root delegation 实际写成功；操作前root subtree_control空、项目新建且无PID；操作后cpu/memory/pids已委派，已有root limit均仍null，未迁入任何旧PID。项目父节点8GiB memory.max、2GiB swap.max、cpu.max=200000 100000、pids.max2048，parent不直接放PID；新supervisor叶放本包进程，Docker容器cgroup-parent指项目节点。

2026-10-14T21:49:16+08:00版本请求实际返回server29.2.0/API1.53/Linux amd64；21:50:15+08:00 `/_ping` 为OK，info显示专用DockerRootDir、cgroupfs、seccomp builtin。这些才是engine ready证据。原backend/Desktop未改、未恢复。

两次官方hello pull在21:50:25与21:51:57返回TLS handshake timeout。21:51:49宿主curl经现有代理正常返回registry401；21:52:32只检查代理key存在性，HTTP(S)_PROXY/no_proxy均true。本包监督器原env精简为PATH/LANG，遗漏既有代理，导致daemon直连失败；这属于本包启动链的可修复根因，不是证书错误。只继承既有proxy环境到受控子进程，不输出值、不写daemon配置、不读取秘密文件、不关闭TLS。先验证本实例无任何容器，21:54:08停止首个监督器/daemon退出0；保存首个lifecycle与原log；同目录保留data，只重启该专用实例。首次deadline未延长。

当前SupervisorPID **221**、daemonPID **222**，当前段start **2026-10-14T21:54:08+08:00**，整体截止仍 **2026-10-17T21:49:15+08:00**。截止或日志10MiB耗尽时监督器先TERM本daemon组、15s优雅等待，必要时仅KILL该专属组。该服务有真实受控后台进程；不是会话外虚构工作。原live窗口目前只有本次若干分钟，不计72h已运行。

2026-10-14T21:54:57+08:00官方 `docker.io/library/hello-world` pull exit0，digest为 `sha256:11a3eb1597e864c51b3f56733cb2e8a90bf0c284bfc05f9444d81c558bc848aa`；21:55:39—40以该digest真实run，network none、readonly、cap-dropALL、no-new-privileges、64MiB、0.1CPU、16pids，输出官方Hello，State.ExitCode0/OOMKilledfalse。inspect证明容器配置；没有在短暂存活期间单独读取它的内核子节点，不能声称逐项内核配额复验。项目整体内核硬限额已直接读取。保留本包已退出控制容器 `dianzi-r01-hello-20261014` 供review。

### 实际调用与停止/恢复交接

```powershell
wsl.exe -d Ubuntu-22.04 -u root --exec /tmp/dianzi-docker-static-r01-20261014/portable/docker/docker --config /tmp/dianzi-docker-static-r01-20261014/runtime/client-config --host unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock version
```

同一前缀后加具体 `pull/run/inspect/ps`，不使用宿主默认context或Desktop数据。后续PG/Redis/OpenSearch/graph用独立测试容器/项目/DSN；此daemon默认bridge=none，无全局iptables修改，所以 `--network host` 场景必须把**服务内部监听地址设127.0.0.1**、独立端口并显式容器memory/cpu/pids与cgroup-parent。host网络忽略Docker端口映射，不能只凭`-p127.0.0.1:`声称服务本身已loopback。四个Linux Compose候选路径未找到plugin；21:59:54实际专用CLI `compose version` exit1/unknown command，确认此调用入口缺Compose能力。本包不安装Compose、不改infra，裸Docker可运行；R01的Compose集成仍须补齐。

停止时先读 `runtime/lifecycle.json` 与 `/proc/221/cmdline` 确认PID仍为该监督器，再只给它TERM；预计子daemon按上述边界停止，lifecycle记录end与exit。不得blind kill重用PID。项目cgroup清理仅在全层无PID时清理本项目节点，不能递归用户cgroup。父级delegation回滚为向 `/sys/fs/cgroup/cgroup.subtree_control` 写 `-memory -cpu -pids`；**必须先确认没有别的子节点依赖这三项，否则保留委派，禁止撤销影响用户新进程**。WSL未重启时可保留当前专用cache继续用；任何新启动都须复核真实cgroup状态，不套用旧快照。

## 6. 真实命令与验收层级

所有昂贵/外部探针经本目录 `probe.ps1`：outer25s硬超时；WSL命令另加20/24s、curl max20s；记录工作目录、起止+08:00、实际退出码、stdout/stderr。逐条 JSON 对应真实命令；本包不凑业务pytest通过数。

| 日志名 | 时间(+08:00) | 退出码 | 实际结果 |
|---|---|---:|---|
| native_open | 21:28:58 | 1 | no-follow成功的初始假设被反证；assert失败保留 |
| afunix_driver | 21:28:58 | 0 | afunix RUNNING |
| native_open_extended | 21:30:24 | 0 | 五种只读句柄打开均1920/0xC0000279，复现断言符合 |
| native_bind_control | 21:30:24 | 0 | 原生bind成功；该轮只测bind，控制对象另精确清理 |
| native_control_lifecycle | 21:31:18 | 0 | bind/no-follow/同目录rename/清理全成功 |
| process_snapshot | 21:32:39 | 0 | backend进程及驱动文件元数据，非engine通过 |
| wsl_container_inventory / wsl_root_permission | 21:32:39 | -1 | 不存在发行版Ubuntu，保留名称错误 |
| wsl_container_inventory_named | 21:33:04—09 | 0 | 正确发行版工具/容量清单 |
| wsl_root_permission_named | 21:33:04—07 | 0 | root uid0 |
| wsl_root_namespace | 21:33:46 | 0 | root新mount namespace |
| wsl_prerequisites | 21:33:51 | 0 | kernel/cgroup/overlay/工具与目标端口快照 |
| cleanup_native_control | 21:34:42 | 0 | 精确清理本包21:30:24创建的控制socket |
| static_archive_head / static_checksum_head | 21:35:17—19 | 0 / 22 | 29.9.0官方HEAD200；参考hash URL404，最终未选29.9 |
| static_download_1 | 21:36:24—45 | 28 | 网络20s限时失败、保留部分包 |
| static_download_2 | 21:37:41—52 | 0 | 可恢复续传完成29.2.0 |
| static_validate_extract | 21:38:23—25 | 0 | 实际hash/清单/安全提取 |
| isolated_daemon_start | 21:40:08—10 | 0 | binary版本真实；launcher成功不等于daemon成功 |
| isolated_supervisor_state | 21:40:39 | 0 | 读取后台初始化失败原文 |
| isolated_daemon_info | 21:40:39—40 | 64 | socket不存在+本包模板错误 |
| cgroup_inventory | 21:41:49 | 0 | 新节点无控制器、无PID，父级subtree_control为空 |
| portable_evidence_export | 21:43:01 | 0 | 专用cache公开供应商响应头/清单复制到本报告目录 |
| delegate_project_controllers | 21:46:38—43 | 1 | 写操作前预检项目node已不存在，未执行委派 |
| cgroup_preflight_change | 21:47:40—41 | 0 | 独立确认项目node不存在、root delegation空 |
| evidence_validation | 21:48:23 | 0 | 25条当时已有receipts、15源文件语法/hash有效；不是25业务测试 |
| isolated_daemon_bootstrap | 21:49:09—16 | 0 | 一次delegation/项目赋额/daemon启动，真实server29.2 |
| isolated_engine_health | 21:50:15 | 0 | /_ping OK、root专用路径、实际项目cgroup硬限额 |
| official_hello_pull / official_hello_pull_retry | 21:50:15—25 / 21:51:46—57 | 1 / 1 | 原env过滤遗漏代理，registry直连TLS timeout |
| registry_head | 21:51:46—49 | 0 | 经现有代理401正常，四Compose候选未找到 |
| proxy_presence | 21:52:32 | 0 | 仅代理key是否存在，无值 |
| isolated_proxy_restart | 21:54:06—08 | 0 | 专用实例确无容器；首个监督器/daemon优雅exit0，原deadline保持 |
| isolated_engine_health_proxy | 21:54:47—48 | 0 | 新PID221/222真实ping/info与限额 |
| official_hello_pull_proxy | 21:54:47—57 | 0 | 官方镜像真实pull+digest留证，TLS正常 |
| official_hello_smoke | 21:55:39—40 | 0 | digest固定真实run、exit0/OOMfalse/config限额 |
| portable_evidence_export_final | 21:58:30 | 0 | 当前lifecycle/daemonlog/委派前后证据导出；代理值过滤命中0，原log保留cache |
| evidence_validation_final | 21:59:15 | 0 | 37条当时已有receipts和24份源文件hash/语法核验，不是业务测试 |
| portable_compose_capability | 21:59:53—54 | 1 | 本入口compose version实际unknown command，缺plugin |

Windows socket探针的初始失败是调查假设失败；后续复现断言通过也只证明错误可观察，不是业务修复。业务 unit/contract/security/frontend/e2e 本包 `not_run`；原 Desktop integration `blocked`；等价 engine ping/官方hello smoke `passed`；PG/Redis/OpenSearch/graph真实集成 `not_run`。不计持续运行时长、性能、准确率、线上来源或模型调用；本包未调用任何产品模型/FOFA API。

## 7. 影响、可继续工作与下一任务

原 Desktop 的最小特定障碍是 Windows 无法打开该已识别 AF_UNIX 旧对象，即使 no-follow/zero access；内部驱动/对象状态的形成原因还未知。若需要管理员动作、宿主重启、升级或父目录迁移，须按具体范围评估；不能静默把官网 issue workaround 当项目指令。

等价资源现在已真实可用，独立runtime/cgroup/既有代理链已验证。主控可推进R01真实PG等容器和专用测试连接/写读/恢复，同时继续API/检查入口与隔离Compose实现；不能用本包资源smoke代替任何业务数据库验收。

合同无新增业务变化、无依赖主版本修改。工程资源使用从Desktop改为专用Linux等价daemon是用户已授权运行资源的实现选择，明确披露；它不能证明原Desktop修复。本包 E1/R2 证据为可复现的运行障碍、官方真实工具、隔离engine与官方容器smoke；尚未提供可启动应用验收、P1性能或任何完整评分结论。下一任务建议主控使用显式入口按R01启动实际项目测试服务、验证Windows应用到loopback的真实连接，再做对应迁移/读写/重启；不沿用开发默认DSN、不清旧Desktop数据。文档/log/raw当前cgroup和lifecycle已保存，本包到此结束并等待独立review。
