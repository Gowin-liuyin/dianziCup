# G-A / R01 · 真实隔离测试资源

文档首次创建时间：2026-10-14T22:16:06+08:00。文档写作开始时间：2026-10-14T22:13:37+08:00。首次写作结束：2026-10-14T22:17:13+08:00；最后更新时间：2026-10-14T23:35:21+08:00。本次续包写作开始：2026-10-14T22:51:38+08:00；本次写作结束：2026-10-14T23:35:21+08:00。

执行者：`/root/r01_resources`；输入代码SHA：`15d0272bd2a9e25d19397d8147e9c3cbe6016f9b`；分支：`codex/full-delivery-recovery`。资源操作实际窗口：2026-10-14T22:07:35+08:00—2026-10-14T22:12:14+08:00；证据自检：2026-10-14T22:13:37+08:00与2026-10-14T22:16:43+08:00。本包状态：`awaiting_review`；本包实现：`complete`；**R01整卡/阶段未验收，未commit/push，不登记accepted。**

## 1. 用户问题、授权与边界

本包为R01/T03/E1/R2准备真实PG、pgvector和Redis，避免API/worker的持久化验收继续依赖内存对象。独立资源准备不依赖R00业务合同已生效；R00仍由主控取得独立意见，不凭本包越过阶段门。

已读AGENTS、执行地图、恢复R01卡、原T03、架构、08编码/09运维合同、状态/交接、最新Ponytail插件5.2.0正文、上一socket根因报告。复用上一Agent已真实运行的Docker29.2.0 daemon、日志探针和平台持久卷能力；采用Ponytail full。新增只有隔离服务启动/取证脚本及本报告，不引入应用框架、不替代业务数据库实现。

文件所有权仅为本报告和`reports/runs/recovery_r01_resources_20261014/`。没有修改业务、infra/Compose、公共schema、迁移、依赖锁、状态或用户文件；未读取模型/测绘秘密、盲测、附件或开发`.env`。唯一私有输入是本包新生成的随机test连接配置，在仓库外root私有路径；仅用于本包资源验证和主控后续测试注入，不进入报告或终端。

主控补充了最小测试环境合同：`DIANZI_TEST_RUN_ID=r01_20261014`；PG库`test_dianzi_r01_20261014`、用户`test_dianzi_r01`，端口25432；Redis26379；项目`dianzi-test-r01_20261014`。在创建库前准确采用，不替换已有库。首次预检这些端口和本项目容器/卷不存在；既有退出hello容器保留。

## 2. 实际资源与版本

运行发行版：`Ubuntu-22.04`。精确CLI前缀：

```powershell
wsl.exe -d Ubuntu-22.04 -u root --exec /tmp/dianzi-docker-static-r01-20261014/portable/docker/docker --config /tmp/dianzi-docker-static-r01-20261014/runtime/client-config --host unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock
```

前缀后接`version`、`ps`、具体容器命令或`compose`。不使用Windows默认context、不暴露daemon TCP、不连接旧Desktop数据。本包复核server29.2.0/API1.53与项目cgroup限额；上一包给daemon的原截止仍为**2026-10-17T21:49:15+08:00**，没有因新增服务延长。监督器与原Desktop问题见[G-A-R01-socket-root-cause](../reviews/recovery/G-A-R01-socket-root-cause.md)。

| 资源 | 实际版本与运行镜像 | 身份与限额 |
|---|---|---|
| PostgreSQL+pgvector | PostgreSQL16.14，扩展0.8.2；`pgvector/pgvector@sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc` | 容器`dianzi-test-r01_20261014-postgres`；1GiB、0.75CPU、128pids、swap0 |
| Redis | 7.4.11；`redis@sha256:4fa24486b8bcca8eec45ee0eb166edc674795e53a2b53d1a9ef263eecebaac85` | 容器`dianzi-test-r01_20261014-redis`；256MiB、0.25CPU、64pids、swap0 |
| Compose插件 | 5.0.2，31,327,024 bytes | 仅专用`runtime/client-config/cli-plugins/docker-compose`，实际version/help退出0 |

PG镜像取自[pgvector官方维护项目](https://github.com/pgvector/pgvector)，获取tag`0.8.2-pg16`后按实际RepoDigest运行；Redis获取既有批准7.4主版本tag后按实际RepoDigest运行。上表不把旧Compose声明的postgres16.4称为实际版本。Docker返回的镜像SHA是本次实际获取身份，不是仅搜索结果推断。

[Compose5.0.2官方发布](https://github.com/docker/compose/releases/tag/v5.0.2)及同发布asset `.sha256`经正常HTTPS/TLS取得；参考与实际二进制SHA256均为`2d880f723d3da7c779c54fdaea91a842fca8af55d1397f1ed8d7cbab3dd7af67`。未写`/usr/bin`、全局CLI配置或用户默认插件目录。安装位置遵循[官方手动插件路径](https://docs.docker.com/compose/install/linux/)，将DOCKER_CONFIG限定专用client-config。**插件可用只证明工具就绪，仓库Compose部署尚未实施/验收。**

## 3. 隔离、秘密与持久卷

Daemon bridge为none，因此使用host网络；PG服务参数明确`listen_addresses=127.0.0.1`、`port=25432`，Redis配置明确`bind 127.0.0.1`、`port 26379`、protected-mode、随机requirepass。2026-10-14T22:12:14+08:00读取`ss`的**Local Address**列只有两个127.0.0.1端口；没有凭Docker `-p`映射推断host网络隔离。

PG启用TCP SCRAM认证；随机256bit test密码由标准库secrets生成，POSTGRES_PASSWORD_FILE指向只读挂载。Redis密码在只读配置文件。两镜像账号uid经各自`id -u`真实取得999，挂载文件按该uid所有、mode600；主控私有连接JSON保持root600、父目录700。没有把密码放Docker环境/CLI参数、日志或完整DSN中。容器日志各local最多2×10MiB、restart=no；整体项目cgroup仍8GiB/2CPU/2048pids。2026-10-14T22:12:14+08:00通过真实容器PID→`/proc/<pid>/cgroup`→内核子节点复核上表每项限额，不仅读取Docker配置。

专用持久卷：`dianzi-test-r01_20261014-postgres-data`和`dianzi-test-r01_20261014-redis-data`；均带`dianzi.project`与`dianzi.mode=test`标签。PG唯一事实库角色不变；Redis用于排队/缓存，并未加入另一套业务事实。

仓库外私有文件：

```text
/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json
```

键名：`DIANZI_TEST_RUN_ID`、`TEST_DATABASE_URL`、`TEST_REDIS_URL`、`NO_PROXY`，以及`project`、`postgres_host/port/database/user/password`、`redis_host/port/password`、`created_at`。`TEST_DATABASE_URL`是SQLAlchemy psycopg格式，`TEST_REDIS_URL`带本地测试密码；只由主控捕获到内存、注入受控子进程环境，不能`cat`到终端/报告。`NO_PROXY=127.0.0.1,localhost`用于保证本地服务不走外部IO代理。当前test PG初始化账号为本库迁移用superuser，只能用于隔离测试，不能作为产品部署账号。

## 4. 已观察行为与问题台账

| ID/发现时间 | 输入、预期与实际 | 根因/影响/处理 |
|---|---|---|
| RESOURCE-01 / 2026-10-14T22:07:35+08:00 | 预检专用端口/容器/卷；均未占用，daemon真实ready | 新独立资源可以创建；没有触碰用户既有容器/卷 |
| PROBE-01 / 2026-10-14T22:11:55+08:00 | 预期检查两个服务不公开；初始断言把`ss`输出中Peer Address的`0.0.0.0:*`也当作Local公开监听，探针exit1 | 探针列选择错误，不是服务暴露。最小修复只检查Local Address列。2026-10-14T22:12:14+08:00复验exit0、两个127.0.0.1，原失败日志保留。资源脚本修改无业务SHA，源hash记录于evidence_index |
| TOOL-01 / 2026-10-14T22:10:12+08:00 | Docker restart使用`--time`返回弃用提示但实际退出0 | 不影响本轮重启证明；后续应使用`--timeout`，本包保留实际调用，不回改历史日志 |

PG已写入独立`r01_resource_probe`持久测试行和真实vector(3)，距离计算为0。2026-10-14T22:10:12+08:00—2026-10-14T22:10:14+08:00同时重启PG/Redis后，PG行及向量仍存在，Redis AOF键仍存在。没有进行drop、downgrade、清卷或开发库操作。

2026-10-14T22:11:05+08:00Windows既有backend psycopg经loopback真实读取该持久行并提交`r01_windows_probe`新行，核对数据库/用户名/扩展身份。错误PG密码拒绝；Redis未认证PING拒绝、错误密码拒绝，正确认证PING及持久键读取通过。这些输入明确是test数据，不含用户资产。

## 5. 命令与验证层级

工作目录均为`D:\dianzi`。原始命令、精确开始/结束秒及毫秒、退出码、stdout/stderr见[run目录](../runs/recovery_r01_resources_20261014/)的每个`<name>.json`和`.stdout/.stderr.log`；内层Docker/curl命令亦逐条输出，时间统一+08:00；Docker自身State内UTC标注Z保留。

| 探针 | 实际时间(+08:00) | exit | 可证明的结果 |
|---|---|---:|---|
| resource_preflight | 2026-10-14T22:07:35+08:00—2026-10-14T22:07:38+08:00 | 0 | server真实版本、项目总限额、端口及资源身份可创建 |
| postgres_pull | 2026-10-14T22:07:48+08:00—2026-10-14T22:08:34+08:00 | 0 | pgvector官方镜像拉取与实际digest |
| redis_pull | 2026-10-14T22:07:48+08:00—2026-10-14T22:08:15+08:00 | 0 | Redis官方镜像拉取与实际digest |
| compose_checksum | 2026-10-14T22:08:38+08:00—2026-10-14T22:08:40+08:00 | 0 | 发布者校验文件获取 |
| services_start | 2026-10-14T22:09:16+08:00—2026-10-14T22:09:23+08:00 | 0 | 专用卷/容器/secret文件模式与镜像账号真实启动 |
| compose_download | 2026-10-14T22:09:16+08:00—2026-10-14T22:09:38+08:00 | 0 | 官方二进制获取；无TLS关闭 |
| services_smoke | 2026-10-14T22:09:34+08:00—2026-10-14T22:09:36+08:00 | 0 | PG SELECT/写读/vector与Redis认证PING/SET/GET，容器非OOM |
| windows_loopback | 2026-10-14T22:09:38+08:00 | 0 | Windows TCP可达两个127端口；仅TCP，不算认证SQL |
| services_restart_persistence | 2026-10-14T22:10:12+08:00—2026-10-14T22:10:14+08:00 | 0 | 两容器重启后数据保留 |
| compose_install_verified | 2026-10-14T22:10:12+08:00—2026-10-14T22:10:13+08:00 | 0 | 发布者SHA匹配；5.0.2/version/help真实可执行 |
| windows_authenticated_services | 2026-10-14T22:11:05+08:00 | 0 | Windows真实PG提交、Redis认证读、两类错误密码拒绝 |
| kernel_limits_listeners | 2026-10-14T22:11:55+08:00—2026-10-14T22:11:56+08:00 | 1 | 探针误判，保留失败，不计服务失败或passed |
| kernel_limits_listeners_recheck | 2026-10-14T22:12:12+08:00—2026-10-14T22:12:14+08:00 | 0 | 内核逐容器限额、Local列127监听、私有文件600 |
| evidence_validation | 2026-10-14T22:13:37+08:00 | 0 | 当时13条receipt/4源语法与SHA核验；实际test密码/DSN未出现 |
| evidence_validation_final | 2026-10-14T22:16:43+08:00 | 0 | 当时14条receipt/4源与报告一起检查；test密码/DSN未出现 |

这些是有断言的真实资源smoke，不是pytest业务测试总数。应用测试执行数**0**。unit/contract/frontend/e2e/live来源模型/manual均`not_run`；资源integration smoke与认证负例已执行通过，**应用integration/security仍not_run**，不把资源健康计为业务认证正确。Redis容器health只验证NOAUTH协议响应；完整认证PING另有上述真实smoke/Windows证据，不能只从health字段推断授权或数据完整性。

首包证据截止时OpenSearch/Neo4j/MinIO及产品API/worker/scheduler、应用迁移、UI链路、备份恢复、正式性能均未运行；续包OpenSearch真实结果见第9节，其它项本包仍未验证。未调用生成/embedding/reranker或测绘API，无产品API消费；模型会话费用unknown。未把本包数分钟观察算持续稳定运行。

## 6. 安全停止、回滚和交接

可先用同CLI前缀`inspect`核对两个名称/标签确属本项目，再`stop --timeout 10`仅停止这两个容器。**本轮未执行stop验收**；命令语义会保留命名卷，但C06仍须主控后续真实执行并检查卷存在，不能将建议当日志。恢复为同前缀`start`两个明确名称并重新smoke；不会重新生成密码或覆写现有私有配置。

不使用`compose down -v`、全局prune或删除任何卷。若需回收本包资源，先备份测试数据库，再核对标签、容器挂载及真实绝对路径，单独处理本包对象；当前保留给主控和独立审查。Compose插件可仅从已核对专用client-config子目录撤除；未测试撤除，不改变宿主默认插件。Docker supervisor的关闭和cgroup委派回滚规则由上一socket报告维护，不能在其它项目依赖控制器时撤销父级委派。

本包产物可复跑只读/既有测试资源操作：`resources.py smoke`、`resources.py kernel-limits`、`windows_probe.py`。`preflight/start`只用于首次新资源且有拒绝覆盖断言；不要在已创建状态直接重跑start。当前secret目录及named卷保留，WSL/daemon再次启动必须先验证实际生命周期和deadline，不假定临时缓存永远存在。

下一步由主控接入R01默认应用、测试DSN守卫与真实Compose项目，再跑原T03/R01全验收；本包没有签整T03、R01或G-A。资源问题与原Desktop错误区分：等价资源已真实ready，原Desktop旧AF_UNIX对象仍未修复。

## 7. 文档修订记录

- 2026-10-14T22:16:06+08:00：首次落盘整理实际资源、失败探针、版本和secret边界；写作起点是整理开始，文件创建时间为实际落盘，不填应用通过。

- 2026-10-14T22:17:13+08:00：补最终证据自检及写作结束时间，未改资源或业务实现。

## 8. 独立worktree资源续包（G-A / R01，尚未整卡验收）

本次写作开始：2026-10-14T22:51:38+08:00；输入SHA：`f0b154ee0e10100bc9a9d293ebeded13926d0a42`。主控现有PG25432/Redis26379仅归主控；本轮没有restart/delete/改配置这些既有服务。文件边界仍只有本报告和新run目录`reports/runs/recovery_r01_worktree_resources_20261014/`；续包状态`awaiting_review`、本包实现`complete`，不改进度、不commit/push、不签accepted。

按照主控冻结的最小test环境合同，2026-10-14T22:42:24+08:00—2026-10-14T22:42:27+08:00创建两组独立容器、卷、port、数据库、用户、随机密码与外部700目录/600配置。沿用已获取的同一PG/Redis digest，未重复下载依赖。每组PG512MiB/0.4CPU/128pids、Redis128MiB/0.1CPU/64pids、swap0；真实内核限额与服务Local监听127列已于2026-10-14T22:43:29+08:00复核。

| 所属worktree | run_id/库/用户 | 端口/项目 | 私有配置 |
|---|---|---|---|
| quality | `r01_quality_20261014` / `test_dianzi_r01_quality_20261014` / `test_dianzi_r01_quality` | PG25434 / Redis26381；`dianzi-test-r01_quality_20261014` | `/tmp/dianzi-docker-static-r01-20261014/runtime/test-services-r01_quality_20261014/connection.json` |
| frontend | `r01_frontend_20261014` / `test_dianzi_r01_frontend_20261014` / `test_dianzi_r01_frontend` | PG25435 / Redis26382；`dianzi-test-r01_frontend_20261014` | `/tmp/dianzi-docker-static-r01-20261014/runtime/test-services-r01_frontend_20261014/connection.json` |

配置键为DIANZI_TEST_RUN_ID/TEST_DATABASE_URL/TEST_REDIS_URL/NO_PROXY及分项连接元数据，格式沿用第3节，不能回显整个JSON。容器/命名卷以对应项目名称加`-postgres/-redis/-postgres-data/-redis-data`命名，均为本轮新建，拒绝覆盖既有名称/目录/端口。

2026-10-14T22:43:28+08:00—2026-10-14T22:43:29+08:00通过Windows现有psycopg真实认证SELECT，核对库、用户、服务地址与端口，迁移前public表为空；没有替应用执行迁移、drop或downgrade。两组错误PG密码拒绝；Redis未认证PING、错误密码均拒绝，正确认证PING返回PONG。原始证据分别为quality/frontend_start、quality/frontend_windows_auth、quality/frontend_kernel_quota的JSON/stdout/stderr，均exit0。这里的空表是该次迁移前观察，不能在后续应用迁移后继续称为空。

2026-10-14T22:49:25+08:00复核父级memory.max8GiB、cpu.max2CPU、pids.max2048保持原值，实际当时memory.current336,433,152 bytes/pids.current156。各容器CPU上限可共享同一父级额度，后续Search加入后上限之和会超过2，但父级硬限仍限制总执行；不能据此声称各服务同时达到各自峰值或公平性能基线。原daemon deadline不延长。此预算只覆盖本项目Linux daemon/容器，不把Windows编程工具与API进程说成同受该cgroup限制。

复用冻结的既有资源辅助脚本（SHA256 f152515405e7a1462a9d01d24815c7a3f5ebe2548c380e589a67c436caf5baf0），本轮按进程内独立profile限定资源身份和配额，没有修改旧源与旧证据。首次import生成一枚本包自己的resources.cpython-310.pyc，已精确核对父目录后删除该文件；后续设置dont_write_bytecode，未递归删除或清用户目录。该局部生成文件清理没有单独时间receipt，不能补造时间。

root-only OpenSearch续包现在已取得真实ready与接口证据，详见第9节；保留此前下载限时失败和探针错误，不回改历史日志。

本轮未执行应用unit/contract/frontend/e2e/live/manual；独立资源integration/认证负例的证明仅限上述实际输入，不能计作R01/G-A业务验收。
## 9. root-only OpenSearch真实闭环与最终续包交付

Search本包实现complete/awaiting_review，代码/运行版本仍引用第8节输入SHA；资源测试脚本各自实际SHA见新run目录evidence_index。不是R01、原T03或阶段验收。最终资源证据截止2026-10-14T23:03:03+08:00，本文更新时没有替主控测应用。

下载来源采用[OpenSearch2.17官方Docker文档](https://docs.opensearch.org/2.17/install-and-configure/install-opensearch/docker/)列出的DockerHub与Amazon ECR；两份实际manifest的linux/amd64 digest均cc2b752873d6f16d077b4944368f5bb0e8923a5133419836a33d0ad8ad6692f2，主压缩层912,057,029 bytes。先前55s和180s客户端预算不足，第二次已有层完成，未从超时推定认证或证书失败。官方ECR唯一一次300s有界获取在2026-10-14T22:56:17+08:00真正成功（pull exit0，实际约97s），没有关闭TLS校验。

已运行镜像：`opensearchproject/opensearch@sha256:7b9517dff561f54456fad947f11820fa595a340fd1034fc63d57b77f724b3f8f`，实际version2.17.0/amd64。Docker29的image.Id实际指manifest-list descriptor，不能将它和平台config blob hash884999…比较；这个本包错误断言曾让外层ECR探针exit1，虽然内层pull已经exit0。2026-10-14T22:56:52+08:00独立image inspect核明字段，2026-10-14T22:57:45+08:00定向复验exit0；本地tag仅补此前不存在的DockerHub同版本名称，拒绝覆盖不一致镜像，未push registry。失败日志保留。

专用容器`dianzi-test-r01_20261014-opensearch`、持久卷同前缀`-opensearch-data`，test标签；non-root uid1000、2GiB/0.75CPU/256pids、swap0、JVM512MiB、日志local2×10MiB、restart=no，与其余服务共用原8GiB/2CPU/2048pids父级及原deadline，不改global sysctl。实际host vm.max_map_count保持65530；局部`node.store.allow_mmap=false`使用非mmap存储，[_nodes实际设置](../runs/recovery_r01_worktree_resources_20261014/opensearch_live_smoke.stdout.log)确认false。此静态选项由[官方配置说明](https://docs.opensearch.org/latest/install-and-configure/configuring-opensearch/configuration-system/)描述；本包另外在指定2.17.0真实验证，不仅凭新版页面推测兼容。

依据实际镜像entrypoint，使用其现有`DISABLE_PERFORMANCE_ANALYZER_AGENT_CLI=true`避免无用途的PA旁路进程，并把供应商PA配置的web bind限定127、备用REST29600/RPC29650。保留Apache许可证及供应商注释，没有重写entrypoint。2026-10-14T23:01:42+08:00查询主Java PID所有监听只见HTTP29200/transport29300，两者为内核IPv4-mapped127.0.0.1，未开PA监听；真实内核memory/cpu/pids/swap和600配置已验证。第一次quota探针直接匹配IPv4字符串而误拒Java的`[::ffff:127.0.0.1]`（exit1）；只读ss定位后复用标准库ipaddress归一，并用0.0.0.0反例断言保留公开监听拒绝，复验exit0，未更改服务绑定或放宽为任意地址。

该节点沿用批准的开发隔离方式：security插件关闭、仅loopback HTTP，没有认证或TLS。没有降低远端下载的TLS证书验证，但**这里不提供生产权限/TLS证明**；不能公开发布或给产品容器放私有业务数据。指定2.17文档提示该版本不再维护，本包遵守主控的固定版本输入，不将测试节点称为生产可用。

2026-10-14T23:00:10+08:00真实GET版本、cluster green；创建显式test索引r01-resource-smoke（1分片/0副本），写入`mode=test`合成文档并BM25查询命中1条；不能将它计为真实来源采集、模型或问答性能。2026-10-14T23:01:42+08:00 Windows标准库客户端经显式代理旁路读取同文档/版本/cluster green成功。没有应用权限/租户检索验收，也没有重启Search或做备份恢复。

第三个私有配置位于：`/tmp/dianzi-docker-static-r01-20261014/runtime/test-opensearch-r01_20261014/connection.json`，root600、父目录700。键为DIANZI_TEST_RUN_ID（root原run_id）、TEST_OPENSEARCH_URL、OPENSEARCH_URL、NO_PROXY、created_at、image_digest、test_service、test_security_plugin_disabled；不含模型/API密钥。主控只对自己的root应用注入，quality/frontend不复用此节点来声称独立Search集成。

| 新run探针 | 实际时间(+08:00) | exit | 结论 |
|---|---|---:|---|
| quality_start / frontend_start | 2026-10-14T22:42:24+08:00—2026-10-14T22:42:27+08:00 | 0 / 0 | 两组独立新资源与秘密路径 |
| quality_windows_auth / frontend_windows_auth | 2026-10-14T22:43:28+08:00—2026-10-14T22:43:29+08:00 | 0 / 0 | Windows迁移前PG身份/空表，PG/Redis认证正负例 |
| quality_kernel_quota / frontend_kernel_quota | 2026-10-14T22:43:28+08:00—2026-10-14T22:43:29+08:00 | 0 / 0 | 各自PG512MiB/.4CPU、Redis128MiB/.1CPU、内核pids/swap与127监听 |
| opensearch_pull | 2026-10-14T22:45:41+08:00—2026-10-14T22:46:37+08:00 | 1 | 55s本包限时，初版helper未打印partial stdout，日志缺口明确保留 |
| opensearch_pull_retry | 2026-10-14T22:47:58+08:00—2026-10-14T22:50:59+08:00 | 1 | 180s限时，内层124及partial层进展已保留 |
| project_resource_inventory | 2026-10-14T22:49:24+08:00—2026-10-14T22:49:25+08:00 | 0 | 父级配额及host map_count65530真实读取 |
| opensearch_manifest_dockerhub / opensearch_manifest_ecr | 2026-10-14T22:52:39+08:00—2026-10-14T22:52:55+08:00 / 2026-10-14T22:52:39+08:00—2026-10-14T22:52:49+08:00 | 0 / 0 | 两官方平台manifest相同及大层尺寸 |
| opensearch_pull_ecr | 2026-10-14T22:54:40+08:00—2026-10-14T22:56:19+08:00 | 1 | 内层pull实际0；本包错误身份断言1，不能说完整失败或完整通过 |
| opensearch_image_identity / opensearch_identity_recheck | 2026-10-14T22:56:51+08:00—2026-10-14T22:56:52+08:00 / 2026-10-14T22:57:44+08:00—2026-10-14T22:57:45+08:00 | 0 / 0 | 实际Id/Descriptor与版本，最小探针修复和新local tag |
| opensearch_configuration_read | 2026-10-14T22:57:48+08:00—2026-10-14T22:57:49+08:00 | 0 | 真实官方entrypoint/uid/PA控制配置，无推测变量名 |
| opensearch_start | 2026-10-14T22:58:27+08:00—2026-10-14T22:58:31+08:00 | 0 | 专用test卷、node启动与局部配置 |
| opensearch_health_state | 2026-10-14T22:59:28+08:00—2026-10-14T22:59:29+08:00 | 0 | 真实healthy，日志保留前两次startup curl7与2026-10-14T22:59:01+08:00起green |
| opensearch_live_smoke | 2026-10-14T23:00:09+08:00—2026-10-14T23:00:10+08:00 | 0 | 真实版本/健康/写读/BM25/节点实际配置 |
| opensearch_kernel_limits | 2026-10-14T23:00:09+08:00—2026-10-14T23:00:11+08:00 | 1 | IPv4-mapped格式探针错误，非实际公开监听 |
| opensearch_listeners_read | 2026-10-14T23:00:46+08:00 | 0 | ss真实IPv4-mapped loopback定位 |
| opensearch_kernel_limits_recheck | 2026-10-14T23:01:42+08:00—2026-10-14T23:01:43+08:00 | 0 | 内核2GiB/.75CPU/256pids/swap0和主节点全部loopback监听 |
| windows_opensearch_read | 2026-10-14T23:01:42+08:00 | 0 | Windows真实连接/版本/健康/显式test文档读取 |
| worktree_evidence_validation | 2026-10-14T23:03:02+08:00—2026-10-14T23:03:03+08:00 | 0 | 当时22条receipt、5份源语法/SHA与报告检查，三个配置600，test秘密值无命中 |

问题关闭仅指对应最小探针复验成功；下载预算与字段/IPv4-mapped错误分别记录，不混为同一个“网络修好了”。该次正式应用测试数量仍0，unit/contract/frontend/e2e/live/manual以及应用integration/security均本包not_run。资源integration与认证负例、Search真实读写证据可以用于后续实施资源前置；不替代原卡六项验收、独立review和阶段门。

保留三组PG/Redis及root Search服务，未restart任何新增后已交付资源，未停止/清卷/删除用户文件。停止/恢复仍需核对精确名称及test项目标签后只操作对应容器，不down -v、不prune；Search的持久化重启/恢复本轮未测。首次Search写入smoke脚本需要新索引，不要在已有同名索引上盲目重复创建；独立复核可用Windows只读probe和节点limits，或主控按隔离运行标识新建另一个test索引。最终续包状态awaiting_review，根任务还须自己的集成/审查/阶段文档和push。
- 2026-10-14T23:05:39+08:00：续包完成两worktree隔离与root Search真实资源证据；保留4个失败receipt及最小修复/复验，状态awaiting_review，不签业务通过。

## 10. 最后自检的宿主时间异常与复核

`worktree_evidence_validation_final`开始2026-10-14T23:09:26+08:00、结束2026-10-14T23:23:46+08:00，exit1。首个WSL只读cat声明10s但收到TimeoutExpired；外层声明30s、timed_out=false，却实际墙钟约860s。该现象说明本次计时/调度不能按声明上限解释墙钟，宿主暂停或调度原因尚未确认；不擅自写成WSL、Docker或本包脚本的已证实共同根因，不声称这860s持续采集或稳定运行。前台命令已经结束，未执行kill/restart/global修复。

2026-10-14T23:32:00+08:00单独Windows当前探针exit0：本项目7个loopback TCP端口全部可连接，Search当前HTTP200/cluster green；这只是当前可达性，不替代PG认证或期间连续在线证明。2026-10-14T23:33:11+08:00独立WSL stat退出0、quality配置600，说明该次WSL调用可用，但不解释前次为何超时。2026-10-14T23:33:40+08:00原证据自检定向重跑exit0：当时26条receipt、6份源语法/SHA，三个配置600，实际生成test秘密/DSN在新run及报告均无命中；5个历史失败receipt原样保留，应用测试执行数0。

最终证据截止为2026-10-14T23:33:40+08:00。当前运行资源与配置可交给主控；宿主时序异常作为未解释的观察限制保留，正式持续运行/性能验收需要主控另行观测与如实计入中断。没有修改任何已有服务、延长daemon截止或对外部署。代码/资料本包仍awaiting_review，不能将当前资源smoke当R01/G-A通过。
- 2026-10-14T23:35:21+08:00：统一人可读时间为ISO带+08:00，追加真实宿主时序异常及当前可达/WSL/秘密自检复核；保留失败，未改业务或服务。
