# R10-owned-neo4j-runtime · 隔离测试资源

资源子包状态 `awaiting_review`；R10 实现仍 `partial`。本包的 owned identity 单元、HTTP/Bolt 认证、内核限额、权限与回环监听检查 `passed`；业务图投影、默认 API、整张 R10 与 G-C 不由本执行者验收。执行者 `/root/r10_owned_neo4j_runtime_integration`，没有新增子代理、提交或 push。

输入 checkout 为 `codex/full-delivery-recovery@3baeb8809d3950a091e8db114be7a28049b74b36`，不是委派文字中的 main 分支名称。已有用户与 root 修改全部保留。已读 AGENTS、00 执行索引、02 架构、09 运维、恢复 R10 卡、task_state 的 R10 条目、最近交接、原 R01 安全恢复/停止脚本及 Ponytail full。

## 输入输出与边界

精确资源方案为 `D:/wt/r10-neo4j-projection/reports/runs/recovery_r10_neo4j_projection_20261016/neo4j_resource_proposal.json`，SHA-256 `92e59aed3c0df37ad54d27ea3b9d8cc15d6b0250e307cced5f4b4a3bfd92022f`。root 批准该 Community 5.26.32、Linux/amd64、固定官方 manifest digest；方案不替代 PG 事实权威。

仓库修改仅本报告及 `reports/runs/recovery_r10_owned_neo4j_runtime_20261016/`。代码是固定资源的预检、凭据保护、监督/guardian、停止、只读安全和健康探针；没有改业务、schema、迁移、认证、指标、盲测、项目依赖、全局 ACL/iptables 或 WSL 配置。外部缓存为 `D:/dianzi-runtime-cache/r10-neo4j-operations-20261016`，Linux owned 控制路径为 `/tmp/dianzi-r10-neo4j-operations-20261016`。未操作其他容器、卷、来源库、Redis DB、索引或 MinIO。

## 实际资源与健康

只复用原 daemon：`/tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock`，Server 29.2.0、`LiveRestoreEnabled=false`，当前 boot ID `8ee1634d-0b2e-4279-8426-2ae855e3b997`。

镜像为 `docker.io/library/neo4j@sha256:57ecb62bbb0c41c98fb69e08ee014c959926f3bd16ee8ef466c4a1e298f6157c`。root 原核 OCI config 为 `a6ac4fbb3863670c42fd72cb8fbcb500ba5c2e67538eaac98e45f56936807c81`；本 Docker 29 containerd 存储实际 image ID 使用上述 manifest digest，不能混称 config digest。compressed layers 351,667,694 bytes、Docker image summary 351,674,986 bytes；拉取前磁盘可用 970,976,088,064 bytes，后可用 970,131,750,912 bytes。全 daemon 文件系统差额 844,337,152 bytes，可能包含同期服务 IO，未声称是精确独占解压大小；实际低于新增 4 GiB 上限。拉取命令 exit 0、没有网络重试或新镜像选择。

资源 ID/container name 为 `dianzi-r10-neo4j-test-20261016`；唯一卷 `dianzi-r10-neo4j-test-20261016-data`，mountpoint 为原 daemon data-root 下该精确卷的 `_data`，inode **701675**。标签绑定 owner、resource ID、creator token 和不可续期截止。

当前 CID 为 `c0d49f69954c9d7b5d3ab0420347b99d96e9fdbeaf87ece3032b8c3430cd41ab`。关闭统计前成功监督段 started_at 为 **2026-10-16T07:40:02.001151+08:00**；其实际 Docker ended_at 为 **07:46:25.290410+08:00**。关闭统计后新段 started_at 为 **2026-10-16T07:46:29.739950+08:00**；这些段不拼成连续运行。固定截止为 **2026-10-16T19:35:43.312788+08:00**，自首次凭据准备最多 12 小时，早于父 WSL 2026-10-17T21:49:15+08:00 截止。没有重置或延长预算。

HostConfig 与内核实际均为 memory 1,610,612,736 bytes、memory+swap 同值（内核 swap max 0）、CPU 1、pids 128；heap initial/max 和 pagecache 实际各 `512.00MiB`，transaction timeout `3s`、lock acquisition `2s`。restart policy no，日志 json-file 单文件 10 MiB。cap-drop ALL，entrypoint 所需 CHOWN/SETUID/SETGID/DAC_OVERRIDE/FOWNER 五项；no-new-privileges 和默认 seccomp 生效。Java 实际 UID/GID 7474、CapEff 0、NoNewPrivs 1、Seccomp 2；tini 保留五项入口能力。两个 owned Java sockets 在 `/proc/net/tcp6` 呈 IPv4-mapped 127.0.0.1，分别 27687/27474，无其他 owned listener。没有公网监听。

HTTP 200 返回 5.26.32/community；Linux 与 Windows 两端本地连接通过。官方 Python driver **6.4.0** 由 root 唯一安装，本执行者没有改依赖。真实认证、`RETURN 1` 及 11 个运行配置字段读取通过，server agent `Neo4j/5.26.32`、Bolt 5.8；没有查询 PG 或业务事实。driver `telemetry_disabled=True`。

初段服务端 `dbms.usage_report.enabled=true` 由启动日志和 `SHOW SETTINGS` 确认。root 明确批准后，在同 CID 的 owned neo4j.conf 精确增补 `dbms.usage_report.enabled=false`、官方 validate-config exit 0，再同 CID stop/start。原/新配置 SHA 分别为 `37e7c336da67cc68b886ceed48f1c46fd45ef01de81b7c1dbf84e5f95c2206f7` / `a6bcb80fcbe57aeddf4c69d51a3e8637e70449b36c8f286eb9506866870abc4b`；原配置留私有目录，不输出完整配置。新段 `SHOW SETTINGS` **false** 已真实验证；初段曾开启统计的事实保留在 `usage_reporting_before/`，没有声称历史一直关闭。

## 真实命令与结果

完整固定 argv、cwd、timeout、起止与 exit 见 run 内同名 `*.command.json`；标准前缀为 `wsl.exe -d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_20261016/`。后台 Windows 启动器均 `Start-Process -WindowStyle Hidden`，其 null exit 明确是仍运行，不是完成退出。

| 检查 | 实际 +08:00 时间 | exit/数量 | 结果 |
|---|---|---|---|
| root 独立端口/名字检查 | 07:31:43 / 07:33:22 | 0 | Windows/WSL 两端空闲；exact container API 404、卷不存在 |
| `runtime.py preflight` | 07:33:35 | 0 | 本人独立 bind 两端口、名字/卷/owned path 不存在，空间足够 |
| `runtime.py pull` 内 pull | 07:33–35 | 0 | 精确批准 digest 已实际下载；外层首次 image inspect 失败，见下 |
| `runtime.py verify_image` | 07:35:36–37 | 0 | manifest ID、repo digest、Linux/amd64 与空间复核 |
| `prepare_credentials.py` / 隐藏 launch | 07:35:43–44 | 0 | 当前用户 DPAPI、固定 deadline；秘密不进 argv |
| guard `test_runtime_guard.py` 最终 | 07:48:48–49 | 0 / **14 tests** | 其他 CID/creator/digest/mount/boot/创建时间、PID 复用、check 不 stop、旧心跳、伪 creator、过期截止负例 |
| `runtime.py snapshot` | 07:40:28–29 | 0 | HTTP/socket、内核四限额与身份链 |
| `runtime.py stop --check` | 07:40:30 | 0 | 只读检查当前 exact CID/boot/digest/creator/mount/PID ticks，不停止服务 |
| `bolt_smoke.py` | 07:41:07–10 | 0 | driver 6.4.0 真实认证、RETURN 1、11 设置；业务事实查询 0 |
| `inspect_security.py` 最终 | 07:42:16–17 | 0 | owned Java UID/CapEff/seccomp/NNP、两个精确 loopback sockets、envfile 已删除 |
| `windows_health.py` | 07:42:17 | 0 | Windows 两端口和 HTTP200 |
| Ruff / format check 最终 | 07:48:47–49 | 0 | 本运行包静态检查通过 |
| owned 单项配置 / `neo4j-admin server validate-config` | 07:46:18–22 | 0 | 只关闭 dbms.usage_report.enabled，保留原配置/hash |
| 同 CID stop / start 新段 | 07:46:25 / 07:46:29 | Docker 0 / 0 | 实际 stop 容器 exit 1，见下；原卷/密码/截止均保留 |
| 新段 HTTP / authBolt / stop check | 07:46:43–47 / 07:47:06–11 | 0 | HTTP200、实际统计 false、认证、RETURN 1、同 CID 创建/PID 身份链 |
| 新段 kernel / Windows health | 07:47:06–08 | 0 | 五 caps/NNP/seccomp/UID与回环限额保持 |

上述 14 个测试仅资源 guard 单元，不计 R10 业务测试、六关系质量、性能或外部 live。业务作者另执行真实投影用例，其报告和固定业务 SHA 才是业务验证依据。

## 失败、修复与停止链

初次镜像 white-list inspect 取 `.Config.User` 时 CLI 拒绝不存在的键（exit 1）；移除该非必需字段，显式 `--platform linux/amd64` 后复核成功。原 pull 日志保留，未把镜像下载成功偷换成整个初次命令通过。

首次 CID `74a8b3d5916429588d9d93660381395e18638de3864f69574553b70aa7ad7689` 于 07:35:47 start，07:35:49 自主 exit 1、OOMKilled false；日志唯一错误为 chmod `/var/lib/neo4j` Operation not permitted。原因是本执行者设置过紧的 cap 白名单缺 FOWNER。root 明确批准增加这一项，并在退出、创建时间、creator、digest、mount、卷 inode 与旧进程身份核实后仅 `docker rm` 此精确已退出 CID，不 force、不删卷；旧材料在 `initial_attempt/`，新容器仍保留原密码/卷/截止。

第二段新 CID 于 07:37:56 start，07:37:57 guardian 精确停止它、exit 143：监督换段错误读取了旧 CID 心跳。这是本执行者的 guard 缺陷，未声称第二段健康成功。原心跳 bytes/hash、停止记录和新创建命令在 `stale_heartbeat_attempt/`。修复将心跳绑定 expected CID、creator token、supervisor boot/PID/start ticks 和 generation，保持原 45 秒门槛；root 批准只恢复这个已退出的新 CID。旧心跳与 termination 先归档；成功段源码在 `launched_runtime.py.txt`，实际 SHA 与 resource_started 绑定。没有再次删除/重建容器或修改卷。

早期 Ruff SIM117/import 顺序/C402 失败已实际修正；内核探针最初仅预期 IPv4 tcp 表而断言失败，真实观察是 Java 的 IPv4-mapped IPv6 loopback，最终按内核地址解码核验，未扩大允许地址。早期 HTTP snapshot 失败时容器已退出或被 guardian 停止，未记 passed/skip。

监督循环同时核墙钟截止与 monotonic 截止、exact CID/creator/digest/mount/boot/PID 创建身份、guardian 状态；每 5 秒写 generation 绑定心跳。独立 guardian 核 supervisor 身份、同段心跳及同一截止；失联时仅对匹配的 exact CID 受控 stop。实际第二段 guardian stop 提供一次真实停止记录；未来截止效果及最终版故障注入未提前标 passed。全部 owned stop 只使用下面入口：

`wsl.exe -d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_20261016/runtime.py stop --check`

移除 `--check` 才是提前停止当前精确 owned CID。不要按名字猜测、数字 PID 单独 kill、复跑首次 create/rebuild 或改变 WSL 全局服务。

统计关闭前的受控 stop 又暴露了真实未关闭项：日志 `[FATAL tini] Unexpected error when forwarding signal: Operation not permitted`，容器 exit 1、Docker stop 命令 exit 0。五项能力不含 KILL、tini 为 root、Java 为 UID 7474，转发权限拒绝指向缺 CAP_KILL；尚未追加该能力做对照实验，根因判断未由独立 reviewer 关闭。PID1 退出后 Docker 实际停止该 CID（state Running false/Pid 0），之后同 CID 已恢复健康。**优雅退出 `failed`**，有界 exact-stop 效果已观测；不得用后续健康成功抹掉此失败。本执行者遵守 root 的本次仅单项配置/同 CID 重启范围，没有自行加入第六项能力或再重建容器。此缺口已立即交 root 和新独立 reviewer，资源子包仍 awaiting_review/partial。

## 凭据、材料与交接

凭据为本实例独立强随机密码，用户名 neo4j。Windows 当前用户 DPAPI 文件仅在 `D:/dianzi-private/r10-neo4j-test-20261016.dpapi`；受保护 JSON 字段只有 `NEO4J_TEST_BOLT_URL`、`NEO4J_TEST_USERNAME`、`NEO4J_TEST_PASSWORD`、`resource_id`、`deadline`。临时 Linux auth envfile 位于 owned 0700 路径、权限 0600，Docker create 后立即核绝对归属并删除。没有密码出现在提示、argv、报告或前端；没有导出 Config.Env/raw full inspect。原始启动日志仅仓外缓存，仓库只存扫描/脱敏副本；最终实际值及编码形态扫描结果见 `logs_and_secret_scan.json`。

使用官方 [Neo4j 5 配置](https://neo4j.com/docs/operations-manual/5/configuration/configuration-settings/) 与 [Docker 环境变量变换规则](https://neo4j.com/docs/operations-manual/current/docker/configuration/)，每个使用字段均核对原名，非 Enterprise/APOC/GDS。[Docker capability 文档](https://docs.docker.com/engine/containers/run/) 支持 FOWNER 的目录权限用途；[image inspect 文档](https://docs.docker.com/reference/cli/docker/image/inspect/) 支持指定平台。采用成熟组件而非自制图引擎；Community 为 [GPL v3](https://neo4j.com/legal-terms/)，官方 [Python driver 6.4.0](https://pypi.org/project/neo4j/6.4.0/) 为 Apache 2.0。本记录是材料来源和实际选择，不冒充许可证法律审查。

合同偏差只涉及本执行者已证启动/监督错误及 root 批准的受控修复，没有公共合同或分母变化。E1/R2 证据仅支持有限隔离资源运行与停止管理；不替代 A1/F2/P2 图投影、T54 连续观察、业务链、独立资源安全 review 或阶段门。下一动作是业务作者最终真实投影验证、root 处理 tini 优雅退出缺口，再由未参与本包实现者复核固定源码/日志。运行管理权交回 root；本包不签 accepted。
