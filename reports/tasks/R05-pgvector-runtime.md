# R05-pgvector-runtime · 专用 pgvector 运行准备与实证

记录时间：2026-10-15T15:55:00+08:00（Asia/Shanghai）。准备包状态：awaiting_review；实现：complete（仅资源准备）；integration：passed；live/model：not_run；manual：not_run。R05 整包与 T18/T30 整卡状态由主控维护，本包不改 progress，不自行 accepted。

基线 SHA：`fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4`；分支：`codex/r05-pgvector-runtime`；独立 worktree：`C:/Users/yinha/.codex/worktrees/r05-pgvector-runtime/dianzi`。最终冻结 SHA 由交接中的实际 `git rev-parse HEAD` 给出，不在报告中伪造尚未产生的提交值。

## 目标与边界

为主控后续真实 embedding 写入及检索提供可复跑资源。读过 AGENTS、执行图、R05/T18/T30、CR-R02、架构/API/资源/检索/测试合同和基线 task_state；按用户授权及 Ponytail 5.2 full 选择已有资源最小路径。实际源码定位为 `backend/src/ai_intel/infrastructure/database.py` 和 `backend/src/ai_intel/infrastructure/settings.py`，同步 SQLAlchemy/psycopg 与 SecretStr 已存在。CBM 0.11.0 真实 help 已运行；此次仅资源和报告，不索引秘密、用户附件或 holdout，也未建立产品源码补丁。

仅新增本报告和 `reports/runs/recovery_r05_pgvector_runtime_20261015/` 内脚本、JSON、脱敏日志。未改共享 schema/迁移、settings、锁文件、infra、backend、progress；未触碰主线未提交文件、其他 review 数据库、产品数据和历史；未 push。

输入为 WSL root600 授权连接文件，读取到子进程环境，先校验 `127.0.0.1:25432/test_dianzi_r01_20261014`；输出为专用库 `test_dianzi_r05_pgvector_20261015`、合成 SQL 实测和仓外专用连接引用。合成三维/384 维输入只证明 SQL 行为，不是模型 embedding、语义召回或性能结果。

## 实际资源

只读 `SELECT version()`、`pg_available_extensions`、`pg_extension` 确认共享服务已具备 vector 文件并在原测试库启用。未对原库执行 CREATE/ALTER/DROP/迁移或重新初始化。

| 项目 | 实际值 |
|---|---|
| PostgreSQL | 16.14，Debian 16.14-1.pgdg12+1，x86_64 |
| pgvector | available/default/原库 installed 均 0.8.2；专用库 CREATE EXTENSION 后 0.8.2 |
| 缓存官方镜像 | `pgvector/pgvector:0.8.2-pg16` |
| RepoDigest / Image ID | `sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc` |
| image inspect Size | 156136386 bytes；CLI 展示 621MB 为不同显示口径，不据此编造下载量 |
| 现有 PG 容器 | `dianzi-test-r01_20261014-postgres`，host 网络，仅校验授权 25432 连接 |
| PG 上限 | 1 GiB memory，0.75 CPU，128 pids，restart=no |
| 父 cgroup | `/sys/fs/cgroup/dianzi-r01-20261014`，8 GiB memory，2 GiB swap，2 CPU，2048 pids |
| 15:52:13 观测 | memory.current=5141540864 bytes；pids.current=509；不是正式容量/性能指标 |
| 当前父资源段 | lifecycle 实读 started_at=2026-10-15T09:59:13+08:00；deadline=2026-10-17T21:49:15+08:00 |

无需新容器、镜像 pull、包安装或额外 watchdog；没有更改共享容器文件/服务配置，也没有 apt/dpkg/make、DNS、ACL、TLS 或系统库改动。专用库于 2026-10-15T15:50:07+08:00 创建，持续性依赖已存在的父资源段和 supervisor。主控接管必须在截止前决定关闭消费者及释放/续期资源；本包不会自行重启、停止共享 PG 或删除测试库。仅测试资源，不创建第二套产品业务真相。

## SQL 验证

`verify_isolated.py` 可重复执行：仅检查本包库存在与否，创建专用表，固定主键的合成行幂等插入；既有值不覆盖，断言失败不会伪成功。所有 SQL 执行在专用库；CREATE DATABASE 是唯一对共享 server 的增量对象操作。错误只记录 SQLSTATE，不记录原始 SQL 参数/DSN。

| case | 可观察结果 |
|---|---|
| PV-C01 | 专用库创建/可连接 |
| PV-C02 | CREATE EXTENSION vector，extversion=0.8.2 |
| PV-C03 | `[1,0,0]` 查询余弦距离，ID 顺序 `[1,2,3]`，距离 `[0,0.29289321881345254,2]` |
| PV-C04 | 真实 EXPLAIN ANALYZE/BUFFERS JSON，Actual Rows=3，Seq Scan+Sort+Limit；无 ANN 索引或正式性能声明 |
| PV-C05 | 错误维度 `[1,0]` 被 22000 拒绝，id=90 保持零行 |
| PV-C06 | NaN 被 22000 拒绝，id=90 保持零行 |
| PV-C07 | Infinity 被 22000 拒绝，id=90 保持零行 |
| PV-C08 | 写入 id=99 后 rollback，查询零行 |
| PV-C09 | vector(384) 可写入，vector_dims=384，自身余弦距离=0 |
| PV-C10 | 提交后断开并新建连接，三个原值逐项保持 |
| PV-C11 | not_run：共享 PG 不允许重启，重连不能计为重启耐久性 |

实际 10 passed、0 failed、1 not_run，无 pytest skip。JSON 保留完整 EXPLAIN；输入都是本包静态合成数据，不读取原文、用户资产或盲测。真实模型/API/ACL/端到端问答、迁移升级及重启耐久性没有运行。原 T18/T30 的维度/模型空间、授权过滤、撤回、水位及语义召回仍须完整执行。

## 命令和日志

所有复跑 cwd 为上述 worktree；Python 使用已存在 `D:/dianzi/backend/.venv/Scripts/python.exe`，没有改装该环境。

| 实际命令 | 时间 / 退出码 / 计数 | 证据 |
|---|---|---|
| `python .../probe_existing.py` | 15:48:03 首次只读、15:50:06 复跑；exit 0；3 类查询 | `existing_database_probe.json/.log`；最终复跑覆盖为最新时刻 |
| `python .../verify_isolated.py` | 15:50:07 首次；exit 0；10/0/1 | `isolated_sql_verification.json/.log`；最终复跑另有完整 receipt |
| `python .../inspect_resource.py` | 15:51:07→15:51:09 首次；15:52:11→15:52:14 修正；exit 0 | `resource_inventory_attempt1.json`、`resource_inventory.json` |
| `python .../final_check.py` | 每个命令实际 start/end/exit 按秒存档；资源、只读、SQL、Ruff、format、git diff 6 个命令 | `command_receipts.json`、`*_final.log`、`final_check.json` |

首轮资源 inventory 的 Bash `$file` 经 WSL quoting 后为空，cat 报目录错误而后续 stat 使外层 exit=0；原记录保留在 attempt1。该次 cgroup 行无效，不算资源验证或业务失败。已改用 WSL Python 明确路径读取，并检查 stderr。最初源码搜索误用仓库根 src/settings 路径，明确报不存在后用 rg 核对真实 backend 路径；不据错误搜索推断缺失实现。首次 Ruff 修复3项后尚余23项，format 后余13项，已改正字符串长度与列表展开；最终检查结果以 receipts 为准。

最终检查编译四个脚本的语法，不写 pycache；以实际两份秘密文件扫描所有本包报告/脚本/日志的完整 DSN、密码所有连续8字符片段，发现数须为0。未运行无关产品回归，因为本包没有产品代码改动。初期交互式只读定位的逐命令 start/end 未完全落文件，不能虚构；验收入口已完整重跑并生成逐命令 receipt。

## 主控接管与后续

仓外引用：`/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json`，实测 `600 root`。它只含派生专用库的 TEST_DATABASE_URL，身份沿用授权测试身份；不输出值、不复制入报告、不作为模型凭据。主控应从 WSL root 子进程 capture_output 读取，JSON 解析后只传到测试子进程 env；不得命令替换/echo、envdump、日志或将 DSN放 argv。可参考本包 `launch_verification` 中对原授权文件的同模式读取，并将读取路径换为专用引用。若连接文件已存在，复跑只核验 root600 及同值，不覆盖冲突秘密。

后续由 root 控制新增迁移0014、embedding空间/版本、EvidenceSpan/tenant约束及产品设置；此库不能承载另一套业务事实，不将旧全库 dump 入仓。当前 PG 本身已装 vector，无需升级镜像或改变旧扩展；产品迁移应先检查扩展存在并保持原事实/历史/任务/认证，增量迁移和回滚边界另测。

Python 成熟组件候选：实取 [PyPI官方元数据](https://pypi.org/pypi/pgvector/json) 当前 `pgvector==0.5.1`（Python>=3.10，2026-10-09上传），wheel 31056 bytes，SHA256 `ec5bcd5ffaefe6ecb2dcc9564ca921d284564b969183bc837a144604773af8ea`。依据 [pgvector-python官方集成](https://github.com/pgvector/pgvector-python#sqlalchemy) 采用 `pgvector.sqlalchemy.VECTOR` 及 `pgvector.psycopg.register_vector`；不自制 UserDefinedType。本包未安装该包，SQLAlchemy2.1.1/psycopg3.3.6 环境下官方 Python 适配兼容实测由 root 锁定后执行。扩展语法依据 [官方 pgvector](https://github.com/pgvector/pgvector)，现有0.8.2版本依据实际 SQL/镜像，不把网页新版本当运行版本。

没有本包外部 live 阻塞；资源已可供主控继续，但模型兼容与产品链路仍未验。F3/A1/F2仅登记真实运行资源前置证据，不能认定语义效果或评分达标。建议下一步：root 使用专用连接进行迁移及真实 embedding 写入/检索回归，并安排独立 review。风险：此库依赖共享资源截止；本包不重启共享 PG、不证明重启耐久性，也未执行产品或模型测试。
