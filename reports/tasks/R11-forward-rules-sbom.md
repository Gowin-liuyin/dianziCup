# R11 · 规则/评估与 SBOM sidecar 生产前向迁移

状态 `awaiting_review`；本生产迁移切片实现 `complete`。作者不签 `accepted`，不改 progress，不签整 R11/T24/T27/T28 或 G-D。0020 独立审查尚待主控确认，是最终前置门；独立准备与隔离验证已获明确授权。

报告实际开始写作：2026-10-16T07:22:50+08:00。最早持久化检查 receipt：2026-10-16T07:10:52+08:00；更早的只读任务核对未保存磁盘 command receipt，不补造起止。执行结束时间以材料封存 receipt 为准。

冻结起点 `ed0e14a03a06ed104f23afd0be5407d873ed8edf`；仅获取已限定 Ship 的 PG 源码 `2ddc8fe2ff3e7becfad3b1774a10407911eacbe6` / 材料 `6b10f2c4ed013f4375d51fc31e1cb317409730ac`。在独立 `D:/wt/r11-forward-rules-sbom` / `codex/r11-forward-rules-sbom` 合入其冻结材料，merge `a9dd97102623640b587ef7e5aea67170cb193b6f`。唯一 merge 冲突是已有旧 run 的 `.gitattributes` add/add，精确保留 ed0 一侧，未改旧材料原字节。根工作树已有未提交内容未触碰。

新增代码冻结 `2fe903eaff4030b64b3f5789e8027e1e11e41694`。后续材料提交只包含本报告与 owned run；未 push、公开发布或操作用户运行库。

## 输入输出与文件范围

输入为冻结 metadata、资产主快照 authority 和现有 Alembic0020；输出为普通 forward head0022。新增：

- `backend/migrations/versions/0021_condition_assessments.py`、`0022_sbom_sidecars.py`。
- `backend/tests/r11_forward_fixtures.py`，`tests/contract/test_r11_forward_rules_sbom_migrations.py`；三个直属 integration 文件 `test_r11_forward_rules_sbom_schema.py`、`test_r11_forward_assessment_regression.py`、`test_r11_forward_hybrid_regression.py`。
- `docs/decisions/CR-R11_rules_sbom_forward_migrations.md`、本报告、`reports/runs/recovery_r11_forward_rules_sbom_20261016/`。

0021 精确复刻六表：condition_rule_versions、rule_support_bindings、rule_leaf_reviews、rule_validation_receipts、assessment_results、assessment_scope_watches。保留全部列/类型/nullable/PK/FK/UNIQUE/check，两个既有索引、两函数和六个 trigger。`uq_current_published_rule_family` 仍为一个 published family 的 partial unique，规则内容不可变且 lifecycle 单向。0022 精确复刻主控 SBOM seam 的唯一 sidecar 表：snapshot 主键，asset/tenant/snapshot 复合 FK，版本长度、两小写64位 hex hash、JSON object 和 UPDATE/DELETE 拒绝。

DDL 是静态 PostgreSQL SQL，通过 Alembic op执行；没有业务 metadata 导入、动态建表或产品 create_all。未变更现有 metadata、服务、auth/API/settings、依赖、锁、全局属性、旧迁移、gold/holdout、分母或阈值。获取的五个业务文件逐 blob 仍等于冻结6b；旧迁移和 root SBOM metadata 逐 blob 仍等于 ed0，核验见 source_manifest。没有新增 authority FK 或改变已批准业务语义。

七表承载不可变历史，downgrade 明确拒绝删除；关闭新增写入、保留读兼容，必要时批准前向修复。隔离 PG rollback 使用真实 DDL 与 Alembic stamp同事务注入失败，不执行 destructive downgrade。

## 真实验证与原红

执行器 `D:/dianzi/backend/.venv/Scripts/python.exe`；cwd为本 WT/backend。完整 argv、+08起止、退出码、墙钟、stdout/stderr与JUnit位于 owned run/commands.jsonl，以下只列重要最终检查，不累计早期重复轮次：

| 标签与实际检查 | 2026-10-16 +08:00 起止 | exit / 真实结果 |
|---|---|---|
| frozen_pg：`-m pytest tests/integration/test_r11_forward_assessment_regression.py tests/integration/test_r11_forward_hybrid_regression.py tests/integration/test_r11_forward_rules_sbom_schema.py --no-cov -q --junitxml=…/frozen_pg.xml` | 07:19:25—07:21:01 | 0；119 passed，0 fail/error/skip；93.11s pytest |
| frozen_pure：新增迁移合同 + 原 scope/contracts + T26/version branch/manifest/identity/T27/condition schema/security，完整十文件 argv在receipt | 07:19:25—07:19:29 | 0；371 passed，0 fail/error/skip；2.06s pytest |
| types_initial：`-m mypy src` | 07:15:03—07:15:28 | 0；135源文件；其后src未修改 |
| final_quality：`-m ruff check` 七个新增迁移/tests及 owned run | 07:22:29—07:22:29 | 0；passed |
| final_format_check：`-m ruff format --check` 同范围 | 07:22:33—07:22:33 | 0；11 files already formatted |
| CBM：独立src/assets index→schema→architecture→三trace→rg七表/来源caller | 07:10:52—07:11:21 | 八命令全部0；src未再变化 |
| inspect_frozen / inspect_final：PG反射、147源raw/Git blob、四原测试保字节、旧迁移/SBOM及五service冻结核对 | 完整起止在receipt | 0；七表、三函数、七trigger与10份JUnit材料 |

最终两个JUnit共490个distinct cases：unit327、contract22、integration74、security67（纯22 + PG45），全部 passed；PG119里含45 security，不额外累计。371=5新增迁移合同+原366；PG119=原33+fix15+R12原22+新增49。没有执行全仓库覆盖率门、全部回归或性能计分；`--no-cov`明确，不能把小切片的测试通过写成全局门通过。

原33+15及R12原22函数对象、原输入和断言原样导入adapter，仅替换自有数据库/schema/当前headfixture。4份原测试Git blob不改。R12的原local E5/reranker检查用已有权重实际运行，未下载模型或调用provider，不计外部live或本迁移新增模型能力。

新49项验证空schema生产0022、七表完整反射/trigger/partial unique；已填0019与0020逐20→21→22，排序原始to_jsonb行逐表逐字比较；每表count/hash/rawJSON原值保留；新连接与重复head后同值。旧BYTEA通过rowJSON原十六进制表示一起比较。0020四张投影也填有fixture行再升级，没有用空表比较代替已填history。真实事务中0021/0022 DDL与revision stamp后失败：表、函数和版本全部回到0020，再普通forward成功。六表各自UPDATE/DELETE实际23514；binding/review/receipt/assessment/watch FK、规则scope/type/hash/payload、sidecar复合FK与hash/JSON、不可变、同键两线程和事务rollback真实验证。

sidecar的canonical/hash持久化使用既有parse_sbom计算的显式synthetic输入，schema负例保证边界；这是DB存储合同，不声称SBOM importer/sidecar-only重判已接通。原规则/评估回归覆盖Unicode span、来源 roster、原文损坏/缺失、ACL/低权限/撤销、四态/版本/配置、准备与提交/读取当前性、发布/评估rollback及并发publisher。

原红不删：contract_red为未实现0021/0022的5失败；assessment_pg为新增fixture错误拦截Table.create，误拦Alembic自身版本表导致48 setup error、0业务函数执行，精确允许唯一alembic_version后原48全绿。schema_pg_extended为新诊断期待错误，非法visibility同时违反tenant XOR，PG先报ck_condition_rule_tenant：48pass/1fail；修正新case接受这两条精确scope check之一，仍要求23514且拒绝持久化，最终49全绿。未改DDL、原测试、gold或threshold。新代码Ruff初53问题、后续排版/import问题与原日志保留；逐项修复无新增ignore。一次PowerShell -c引号解析错误exit1在工具记录，未执行编辑、未保存磁盘日志，不伪造test红。

PG JUnit保留1个第三方Starlette/httpx弃用warning，未升级依赖。初步25/48/22通过和扩展轮仅历史迭代，不与最终119相加。

## 资源、制品与未运行

仅 `test_dianzi_r11_forward_rules_sbom_20261016`、自有随机 `test_r11_forward_` schemas；上限80，实际数量/库大小见 owned_resource_snapshot.json。PG16.14、pgvector0.8.2来自真实SHOW/extension查询；loopback25432、test_用户守卫。每条statement15s、lock5s、command300s、connection5s；pool8+overflow2。自有search索引 `dianzi_test_r11_forward_` 每fixture清理，仅loopback29200，原索引、Redis15与source业务数据未操作；PG自有schema保留供审查。授权截止2026-10-17T21:49:15+08:00，执行器显式检查。

私有DPAPI经明确pwsh7 subprocess capture读取，stdout JSON只在内存解析；真实密码不进argv/输出/报告。probe在backend/tests加载共享redaction hook并注册动态SecretStr；失败前脱敏。材料末尾actual密码扫描必须match0，receipt只记录数量/匹配文件，不回显值。0付费模型/API、0外部source/provider、0第三方扫描；预算unknown，没有开启付费批量任务。

seven_table_reflection.json保留真实constraint/FK/index/trigger/function；history_0019/0020及rollback_then_forward文件保留逐旧表rawJSON/count/SHA256。source_manifest保存147个源码/新文件/原测试的worktree SHA256、Git blob ID、blob SHA256与CRLF→LF区别；源码与材料版本独立绑定。owned run局部.gitattributes仅保护该目录raw日志/XML/JSON/脚本原字节与正常CRLF，未修改global attrs或忽略业务质量检查。artifact_manifest对raw材料大小/hash封存；可再生__pycache__不提交。

unit/contract/integration/security：本切片 passed，尚非独立review。frontend/e2e/live/manual：not_run；没有UI、真实来源/人工金标、OpenVEX、worker/API或正式准确率/召回率/持续监测/SLA声称。上述资源是隔离integration，不是production验证或最终验收。

合同偏差：无业务/公共合同变更；[变更记录](../../docs/decisions/CR-R11_rules_sbom_forward_migrations.md)准确登记静态DDL和历史不可删除的forward修复路径。评分证据只支持F2/F3可追溯内部规则/评估存储、F2资产sidecar历史及E1可复跑迁移/事务；P2真人标注、A1真实Agent、F3完整API与页面仍无本次验收证据。

下一项由主控安排新非作者source reviewer，在本代码/材料SHA上复跑；取得0020独审前置后才可限定本迁移结论。作者停在awaiting_review；不继续业务接线、R12或其他卡，不自行推送/验收。
