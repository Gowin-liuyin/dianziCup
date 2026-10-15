# R07 · 幂等范围修复小批

状态 `awaiting_review`，本窄修复实现 complete，未签 accepted、未 push。新隔离工作树 `D:/wt/r07-idempotency-scope`，分支 `codex/r07-idempotency-scope`，基线 `e61d9d6dd1215c337755d32d112dfe70f13d9e94`，代码冻结 `ba69d6cbc2bc4828a56bdc8c7d2f2c95c4dda5ce`（7files、832 insertions/8 deletions；业务service为130 insertions/8 deletions）。源 raw blob 与完整材料 manifest 绑定该 SHA。

只改 `backend/src/ai_intel/enrichment/job_service.py` enqueue/规范范围/旧记录核验 helpers；新增 unit、contract、PG、API alias、security 与直接专用 fixture helper 六文件。未改 API、settings、worker、shared contracts、迁移、锁文件、table metadata、全局 attrs、progress、既有测试或金标/阈值/分母。源码检查全部调用方：HTTP enrichment_routes 接同一 service.enqueue；runtime_policy 构造 service；handler/child enqueue 及 source/polling/outbox 调用不改。

新规范键绑定认证 tenant、canonical event route、actor user_id、raw key，以固定 JSON+SHA256 生成 77 ASCII 字符；None 与 literal public 分开，Unicode/delimiter 不混。job tenant 仍为 event scope，worker rule/payload 不升级。新/旧复用必须核原 PG payload reference/digest、WF UUID/parent/scope、request/policy 型别/摘要与完整 binding。准确旧 actor/event/auth tenant/body/session/policy复用原job/UUID；合法其它旧范围独立新建；未知/orphan/tampered拒绝。非富化来源同 key 原样保留，不读其 payload；合法 v2 key 作为新 raw key不别名。新 session、body/policy同范围变化仍409，不进新namespace绕过冻结收费预约。

真实命令均由 `backend/.venv/Scripts/python.exe reports/runs/recovery_r07_idempotency_scope_20261016/run_scope_checks.py <mode>` 运行。各 JSON 记录展开 argv、cwd、Asia/Shanghai 起止秒、退出码及 JUnit 数量。新 unit 6/6、contract 2/2、PG 16/16、security 8/8；原执行21+API9+固定独立探针2+新HTTP POST alias1 共33/33 passed，exit0、0skip。静态 ruff check、format --check、mypy job_service、git diff --check 四项实跑通过，static.json 留实际命令。`--no-cov` 是专属行为检查；整体 coverage 与评测未运行。

固定探针来自 `D:/wt/r07-default-entry-review1/reports/runs/recovery_r07_default_entry_review1_20261016/probes/test_independent_idempotency_scope.py` 与共享脱敏 conftest，完整字节复制到本批 probes，未改 inputs。baseline_job_service.py 为 git show e61 的精确原 blob（SHA256 `13dd4cfe22ab590bcf74483656d7ef1c9eb745f0bc02909d0876029b5a1daa5e`）；baseline_import pytest 插件在 collection 前载入并断言 blob。原32案例 red_064241 为30pass/2fail：两个独立probe都收到旧409；同一原输入在修复后的 regression_064400 为33pass（包括新增alias），0fail/0skip。

早期红证据保留：red_064015 是29pass/3fail，第三项为旧21用例固定NVD报告目录在fresh baseline不存在，非业务缺陷。专属 artifact_redirect 仅将该固定输出落到本批 owned run，旧测试和断言不改。PG/security首轮同时尝试 CREATE 同一专用 DB，PG bootstrap 发生 UniqueViolation、pytest未运行；安全层正常8pass。以后专用 DB 已建立、PG检查串行启动并全16pass，此 harness 失败记录为 not_run，不计业务失败或 skip。初次 CBM/依赖建立起始时钟没有单独落盘，标 not_recorded，不依 mtime造时间。

PG 专用 `test_dianzi_r07_execution_scope_20261016`，每例独立随机 schema、真实 forward head `0019_aggregate_observations`。原 API fixture 必需 public schema/default factory，按原 guard 使用专用 `test_dianzi_r07_execution_api_scope_20261016` base，再由原 fixture 创建随机 test API DB；未改 fixture逻辑。凭据只在 Python内从指定 WSL connection.json 捕获，未进argv/stdout。source queue15/e310 collector及其DSN未读写。没有外部模型/provider/source网络或付费调用，费用unknown；旧预约是明确合成 potential paid reservation，未声称实账费用。

PG新例覆盖同范围重放/并发唯一、双actor双event共key独立、auth tenant null/public、200字符Unicode/delimiter/ASCII键，body/policy/session双方新旧409，旧UUID/已预约step不变、不同旧actor/event独立、legacy actor tenant变化冲突、来源同key不动、v2 rawalias不别名。security实PG覆盖request/policy/actor/UUID/payload/orphan篡改、v2prefix篡改、公共写角色不足/私有跨租户拒绝、私有合法tenant授权和body身份字段拒绝。secret扫描使用实际私有凭据值及受控环境secret值，不保存值或其hash；外部 probes 显式加载仓库共享脱敏hook。

CBM 先为新WT backend/src独立index `r07-idempotency-scope`（v0.11、1588 nodes/8454 edges，现有assets目录过滤），schema/architecture/enqueue_job双方trace与rg源码交叉；发现父enqueue、子enqueue和sources共用outbox函数，因此根因修复只在富化父namespace，不改变公共outbox行为。原graph/artifact保存在本批run，无全局attrs变更。

合同偏差：无。CR-R07_idempotency_scope_proposal 记录批准方案和安全rollback。评分仅为R07/R03的05幂等、安全和历史收费边界证据；不产生准确率/性能/正式分数。live/e2e/manual未运行，本批没有Celery真实broker消费验证。下一步主代理合入冻结代码/材料，由原独立reviewer固定SHA重跑两个原probe及legacy/concurrency针对复核；root独占stage/Git push。此批结束停止下一任务。
