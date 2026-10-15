# G-A / R02 · MinIO 与初审 Must 修复独立复核 1

What this change does: 固定候选增加本地/MinIO 共用的内容存储接口、可信配置工厂与官方 SDK 远端适配。原文按 SHA256 寻址，写后重读验证完成才允许登记 PostgreSQL 修订；此前事件硬标识、事实关系和测试失败隐私的四个 Must 修复已包含在候选中。

**限定结论：本次 MinIO 对象适配切片与四个既有 Must 的定向复核通过，没有新增已证实的 Must/Should/Nice finding。** 本报告允许主控据此登记这两个有限范围的审查意见，不签整 R02、G-A 或整张原 T 卡。维度状态 writer、知识 API/worker 产品接线及其它原验收仍有缺口；没有写全局 accepted、提交或 push。

## 冻结与只读边界

- reviewer：`/root/r02_minio_integrated_review`，没有参与本批实现，也不是初审作者。
- 候选 SHA：`60fe4c311f98a0692e2207b884d83b676f5fb9c2`；tree：`c3aee5a2121a11a2293d4282049cfb26d8235229`。
- 要求基线：`8015ac091f9217a1940f51919778ba59d7b1567b`。新增 MinIO 代码单独审 `9a696b770c574761ce7bfd827902f998f069dc2b → 60fe4c3`，10 文件、753 insertions/5 deletions；四个旧 Must 定向核对 `33423b4`、`8015ac0`、`9a696b7`。基线至候选的其它 UI/搜索 TLS 改动没有被本报告整体背书。
- 独立 WT：`C:/Users/yinha/.codex/worktrees/recovery-r02-minio-review/dianzi`；分支：`codex/recovery-r02-minio-review`。新建后 `git status --porcelain` 为空；最后冻结资源核对也为空。没有业务源码或候选测试改动；所有审查输入和日志写到主仓本报告及专属 run。
- 已读 AGENTS、00/03/05/06、恢复卡 R02、T05/T06/T19/T21、CR-R02、CR-R04-R02 实施合同、CR-R05、状态/交接，以及主仓作者 `reports/tasks/R02-minio.md` 和独立初审 `G-A-R02-persistence-review-1.md`。作者报告只用于定位主张和范围；结论依据本次实际运行。读取版本 hash 见 [冻结与资源收据](../../runs/recovery_r02_minio_review_1_20261015/freeze_and_resources_recheck.json)。
- 使用新版 [Ponytail-review](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)，按正确性、安全、并发、测试、性能与复杂度核查。没有以缩短代码替代正确性要求。
- 真实资源仅授权的 `r02_knowledge_20261015` 专用 PG 和 loopback `127.0.0.1:29400` MinIO；本审单独创建 `test-dianzi-r02-review1-20261015` bucket，文档/源/用户等用随机测试 ID。PG 实际 head 为 **`0009_enrichment_results`**，没有接入主控新维度代码/head0010，没有 downgrade/drop/清库，也没有停止其它服务。
- 两份指定 root 0600 私有连接只由子进程捕获到内存并注入子进程环境；没有读取 `.env`、附件 KEYS、DPAPI、其它用户资料或 holdout。报告中没有值、argv 凭据或前端秘密。原生故意失败的 JUnit 完全留内存，检查后才保存安全副本；其它日志/XML在写报告目录前替换真实连接和秘密值/连续八字符片段。

## 实际命令与结果

下列均 cwd 为固定 WT 的 `backend`，通过专属隔离 `UV_PROJECT_ENVIRONMENT=C:/Users/yinha/.codex/tmp/r02-minio-review1-venv` 使用固定锁。完整 argv、秒级 +08 起止、退出码、SHA/tree 和 JUnit 计数在同名 `.command.json`，stdout/stderr/XML均独立保存。数量有重叠，不相加冒充独立测试总数。

| 验证 | 实际命令/范围 | +08:00 起止 | exit；真实数量 | 原始证据 |
|---|---|---|---|---|
| 依赖 | `uv sync --locked` | 11:28:47–11:28:51 | 0；非测试 | [locked_sync.command.json](../../runs/recovery_r02_minio_review_1_20261015/locked_sync.command.json) |
| 混合相关回归 | `uv run --locked pytest tests/unit tests/integration/test_r02_minio_persistence.py tests/integration/test_r02_knowledge_revisions.py tests/integration/test_r02_relation_identity_regressions.py tests/integration/test_r02_auth_state.py tests/integration/test_r02_default_application.py tests/security/test_r02_auth_state_boundaries.py tests/security/test_r02_default_auth_failure.py tests/security/test_r01_dynamic_failure_privacy.py --junitxml=<temporary> -q` | 11:29:11–11:30:33 | **0；195 passed / 0 failed/error/skip**，coverage81.08%，2 warnings | [command](../../runs/recovery_r02_minio_review_1_20261015/independent_integration.command.json)、[XML](../../runs/recovery_r02_minio_review_1_20261015/independent_integration.xml)、[log](../../runs/recovery_r02_minio_review_1_20261015/independent_integration.stdout.log) |
| 原认证故意失败 | 独立子进程 `python -m pytest -p memory_probe tests/integration/test_r02_auth_state.py::test_session_hash_only_is_stored --showlocals --no-cov -o addopts= --junitxml=privacy.xml -q` | 11:31:46–11:31:50（外层；内层收据另存） | **内层1；1 tests/1 failure/0 error/skip**；外层0，因为泄漏布尔均false且计数正确 | [observed](../../runs/recovery_r02_minio_review_1_20261015/native_auth_failure.observed.json)、[安全XML](../../runs/recovery_r02_minio_review_1_20261015/native_auth_failure.xml)、[安全stdout](../../runs/recovery_r02_minio_review_1_20261015/native_auth_failure.stdout.log) |
| 附加边界首轮 | `uv run --locked pytest tests/unit D:/dianzi/reports/runs/recovery_r02_minio_review_1_20261015/test_independent_minio_edges.py --junitxml=<temporary> -q` | 11:33:34–11:33:49 | **1；141 passed/1 failed/0 error/skip**，审查脚本错误，见下文 | [首轮XML](../../runs/recovery_r02_minio_review_1_20261015/independent_edges.xml) |
| 附加边界修正后 | 同上，包含新增真实 TLS 正/负例；候选业务未改 | 11:35:34–11:35:50 | **0；143 passed/0 failed/error/skip**（135 unit+8审查边界），coverage64.60%，1 warning | [command](../../runs/recovery_r02_minio_review_1_20261015/independent_edges_retry.command.json)、[XML](../../runs/recovery_r02_minio_review_1_20261015/independent_edges_retry.xml) |
| 风格 | `uv run --locked ruff check` 本批5个基础设施/修订源、conftest和3个MinIO测试文件 | 11:34:12–11:34:13 | 0；All checks passed | [command](../../runs/recovery_r02_minio_review_1_20261015/static_minio.command.json) |
| 格式 | `uv run --locked ruff format --check` 同9文件 | 11:35:33–11:35:33 | 0；9 files already formatted | [command](../../runs/recovery_r02_minio_review_1_20261015/format_minio.command.json) |
| 类型 | `uv run --locked mypy src` | 11:34:12–11:34:13 | 0；57 source files无错误 | [command](../../runs/recovery_r02_minio_review_1_20261015/types.command.json) |
| 资源/冻结 | 自有只读 `snapshot.py`：Git、PG head、MinIO二进制hash/version、health、cgroup | 11:38:17–11:38:19 | 0；非测试 | [receipt](../../runs/recovery_r02_minio_review_1_20261015/freeze_and_resources_recheck.command.json) |

混合运行 warnings 为锁中 Starlette/httpx 弃用提示与原 auth 并发进程测试的 `record_property`/xunit2 提示；没有改依赖、吞掉 warning、降覆盖门或转 skip。故意失败关闭 coverage 仅避免探针污染业务覆盖统计，不修改业务默认60%门；普通混合与附加回归均实际达到原门。

审查 harness 的三个实际问题保留：基础 Python 缺 tzdata，初次记录器在启动 uv 前 exit1、业务测试未执行，随后改为标准库固定 UTC+08；附加测试误断言 urllib3 的禁重试对象必须是字面 `False`，实际为 `Retry(total=False, redirect=0)`，只修正审查断言；首轮 snapshot 错写不存在的 `0009_event_operation_versions` 作为期望，实际源迁移链与库均为 `0009_enrichment_results`，只修正记录器。对应首轮日志/收据均保留，未把它们记为产品失败或删除难例。

## 路径追踪与 MinIO 核对

先调用官方 portable CBM `--help` 与 `cli index_repository --help`，然后为固定 WT **仅 backend/src** 建独立索引：`CBM_CACHE_DIR=/tmp/dianzi-cbm-r02-minio-review1-20261015`，`CBM_ALLOWED_ROOT=<WT>/backend/src`，`index_repository --name r02-minio-review1 --mode full --persistence false`。11:28:47–11:28:54 exit0，675nodes/2818edges，not_indexed/skipped/parse_partial/parse_unusable均0；没有索引秘密、holdout或reports。使用 `trace_path --direction both --depth 3 --include-evidence true` 分别追踪工厂、save_document_revision和默认app，见 [index](../../runs/recovery_r02_minio_review_1_20261015/cbm_index.command.json)、[storage](../../runs/recovery_r02_minio_review_1_20261015/cbm_storage.stdout.log)、[revision](../../runs/recovery_r02_minio_review_1_20261015/cbm_revision.stdout.log)、[defaultapp](../../runs/recovery_r02_minio_review_1_20261015/cbm_defaultapp.stdout.log)。所有源码 caller 同时用 `rg` 核对，不只相信图边。

- `content_store.py:L19–42` 保留本地 StoredObject 内部 Path，新增不带路径的 StoredContent 和三个 IO 操作的 ContentStorage；`revisions.py:L82–150/L306–323` 仍使用原 PG 父行/hash锁与事务。没有另建事实库。local工厂回归真实读回本地字节，原本地接口没有伪造远端Path。
- `minio_store.py:L65–118` 对键只接受64位小写hash；输入与远端读取均限大小；现存损坏对象拒绝覆盖；新对象写后重读校验hash，再返回登记值。7个真实候选测试实跑：独立进程新客户端读取、A→B→A三修订/新PG连接、rollback不发布、现存对象损坏、拒绝凭据区别于missing、外部断线不提交、两发布者同末版只一修订。
- 本审额外真实对象输入：空原文可往返；远端21字节对象交给20字节适配器明确拒绝；真实写成功后注入远端损坏，save拒绝且PG没有修订/content_object；rollback残留原文可读且可回收，已引用对象拒删；坏身份store明确unavailable且root检查同hash对象仍NoSuchKey。注入操作显式、仅本bucket，不冒称自然服务故障或模型/来源live。
- `minio_store.py:L40–60` 超时/大小范围校验、连接/读超时、CERT_REQUIRED与禁重试均核对。停滞loopback socket在0.2秒读超时配置下明确失败；实际合成HTTPS服务使用自签证书，默认不信任拒绝，显式CA后同payload读回且hash正确。此TLS实验验证SDK适配边界，**不是当前明文MinIO服务的生产TLS部署验收**。连接/读超时不是已验证的整次请求墙钟deadline；slow-drip、生产吞吐与全局并发容量未测。
- `settings.py:L60–95` 与 `content_storage_factory.py:L10–30` 明确MinIO缺endpoint/bucket/凭据即配置失败，非test明文被拒绝；选择minio返回MinioContentStore，不在网络/配置失败时换成本地。工厂初始化无网络，其真实调用在本次PG修订测试路径中得到验证。
- CBM工厂和修订函数在src inbound为0；`rg` 与默认app/worker源码确认没有产品业务调用。默认factory真实PG会话重建/撤销回归通过，只证明认证已接线，不证明MinIO/知识已在API/worker使用。

## 四个初审 Must 的定向裁定

| 初审项 | 实際触发、预期与观测 | 固定源码位置与复验 | 本次判断 |
|---|---|---|---|
| Must1 同事件第二CVE | 先保存CVE-A，再同event_id/new key提交CVE-B。候选拒绝EventLinkingError，原映射仍只有A；同文双事件及已有merge/undo回归也通过。 | `event_linking.py:L227–241` 先合并已存/新CVE集合再检查；`test_existing_event_rejects_second_cve_without_changing_original` | 原缺陷已修复；不再复现 |
| Must2 不同作用范围误supersede | 同source/document的后版分别改变branch、ecosystem、scoring authority。三参数例均KnowledgePublicationError；原supported/current可读，错误替代没有发生；正常同范围supersede及历史回归通过。 | `persistence.py:L712–744` 关系转换前统一校验事实、authority、typed range branch/ecosystem；`test_supersede_keeps_independent_assertions[branch/authority/ecosystem]` | 原缺陷已修复；不再复现 |
| Must3 模型假设dispute变事实 | model_hypothesis/unverified/true与source fact/supported/false提交disputed。候选拒绝，当前事实查询没有该模型记录；正常两supported事实冲突回归通过。 | `persistence.py:L712–718` 拒绝model/未核验/非法状态；`test_dispute_cannot_promote_model_hypothesis` | 原缺陷已修复；不再复现 |
| Must4 原认证失败泄漏 | 保留原认证测试、真实随机PG登录、`--showlocals`。仅扰动返回SessionRecord.session_id触发原最终assert，并向stderr输出真实token/hash片段。内层仍exit1/1failure，原生stdout/stderr/JUnit对真实token/session_hash/CSRF/password的完整值与全部连续8字符匹配均false；无raw privacy.xml。 | 原测试`test_r02_auth_state.py:L382–394` semantic local为session_hash；`conftest.py:L38–150` bounded collector、报告脱敏与显式注册。动态session/sql/registered及不访问属性/repr回归同时通过。独立脚本 [native_auth_failure.py](../../runs/recovery_r02_minio_review_1_20261015/native_auth_failure.py) | 原缺陷已修复；不再复现 |

上述都是confirmed修复/实际观测，不把未运行项改成通过。初审旧报告和旧失败仍保留。故意失败XML中的失败本身属于验证输入，不是需要主控再修复的业务回归。

## 剩余范围、风险与评分证据

**明确剩余能力，不是本次新 MinIO 回归：**

- `0009_enrichment_results` 与 `enrichment/persistence_models.py` 有维度表，`enrichment/structured.py:L29–39` 仍是显式fixture台账；固定候选没有写入该表的PG业务writer。R02:T19仍不能据“有表”视为持久化维度完成，须在后续独立候选验writer、幂等/部分失败、权限、当前/历史与epoch/outbox同事务。
- API/worker没有调用存储工厂/save_document_revision/知识发布路径。需要后续真实接线及重投递闭环，不能以测试调用冒充产品在线能力。
- 本审没有执行空库/旧库升级、MinIO服务重启、备份恢复、本地既存对象迁移、最小权限IAM、产品MinIO TLS或受控上线。没有用作者restart/172报告代替本审证据；当前库仅运行安全的前向迁移检查并独立读回head0009。
- 真实MinIO是授权root身份、明文loopback测试资源。独立核对二进制hash `10ec54df2dc51dfa1399b7187d9377a20bd1b50f22d123a756175173b0cfff75`，自报 `DEVELOPMENT.GOGET`、go1.27.2；cgroup为768MiB、swap0、0.5CPU、256PID，health200。作者固定官方源码模块记录不是官方发行二进制的证明。官方 [minio/minio](https://github.com/minio/minio) 页面于本审读取时显示2026-04-25归档、停止维护且社区版仅源码分发；生产依赖维护与镜像/版本选择仍需专门决策，本审不擅自换栈或声称production可用。

评分项只登记有限证据：F1/F2 的不可变原文、重复末版与A→B→A；E1 的真实对象/PG失败边界、事务、并发和配置；T06/E1 的相关会话/权限回归与失败隐私。没有据本批推断来源覆盖、九维完成、真实多跳问答、性能数字、连续运行、正式金标或整系统优秀档。

验证分层：unit=passed；相关integration=passed；定向security=passed；本批独立contract命令=not_run（配置边界在unit，旧合同行为在集成）；frontend/e2e/model或source live/manual=not_run。隔离MinIO/PG是真实依赖实验，不等同provider live。

Verdict: **Ship，限定为60fe4c3的MinIO对象适配切片与本表四个Must修复。** 整R02/G-A仍待其全部能力、原验收、独立阶段检查；主控唯一负责全局状态/Git/push。下一任务建议完成独立新候选的维度writer验证和知识API/worker接线，本审不追main后续代码。

Not checked: 新维度候选/head0010、整R01搜索TLS/UI、知识API/worker真实链、空/旧库迁移、备份恢复、产品TLS/IAM/部署、slow-drip总时限、性能容量、模型/来源live、正式盲测、持续运行与人工最终验收。

本报告写作开始：2026-10-15T11:39:04+08:00；写作结束：2026-10-15T11:42:51+08:00；最后clean/秘密扫描见专属最终收据（实际后续记录，不回填测试起点）。
