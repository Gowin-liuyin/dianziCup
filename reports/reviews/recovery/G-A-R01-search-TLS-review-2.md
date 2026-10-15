# G-A / R01-search-TLS · 独立审查 2

What this change does: 本修复将独立 TLS 搜索资源接入 CI 的准备/清理步骤，并保护 TLS、会话和 SQL 参数的 pytest 失败输出。本审使用真实 HTTPS 服务和原生 pytest 失败，核对它们的可观察结果。

**固定 f2 结论：needs_changes。** 原审查 1 Must1 的 TLS 密码泄漏已在本次限定复验中关闭；Must2 的资源准备已经实际可用，但 CI 仍缺故障测试必需的 Docker 命令环境变量，不能关闭。此结论仅针对 `f2c5873fa8c2695ae81d673e7107ada3e9b52a81`，不接受整 R01/T03/G-A，不将后续源码的成功倒写为本版通过。

## 冻结版本与审查边界

独立审查者未参与 TLS/共享 hook 实现。新工作树 `C:/Users/yinha/.codex/worktrees/recovery-r01-tls-recheck/dianzi`，分支 `codex/recovery-r01-tls-recheck`；输入 commit 为 f2，tree 为 `c8f89d09f3e44804247893ced89f7fa05aeb0f82`。初末 `git status --porcelain` 为空，冻结 backend/infra/scripts/.github/config diff 为空。审查只写本报告及 `reports/runs/recovery_r01_search_tls_review_2_20261015/`，未改业务、测试源码、conftest、锁、合同、状态、计分分母、阈值或金标；无提交/push。

已读 AGENTS、00、恢复 11/12 的 R01、T03、02/03/05/06/09 合同、相关 CR、状态/交接、原独立审查两项 Must、作者 `R01-search-TLS-fix.md`、源码/调用方/CI/Compose README，并使用 Ponytail 5.2.0 review 技能。作者证据 `e45e06ee`、`e6d8728e` 只作定位；其 0006/full integration 历史结果不计为本审当前 0011 的通过。六个 TLS/CI/hook 相关源码 blob 与 d8 作者版本相同，证据见 `tls_author_blob_match` 与 `source_manifest`。

官方 CBM 0.11.0 在 WSL `-u root` 使用独立 cache `/tmp/dianzi-cbm-r01-tls-review2-20261015`，只索引本工作树 `backend/src`，persistence=false。实际 812 nodes / 3538 edges，not-indexed/skipped/partial/unusable 均 0；architecture、`trace_path(create_application,outbound,3)` 均 exit0。动态健康闭包与 HTTPX/SSL 调用另用 rg 和源码核查，不将静态图称为实跑。

## Must fix

1. **CI 仍未提供故障恢复测试读取的命令前缀**（P1；`backend/tests/integration/test_r01_search_tls_live.py:146`、`scripts/prepare_search_tls_test.py:323`、`.github/workflows/ci.yml:89`）。
   - **这是什么：**prepare 能在未配置 JSON 命令变量时默认调用 docker，导出的十二个 TLS 值没有该变量。测试却直接使用 `os.environ["DIANZI_DOCKER_COMMAND_JSON"]`；dev.py 的默认值只作用于自己的 Compose 调用，不写入 pytest 环境。
   - **复现与结果：**健康 TLS fixture 的全部输入保持，仅删除该变量，运行真实 fault case，`--showlocals --no-cov --junitxml=review-native.xml`。2026-10-15T12:32:54–12:32:56+08:00，exit1，1 failure / 0 error / 0 skip，实际 `KeyError`；失败发生在 inspect/stop 前。原 stdout/内存 JUnit 的完整密码及任意连续八字符片段均未泄漏。证据 `ci_missing_docker_command_actual.json/.log/.xml`。
   - **最小修复与复验：**把 prepare 已校验的实际命令前缀与其余 TLS 值一起写入 connection 和 GitHub ENV；或测试复用同一安全默认规则。冻结后只靠 prepare 输出执行一次真实 fault/recovery/cleanup；不能靠审查 runner 额外注入变量来声称云配方完整。
   - **不修影响：**TLS 创建成功也无法完成当前 CI integration 的故障案例。本审没有执行 GitHub 云 CI，确定结论来自实际 native 缺变量输入与源码装配核对。

## 原 Must1 的限定关闭证据

实际健康服务上将正确 case 的密码替换为随机错误密码，保持 exit1 / 1failure；URL 改为非法端口 70000 保持 exit1 / 1error；缺密码保持 exit1 / 1error，均未改为 skip。另用真实 `AuthenticationSessionService.login` 创建 `SessionRecord`，保留随机 session token、session hash、CSRF 与密码局部值，再实际 assert False，exit1 / 1failure。四份 native 子进程的 stdout、stderr、JUnit 在外层替换前均通过完整值和所有连续八字符片段审计。

JUnit 使用仅拦截指定输出文件写入的内存 StringIO 插件，原生 pytest 仍生成报告和计数；未修改 outcome。原始 XML 从未落盘，审计后才保存安全副本。共享 conftest 的拷贝字节与冻结源一致；没有仅对字符串替身直接调用脱敏函数。对应 receipt 为 `forced_tls_assertion`、`forced_tls_fixture`、`forced_tls_missing`、`forced_real_session_record`。R01 现有失败隐私 security 两文件另实际 6pass / 0fail/error/skip。

## 实际检查与限制

以下均为 2026-10-15 +08:00；每个同名 JSON 保存完整非秘密 argv/cwd、秒级起止、exit 与实际 JUnit 计数。

| 检查 | 实际结果 |
|---|---|
| `uv sync --locked --project backend` | exit0，68 packages，Python 3.12.13 |
| Ruff / format / mypy 当前后端及两个 scripts | 均 exit0 |
| 纯 unit | 248pass / 0fail/error/skip；工具 exit0，但实际 coverage **59.98%**，日志显示原 60% 门未达 |
| 实际 `python scripts/dev.py check --scope unit --timeout-seconds 600` | 同为 248pass、tool_exit0、59.98%；不能登记为覆盖门通过 |
| 三个 TLS/Compose/迁移配置合同文件 | 26pass / 0fail/error/skip，exit0 |
| 全 security 首次探索 | 128pass、9error、0fail/skip，exit1；九项均缺 PG 隔离输入，属于资源 blocked，不冒充 TLS 业务失败或全 security 通过 |
| TLS 七例，12:29:34–12:30:59 | 7pass / 0fail/error/skip，exit0；正确 CA、无 CA、错误 CA、错误主机名、错误密码、实际 socket、停止/恢复自有容器 |
| 额外真实边界，12:32:57–12:33:08 | 6pass / 0fail/error/skip，exit0；缺 CA 文件、过期信任 CA、纯 HTTP、过期链实际 SSL verify_code10、健康账户只读权限、默认 app 入口 |
| OpenSSL 链 | 正确 CA/localhost exit0；过期信任 CA exit2/error10 |
| 当前迁移链 | 程序化 head=0011、11 revisions，fresh 离线升级 SQL 生成 exit0；未升级任何已有 PG 库，**真实空库升级 not_run** |

过期证书实验使用同一 CA 密钥生成已过期的信任根，节点叶证书仍有效；实际 OpenSearch TLS socket 以 verify_code10 拒绝该链，应用返回固定安全503。没有将这个实验冒充过期叶证书替换或全部部署测试。健康账户对 health=200、根信息/索引列表/安全用户接口=403。默认模块 app 的 search 分项 ready，PG/Redis 未配置，整体503；没有写成整体 ready。

f2 的 59.98% 与工具退出0差异已由主控另行定位 pytest-cov 默认 precision0 舍入，属于共享候选门问题；原60%阈值不变。本审保留实际警示，未将含其他合同测试的数量替代纯 unit。后续版本的 unit 成功不能回填 f2。

## 实际 prepare、资源与收尾

新 run `r01_tls_review2_20261015`，项目 `dianzi-test-r01_tls_review2_20261015`，29208/29308，仓外私有目录 `/tmp/dianzi-r01-tls-review2-20261015`。实际调用冻结 prepare 的 PKI、固定镜像 hash.sh、安全模板、securityadmin、严格 CA 健康等待、GitHub ENV 和 cleanup。导出的12变量与私有 connection 精确一致，真实 add-mask 已捕获并在写盘前脱敏。不是仅检查 workflow 字符串。

原 CI 默认 search 为2GiB。本审经主控授权，在自有 wrapper 的原 compose_command 后追加唯一资源 overlay，search768MiB、heap384MiB；使用 host overlay 是当前有界 daemon 的限制。实测内存805306368、0.5CPU、256PIDs、UID1000、healthy、OOM=false。不能将本机这套有界配方写成云 CI 原2GiB/bridge 实跑。

私有目录700；connection、GitHub ENV、CA/admin key600；节点 key/security 1000:1000，600/700。未读产品秘密、DPAPI、用户 .env、KEYS、holdout、原私钥正文；密码只在私有环境/内存与仓外root600。未 pull/build、未停止/重置其他服务、未删除卷。

12:33:17–12:33:19 cleanup exit0，exact project 容器为空，自有 named volume 保留。旧 TLS 仅只读终检仍 healthy；无后台复跑或持有容器操作权。独立 Linux runtime 后续若建立，将供主控复用，不删除仍需使用的缓存。

工具准备的不存在路径/错误文档名、首次使用不存在 alembic.ini（exit非零）、OpenSSL req 不接受负 days（exit1）均保留，不计业务失败/通过；改为程序化 Alembic 和 x509 生成后获得有效结果。一次自有 helper 在捕获子命令失败前输出了不含凭据的 Python 路径异常，后续 helper 统一安全捕获，不以该工具错误改变任何测试 outcome。

精确秘密扫描与原模式扫描的范围/哈希见 runs 中扫描 receipt 与 manifest。原生每例秘密审计是关键证据；最终单次扫描不能替代已经完成的动态随机值逐例内存审计。审查日志中仅脱敏占位符/fixture 源码形状的原模式命中另作安全存储规范化并保留前后哈希与未改 count 记录，不放宽模式或分类表。

Not checked: GitHub云CI、普通bridge冷启、完整安全七服务、真实PG空库0011升级、完整contract/integration、frontend/e2e、模型/FOFA/外部来源live、正式性能/稳定窗口与人工验收。E1/R2/T03只取得本报告列明的工程切片证据，不累计为阶段 pass。

**f2 Verdict: fix 1 first.** 主控已冻结 a7 最小修复，定向复核另记下方，不覆盖此历史结论。

## a7 最小前缀修复 · 独立定向复验

复验输入固定为 `a7c0a4aab37b3cf1916efb3cb480f5db148ead44`，tree `30f5ba257416a50097f9bbbe64838e7f72e0cfca`。新工作树 `C:/Users/yinha/.codex/worktrees/recovery-r01-tls-prefix-recheck/dianzi`，分支 `codex/recovery-r01-tls-prefix-recheck`；初始只读检查及正确目标终检 clean，实际源码 diff0。证据独立放在 runs 的 `a7_prefix_recheck/`，不合并成 f2 的成功次数。

本次唯一审查的 TLS 修复是在 prepare 第324行将经过校验的 `json.dumps(command)` 加入统一 values。TLS consumer、conftest、app/settings、CI 和两个 TLS Compose 文件与 f2 的 blob 均未变化，固定 A/B diff exit0。因此本次不重复七条 TLS 或隐私套件，f2 的已通过行为只作为未变化代码的既有证据；也不将 a7 的其他未审源码改动背书为通过。

WSL 未有 Python3.12/uv。经主控授权，只从已存在批准的 backend 镜像 `sha256:34b24db5595ed36fc608f39f648d5a9a2288cb03a2ca8f1ecd123044158ea7b0` 创建自有停止提取容器，复制其官方 uv 后立刻 rm 此停止容器；没有 pull/build、启动其应用或操作其他项目。uv0.10.9 安装 CPython3.12.13（标准32.3MiB下载，工具报告6.39秒），随后明确记录版本与两个 executable SHA256；12:41:23–12:41:32 锁定安装68包 exit0。此工具准备时间不计入 TLS 运行。

保留环境路径：`/tmp/dianzi-r01-tls-prefix-runtime-20261015/uv`、`/tmp/dianzi-r01-tls-prefix-runtime-20261015/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12`、`/tmp/dianzi-r01-tls-prefix-runtime-20261015/venv`。venv 的 editable 项目指向 a7 工作树；已交主控供其他 reviewer 显式设置其源码 PYTHONPATH 复用，仅共用 runtime，不共享本次 TLS 私有目录和容器。

新 run `r01_tls_prefix_review2_20261015`，私有目录 `/tmp/dianzi-r01-tls-prefix-review2-20261015`，端口29208/29308。仍只有一个768MiB/heap384MiB的自有搜索服务，host overlay，严格 CA 和原安全初始化流程。准备前清除 `DIANZI_DOCKER_COMMAND_JSON`，仅在自有仓外 PATH 中提供名为 docker 的适配器指向已授权 daemon；冻结 prepare 实际走默认 `["docker"]`。

实际 create exit0，导出值数量 **13**，其中 JSON 原值 `["docker"]`；GitHub ENV 与 connection 完全一致，真实 add-mask 捕获并在写盘前脱敏。随后的 Linux pytest 从该 connection 得到所有13值，**没有覆盖或补写 Docker JSON**；只增加测试运行需要的 Python/PATH 机器环境。原 `test_real_search_fault_returns_safe_503_and_recovers` 在12:43:04–12:44:10实际 exit0，1pass / 0failure/error/skip，实际核对标签、stop、自有搜索安全503、start、健康恢复。原 stdout、stderr、内存 JUnit 的完整密码及任意连续八字符片段均 false；raw XML未落盘。见 `fixture_create`、`fault_native` 和 `fixture_after_fault_status`。

12:44:11–12:44:13 cleanup exit0，exact project 容器为空，named volume保留；终检旧TLS仍healthy。prepare Ruff/format 均 exit0。新的官方CBM独立cache `/tmp/dianzi-cbm-r01-tls-prefix-review2-20261015` 只索引 a7 backend/src，813nodes / 3547edges，所有跳过/partial/unusable为0，architecture和trace实际exit0。

首个 outer helper 在切换全局 SOURCE 后，其默认 cwd 参数仍绑定旧 f2 路径，导致最后的工作副本 diff显示exit1；Linux native pytest 的 argv/cwd和被导入包从开始就明确是 a7。发现后只修自己的日志 helper，保留 `*_prior_default_cwd` 的原结果，并在正确 a7 目标重新 status/diff，实际exit0/clean。作者 d8→a7 的 script diff非零则是本次批准的一行前缀变更；不冒充空diff，也不是业务测试失败。所有 source/receipt manifest按真实目标记录。

**a7 定向结论：原审查1两项 Must在已测 TLS/CI装配/失败隐私切片内关闭。Verdict: Ship for this tested slice.** f2 的 needs_changes、59.98%和工具舍入问题保持原记录；未独立重跑 a7 的全unit，主控的268/61.42%结果不作为本报告的新通过。GitHub云CI、原2GiB/bridge配方及完整0011全integration仍not_run，不签整R01/T03/G-A或阶段accepted。

下一步由主控按此冻结 SHA/manifest登记两Must的限定关闭，保留其他 reviewer 的问题，再在阶段检查前运行真实完整 CI/集成与其要求的人工/live检查。runtime/cache和两个自有named volume保留，审查停止，无后台容器操作。
