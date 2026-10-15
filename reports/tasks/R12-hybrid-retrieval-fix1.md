# R12 / T30 最终读取围栏 Must1 修复

状态：awaiting_review；本次窄修复实现 complete，unit/contract/security 回归 passed，真实 PG/OpenSearch integration passed，真实本地 E5/rerank 小样本 passed。frontend/e2e/manual、正式多跳/API/0020/worker 与完整 R12/T30/G-D not_run。作者不签 accepted、不更新 progress、不 push。

原代码 `f316a7aa432d6f730fa49189814c2559be8b6db4`、原材料 `a43d25e64dd00eaec63521c9457c7fa2228b8799` 及原作者 64/22、原 reviewer 四红全部保留。新测试代码冻结 `ba1548d591d2b341e61a230f1cdd5bd387f3235b`；基于原作者 worktree `D:/wt/r12-hybrid-retrieval` / `codex/r12-hybrid-retrieval`。新报告与材料单独放在 `reports/runs/recovery_r12_hybrid_fix1_20261016/`，不覆盖原 run 或原报告；材料清单见 fix_manifest.json，raw/LF/Git blob 核验及秘密扫描记录在那里。证据提交另附于交接，不改已测源码。

## 根因、最小复现与范围

已读本轮 AGENTS、00/T30、原合同/状态/handoff、原作者报告以及已冻结 reviewer 报告（`D:/wt/r12-hybrid-review1/reports/reviews/recovery/G-D-R12-hybrid-retrieval-review-1.md`，SHA256 `cdfeb41e48afa73ba3ddaf29249b304d43d67ca8cb3237fce648e596bd2fb8f3`）。只读参考已审 R10 fix2 的 fresh current read → 锁定 epoch → 事务内构建顺序，没有修改其文件。

仅业务改动 `backend/src/ai_intel/retrieval/hybrid.py`，直属新增 `test_r12_legal_publication_window.py`、`test_r12_final_snapshot_fence.py` 和本次自有报告/run 脚本。原 R05 service/persistence、共享模型、认证、settings/lock、0020 或其他迁移、worker、原 tests/gold/门槛/计数分母及 progress 均未改。

原逻辑在最后一次完整候选读取之前无锁读取 final_epochs，并在 Session 关闭后构建 HybridSelection。合法 `KnowledgeRepository.publish` 可以在这两个位置提交：新增 source_verified supported claim 或 supported source_status=withdrawn；PG epoch1/claims1 → epoch2/claims2/receipt_epoch2，而原服务仍可能返回 epoch1、partial=false，最后候选读取后撤回还会保留旧 hit。正常发布器没有出错，单纯再做无锁 double-check 仍留构建窗口。

初始反馈环为只读复制 reviewer 的四例脚本：原 bytes 存 `reviewer_legal_publication_window.original.py.txt`，SHA256 `b55f8ca4e2060d5ee541351b92cd7c0653a6d988bb23cac877390864f7efe852`。作者副本只更换自身 fixture 导入与格式/导入排序，不改四例输入、阶段、断言、期望；对应 `must1_red` 真实4 failed，13.4137s命令墙钟、pytest10.13s，全部合法发布且没有手动改/恢复epoch。复制只读原文件和本轮初期源码定位命令没有逐条起止 receipt，未补造。初审副本和其已封材料从未运行/覆盖。

## 最小封闭修复

保留早先无锁 epoch/candidate 观察，使原注入窗口照原时序复跑。最终 phase 明确 READ COMMITTED，按既有 R10 顺序对原可见候选的 source/document/revision/event/claim/evidence/text block、event-document 和 claim-evidence identities 加 FOR SHARE；每组 ID 排序，带 visibility 的行独立按认证范围过滤，不锁全表或其他 tenant。随后完整重新执行 facts_query / EvidenceSpan 验证，不能拿锁定 ID 替代当前事实查询。

完整 fresh 候选读之后才按授权 scope_key 排序 FOR SHARE 锁/重读 epochs，并比较起始和观察 epochs、完整候选。发生变化就 partial/空证据或过滤变化 hit，最终 scope_epochs使用锁定读取值。HybridSelection 与 trace 均在同一事务持锁时构建；异常会释放事务，不吞数据库失败。所需 PostgreSQL 语义参照 [PG16 行锁官方文档](https://www.postgresql.org/docs/16/explicit-locking.html)：共享行锁在事务结束前阻止相同行更新，不能用无锁再读代替这个边界。

返回对象的当前性以事务内构建时的受保护快照为准；锁释放后的新事务可正常提交，调用方以后发布回答仍须重新核对认证/事实/epoch。本内部服务未增加鉴权 API，也不承诺快照返回后永远不变。已有时间过滤仍是当前事实可用时间，没有实现历史真值。

## 写入方与 ACL 核查

本 worktree 源范围 CBM0.11 fast 独立 project=`dianzi-r12-hybrid-fix1-backend`，cache=`/tmp/dianzi-cbm-r12-hybrid-fix1-20261016`，仅 backend/src，未索引附件/秘密/holdout/run。index/schema/retrieval architecture、retrieve outbound、KnowledgeRepository.publish outbound、save_change_publication outbound、bump_scope_epoch inbound、EventRepository.publish_events outbound、persist_catalog_documents outbound 以及 rg 交叉全部 exit0。1535 nodes/7994 edges；not_indexed/skipped/parse_partial/parse_unusable均0；工具 excluded 摘要含 assets/cache，不能据此认定这些业务已审。

rg和实际源码确认：KnowledgeRepository.publish 在同一业务事务写 claims/support/receipt 并调用 save_change_publication → bump_scope_epoch；EventRepository.publish_events/merge_events/undo_merge 也经同一发布 helper；catalog 文档新建使用其事务内 public epoch upsert。已有引用/修订创建、source registration 的 visibility 来自可信范围，本基线没有知识记录 ACL 变更的产品 API。已有认证/角色变化仍由 API 调用方的锁定认证上下文处理，本次未触碰 auth。不能凭这个缺口另造一个 ACL API；额外 ACL 竞态以明确 raw PG 安全负例验证当前可见源/文档，而不是宣称已有生产 ACL 调用闭环。

新增并发对照用真实后台 writer 和 pg_stat_activity.wait_event_type=Lock 的实际观察，不靠睡眠后推测阻塞，不把锁超时当修复成功：新 claim、source withdrawal 的正常发布在 trace 构建期间等待，退出读取事务后正常 receipt_epoch2；visible source ACL 更新也等待，释放后下一次检索排除；final candidate之后、加锁前的 doc ACL 改动无手动epoch，fresh读排除；hidden tenant-b 正常 publish 在 public 构建期间直接成功，public仍只锁public且不回显私有候选。writer受自身2s lock timeout与测试有界future控制，任何超时/异常算失败。

## 实际命令与结果

所有下列入口由 `fix_checks.py` 记录完整argv/cwd/+08起止/退出码/墙钟/log/code SHA；私有DSN只从原授权 WSL connection.json capture内存、校验资源身份后注入 env，未读主控其他 vault，未进argv/报告/模型。复用原自己专用 testDB，每例自有 test_r12_hybrid_* schema/dianzi_test_r12_* index，精确自身清理记录保留。未重复全局GET `/`、flush/restart/drop共享服务，也未续期。

| 真实检查 | 结果 |
| --- | --- |
| `fix_checks.py --services must1_red -m pytest tests/integration/test_r12_legal_publication_window.py -o addopts= -q -s --tb=short --junitxml=.../must1_red.xml` | exit1，4 failed/0skip；原合法发布四例红全部保留 |
| `fix_checks.py --services must1_first_green ...同四例...` | exit0，4 passed；新事实/撤回均返回epoch2、partial/空证据 |
| `fix_checks.py --services must1_thread_first -m pytest tests/integration/test_r12_final_snapshot_fence.py ...` | exit0，5 passed；实际锁等待/释放/hidden tenant独立性 |
| `fix_checks.py --services whole_integration_draft -m pytest tests/integration/test_t30_hybrid_retrieval.py tests/integration/test_r12_legal_publication_window.py tests/integration/test_r12_final_snapshot_fence.py ...` | 未提交草稿 exit0，31 passed；code receipt为当时HEAD a43，不能冒充其源码通过。后续已冻结完整复跑 |
| `fix_checks.py --services frozen_integration ...同三文件...` | 冻结ba1548d5；exit0，31 passed/0failed/error/skip=原22+本轮四例+五对照；06:08:42.972513–06:09:59.578158+08，命令76.6061s、pytest74.48s |
| `fix_checks.py frozen_fixture -m pytest <原六文件> -o addopts= -q --junitxml=.../frozen_fixture.xml` | 冻结ba1548d5；exit0，原64 passed/0skip；未改原断言/数量 |
| `fix_checks.py frozen_mypy -m mypy --cache-dir <仓外r12 cache> src` | exit0，122源文件无错误 |
| `fix_checks.py frozen_ruff -m ruff check <本轮5个直接文件>`；`frozen_format ...format --check...` | exit0；5文件lint/format通过，没有新增ignore |
| `fix_cbm_checks.py` | 所有上述窄read/writer轨迹和rg exit0，逐命令receipt保留 |

冻结真实 E5/PGvector/重排为原C02单个三条synthetic中英样本，其余30集成例为明确fixture semantics，不冒充semantic live。没有新权重下载或付费API。中文完整 retrieve 4.5800s、英文6.1528s（含最终PG围栏）；英文超过5秒保留实数，不改门槛，不签全系统QA/SLA、召回率、准确率或评分档位。

初始静态检查4项（docstring101字符、两个import排序、run脚本E402）保留失败日志；导入改为stdlib import_module、排好序和短docstring后通过，不新增ignore或隐藏原红。业务共根因一次修复即将原四例转绿，没有使用两次无进展后扩大补丁。

## 交接与剩余范围

根因与旧64/22绿不覆盖最终窗口的事实均已明确：只有本轮合法发布与锁持有对照能补上这条当前性证据。请原独立 reviewer 定向复核新代码ba1548d5及新fix_manifest；作者仍只awaiting_review。本修复不签完整R12/T30/G-D，不接0020/worker/settings/answering/API/UI/graph，也不影响资产四态前置或官方评分/金标/分母。主控后续生产接线须采用同样的最后认证/事实事务围栏，不能用本返回对象代替未来提交点的验证。
