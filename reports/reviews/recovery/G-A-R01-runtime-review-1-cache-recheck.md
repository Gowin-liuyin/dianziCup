# G-A / R01 · 前端缓存 Must fix 1 定向独立复核

What this change does: 为 Vite 两个缓存 tmpfs 明确 node 的 uid/gid 和 0700 权限。三个配置入口新增相同边界回归；保留非 root、只读根文件系统、cap_drop 和健康检查。

**限定复核结果：passed，建议关闭原初审 Must fix 1。** 本结论只针对冻结缓存修复，不写任务 accepted、不 push、不放行整 R01/G-A。原 [初审](G-A-R01-runtime-review-1.md) 和其 87.031 秒冷启失败/EACCES 原始证据未改；Must fix 2（开发安全搜索的 CA/独立认证装配）和 Should fix 3（45 秒 PG 观测自动回归）继续保留，主控另批处理。本次未拿新 UI、TLS 或正式 live 结果充作缓存证据。

## 冻结与范围

只读工作树 `C:\Users\yinha\.codex\worktrees\recovery-r01-infra-fix\dianzi`，分支 `codex/recovery-r01-infra-fix`。源码 `32d16a4a055a46da2f2183f367075db686ddd790`，tree `a92157747d97eded97c81b202456881f8f2f6f5e`；报告/证据 HEAD `eff45e5f933a002d429ded7557dc29fbf48dd729`，tree `c9eb1ad3ca92d0279b4ca15b9a548c6640ec684e`。起止读取均 clean，源码至证据 HEAD 的 infra/tests 差异为空，旧 `0b6a7ad` 是其祖先。

相对旧冻结只有两个源码文件：`infra/compose/compose.yaml` 的 `.vite`、`.vite-temp` 增加 `uid=1000,gid=1000,mode=0700`；`backend/tests/contract/test_r01_compose_configuration.py` 增加 base/test/host 三个参数化用例。`/tmp`、Dockerfiles、backend/src、迁移、锁、前端源码、API、配置合同、CI、scripts 与状态未改变。实查源码差异 27 行增加、1 行替换，没有新增框架或依赖。

已读原初审、真实 AGENTS、00 地图、恢复 11/12 的 R01/R02、T03/T40、02 架构、06 测试、09 运维、状态及最新 Ponytail-review。作者 `reports/tasks/R01-infra.md` 修复附录只作为材料；以下测试由本审独立运行。预期负载沿用受限本地单节点栈，不假定生产吞吐。

仅本次独占项目 `dianzi-test-r01_infra_20261015` 可操作。先实查七容器的 project/service labels、fix WT 的 config_files/working_dir、host network 和 image ID，才停止服务。应用仍用已冻结 backend image `sha256:34b24db5595ed36fc608f39f648d5a9a2288cb03a2ca8f1ecd123044158ea7b0` 和旧前端 image `sha256:de3c406ba2f65e60273a8e545de8ce0eca3bd9b6c54aebd62de33d8bc382c439`；这次没有 rebuild/pull，不能把它说成新 UI 镜像。

只捕获指定 root 0600 仓库外随机测试连接为环境变量，未输出 DSN/密码，未读 DPAPI、KEYS、.env 或其它项目连接。未操作其它项目/裸资源、清库、downgrade、删卷、改变宿主限额或延期。审查仅写本报告与 `reports/runs/recovery_r01_runtime_review_1_cache_recheck_20261015/`。

## 独立测试与真实重启

所有 argv/cwd/Asia/Shanghai 秒起止/exit、XML 和原始 stdout/stderr 在独立 run 的同名文件中。静态读取在 `commands.jsonl` 和编号 raw log。主测试在 fix WT `backend` 执行；Windows pytest 访问专用 Linux Docker/Compose，Linux 容器内另外核验真实用户和写入权限。

| 本审实际命令/检查 | 2026-10-15 +08:00 开始–结束 | 结果 |
|---|---|---|
| `uv run --locked pytest tests/contract/test_r01_compose_configuration.py -q --cov-fail-under=0 --junitxml=…/contract.xml` | 01:51:33–01:51:48 | **19 pass、0 fail/error/skip，exit 0**，14.671 秒 |
| 本项目 `compose … stop frontend` | 01:53:23–01:53:24 | exit 0 |
| 本项目 `compose … start frontend` | 01:53:24–01:53:26 | exit 0 |
| 同一容器重启后的 HTTP/API/PG 和缓存读写 | 01:53:26–01:53:31；01:54:47–01:54:49 完成健康/身份核验 | HTTP 200；两缓存 uid/gid1000、mode700；实际写/读/删除自身探针成功 |
| 全六 profiles `compose … down`，无 volumes 参数 | 01:54:51–01:54:59 | exit 0，8.922 秒 |
| 对关闭前记录的四命名卷 `docker volume inspect … --format {{.Name}}` | 01:54:59–01:55:00 | exit 0，四卷均仍存在 |
| 全六 profiles `up -d --wait --wait-timeout 180 --pull never --no-build` | 01:55:00–01:56:14 | **exit 0**，74.297 秒 |
| 冷启后 HTTP/API/PG、cache 及七容器 snapshot | 01:56:14–01:56:17 | 七服务 running/healthy、API ready200、旧前端200、缓存0700且实际可写 |
| 定向 Ruff / format / 源码 diff-check | 01:55:34–01:55:34 | 全部 exit 0；各命令完整 receipt 在 run 中 |

实际同容器重启特意复验原缺陷触发路径，避免只用删容器重建背书：frontend ID 前后均 `684eb541e6f08689958360523673bcdbaddce27460b8ce169c9a8bc6759dedb8`，见 `same_container_identity.json`、`same_stop/start.*`、`same_cache*.stdout.log`。两目录在 Node uid/gid1000 下实际 stat 为 uid1000/gid1000/mode700，并创建 `wx` 唯一随机测试文件、核对内容、删除该自身探针；没有碰用户文件。read-only 根、cap_drop ALL、host network 与 PortBindings 空值保留。

保卷冷启也独立确认：四命名卷名未变，PG 原 `t03_volume_probe` 行仍为 `survives-down-up`；数据库/用户仍是 `test_dianzi_r01_infra_20261015` / `test_dianzi_r01_infra`，迁移仍为 `0005_runtime_observations`。本轮 PG scheduler/worker observed_at 分别为 `2026-10-14T17:56:10.469550+00:00` / `17:56:10.473165+00:00`，均晚于 01:55:00+08:00 cold-up 开始；读取时年龄约 5.16 秒。这证明最近执行来自本轮，不是旧记录冒充新启动。见 `cold_volume_names.json`、`cold_volumes_retained.*`、`cold_live.stdout.log`、`cold_cache.stdout.log`、`cold_containers.json`。

19 合同包含旧 16 和新增 3，不改原门槛、分母或 case。没有重复无变化来源/模型/业务 scope，也不把先前 260/64 的数量当本轮新数量。读写探针的 assertion 数只描述检查器，不是正式评测样本数。

新版 CBM v0.11.0 使用独立仓库外 cache `/tmp/dianzi-cbm-r01-cache-recheck-20261015`，只在 fix WT backend/src 做 fast 索引，539 nodes/2037 edges、exit0，不索引秘密/holdout/run、不落图回源码。实际改动的 YAML/include/overlay/测试调用由 rg 和真实 Compose 渲染交叉核对；三个入口均继承共用缓存约束，不依赖图推断动态装配。证据在 `05_cbm_independent_cache.log`。

## 工具失败与覆盖限制

本次记录器有两次自身错误，均不删除或冒充业务失败：首次 snapshot 为所有服务索引可选 `HostConfig.Tmpfs`，无该挂载的服务省略字段，报 KeyError；修记录器读取方式后检查通过。随后同容器 start 的 HTTP 和实际 cache 已通过，但记录器立刻要求 Docker health 全部 healthy，未给健康探针收敛时间而报 AssertionError；补有界 30 秒健康收敛核对，不重跑/改写原 stop/start 日志，并独立核对相同容器 ID。两次 tool-output 摘要保留在 `harness_initial_error.json`、`harness_health_error.json`，并明确不是重构 raw log；失败子步的精确时刻未落 receipt，标 null，不编造它。真实后续命令时刻和 exit 完整保留。

一次读错 `R01-infra-fix.md` 路径后已核对作者实际把修复附在 `R01-infra.md`，原读取错误保留于02编号日志。这不是交付报告缺失。新文件源码 diff-check 通过；原初审和作者 raw 日志的尾部空白没有重写，未自行改 .gitattributes。

本限定范围未发现新的 Must/Should fix。新 UI 浏览器/e2e、GitHub CI、安全 base 搜索实跑、45 秒 PG 自动边界回归、R02/R03 完整业务/持久化、产品模型/来源 live、性能/持续运行和人工最终验收均 **not_run**。74.297 秒只是一轮实际冷启耗时，不是容量/吞吐或持续稳定性结论。E1/R2 只获得缓存可重启切片证据，不能签整评分项或 T02/T03/T06/T40。

## R02 有限后端实施的前置边界

按主控本轮要求另核对批准的 manifest，`R02.requires_slices` 为 `R01:T02`、`R01:T03`、`R01:T06`、`R00:T04`；dependency_reason 明确是实际 PG 与类型合同，不要求模型抽取或关系推理先完成。CR-R07 和00地图以可核验能力切片决定执行前置；同阶段的安全独立步骤可由 review 记录理由，不能把它解释成整包/整卡 accepted。

**允许在 G-A 内、专用新库/新 WT 独立实施主控限定的 PG session、跨进程 limiter/audit 和事实事务子步骤。** 原初审已经独立跑过真实 PG 迁移/约束/不可变原文/事务/权限回归、隔离质量入口，并在真实 PG 目录上完成默认认证 HTTP 登录/me/退出；本轮再次确认 PG0005、持久数据及真实依赖。`R01:T06` 描述正是默认真实认证路由、PG用户目录/配置、请求边界/not-ready，明确不代表会话/审计已跨进程持久化；内存 session/audit 是 R02 待替换对象，不应产生循环前置。R00:T04 的 schema合同已经由非作者审查 accepted。

TLS 缺口、旧前端/Vitest 和 cache 路径不参与上述 PG 子步骤的 IO；使用专用新库也避免新迁移误影响运行中的旧应用。主控仍须登记各前置能力所用冻结版本/报告，并协调公共迁移/合同唯一写入者。limiter 必须保留冻结语义、覆盖正常成功、失败、跨进程窗口与竞争，不能把旧成功登录占失败窗口的 bug 迁到 PG；本报告未独立认证主控后续 `b504` 候选。

这**不表示所有 R01:T03 验收、R02 全包或其所有 requires_slices 已签通过**。R01 整体仍 needs_changes，G-A 仍未过门；R02 完成仍需真实事务回滚、重启/跨进程、租户不可见、A→B→A历史、supersede当前/历史和并发幂等/outbox等原条件，MinIO 等未接入的最终条件不能删除。依赖完整 R02 的业务链、跨阶段、模型/来源/正式 live 和整卡/整阶段验收不得据本次限定意见越门。对这个有明确边界的 PG 子步骤，本审没有发现实际必需能力缺失的额外阻断；对整包验收，原未通过项继续阻断。

## 操作权与结论

本审最后容器检查结束 **2026-10-15T01:56:17+08:00**，七服务健康保留运行，无后台复跑。已明确消息交回 root 唯一项目操作权；之后只读合同/Git并写报告，不与主控并发操作项目。父 deadline 保持2026-10-17T21:49:15+08:00。冻结源码/状态、原失败日志未改；无 accepted/push。

Looks good. **Verdict: Ship. 仅32d16a4缓存修复。** 原 Must fix 1 在这个版本和实际限定环境上可关闭；原初审其它 finding、整 R01/G-A 与上面 not_run 均保留。下一步由主控据证据登记这一个意见，并继续 TLS/PG边界批次与 R02 有界实现。

Not checked: 新 UI/e2e、GitHub CI、安全搜索 TLS、PG45秒自动边界、R02/R03整包、模型/来源 live、正式性能/持续运行和人工最终验收。
