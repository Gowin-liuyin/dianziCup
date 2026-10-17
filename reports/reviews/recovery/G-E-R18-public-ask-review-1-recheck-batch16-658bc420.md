# G-E · R18 public ask 独立审查 1 · fix1

首次登记：2026-10-17T07:21+08:00。原502报告、原深层JSON红与已封62文件材料保留。本报告只针对 Root ACK 的新固定 source `3873c113c7a1a4a7412dcc8a57c6480ea0f83f0c`，不引用旧报告作为新版本通过依据。

这项修复做什么：route 的解析异常边界新增捕获 `RecursionError`，沿原固定 422 problem 返回；新增一个深层 JSON HTTP contract。未改变共享 JSON decoder、深度/节点/1MiB限额、凭据/actor、额度/预约、公共 DTO 或其他业务。

当前结论：**原 Must1 的修复已由独立相同负例核实，离线与CBM检查通过。实际PG尚未执行，不签此route验收或整R18。** 没有新可复现 Must，仍保持 `awaiting_review` 的集成缺口。

## 固定 snapshot 与原负例

第二独立 WT：`D:/wt/r18-public-ask-review1-fix1-20261017`，分支 `codex/r18-public-ask-review1-fix1-20261017`。父提交精确为502，diff只有 route 的一处异常元组与新增12行contract；本 reviewer 未改业务/原测试/状态/金标/阈值，未commit/push。

新 snapshot 四文件均独立与 `git show 3873...:path` LF 字节相等；见 `fix1_inspection.json`。原自有负例文件原样复制，旧/新 SHA256 同为 `ac47160c4b54ba9686561c77ed331aafc6c289f51d47dc58751df85101e8ad28`。原 depth20000 输入仍为40022字节，没有改输入或期望；原502返回500的红保留，新3873返回422 validation_error。

## 新版本真实执行

新 run：[r18_public_ask_review1_fix1_20261017](D:/wt/r18-public-ask-review1-fix1-20261017/reports/runs/r18_public_ask_review1_fix1_20261017)。普通检查仍先加入原生Job再启动child，512MiB/process、1GiB/job、24逻辑核rate833约2核、native active cap10、outer Windows完整子树cap10、每条≤60s；普通实际peak5–8、owned残留0。每条完整argv/cwd/时间/exit、native query与子树保存在 `.command.json`/`.native_job.json`，stdout/stderr/XML保留。

| label / 实际命令核心 | exit | 结果 |
|---|---:|---|
| `fixed_route_and_same_oracle`：`pytest --no-cov -q` 新unit/contract + 原样自有HTTP负例文件 | 0 | 70 passed，12.47s；55新route + 15自有负例 |
| `affected_shared_regression`：`pytest --no-cov -q` 原R05 grounding/question unit/contract、R18 credential unit/contract、public write unit/contract，八文件argv见收据 | 0 | 231 passed，8.46s |
| `fixed_route_ruff` / `fixed_route_format`：ruff check与format --check四文件 | 0 / 0 | 四文件通过 |
| `fixed_route_mypy`：mypy route --cache-dir=nul | 0 | 新route一文件通过 |
| `fixed_capture_http` | 0 | 新 snapshot 重跑一个已计入的fixture HTTP用例，生成新wire；不重复加计数 |
| `fixed_frontend_parser`：Node384MiB heap/8MiB semi-space，实际TS parser | 0 | 接受实际新route fixture JSON；拒extra authority/task/缺引用/伪support/危险URI，共6断言 |
| `fix1_snapshot_inspection` | 0 | 四文件git-show相等、same oracle bytes相等、XML去重与CBM计数实查 |

新版本去重 pytest：**301 passed / 0 failure / 0 error / 0 skipped**，TypeScript6断言单列。原全部覆盖率60%门未执行、未降低；子集使用明确 `--no-cov`。

## 独立 CBM 与资源归还

Root ACK 并由作者归还排他窗后，本 reviewer 从新独立 WT 复制16个调用链模块，生成自有 `cbm_snapshot_manifest.json`；缓存、project、源码独立于作者index。成熟控制逻辑来自 Root 指定 `D:/wt/r06-native-review1/codex/r06-native-review1/reports/runs/r06_native_snapshot_review1_20261017`，只适配固定ROOT/source/snapshot/query，补齐配套process_metadata.py。

首次启动缺配套 `process_metadata.py` 的 import 失败发生在WSL启动前；`cbm_initial_missing_metadata` 的 exit1/原stderr保留，非业务失败。补齐成熟原模块后通过 Root 已授权 full16/≤60s 窗执行：help、index、graph schema、architecture、router trace、shared ask trace六工具实际全exit0且非isError；索引329 nodes /1491 edges，16 Python files，unindexed/partial/unusable均0。

实际外层开始07:15:30.842、结束07:15:49.864（19.022s），Windows peak8 + guest peak5 = combined13≤16；完整guest控制祖先到PID1、birth全部匹配、每child真实wait退出，owned残留0。PID1仅保守祖先计数，没有作为cleanup root。Windows Job 512MiB/process、1GiB/job、rate833；guest两核affinity和Go480MiB软限，未冒称guest hard memory cap。资源已即时ACK归还Root。

router图仅显示factory/route及共享constructor，嵌套closure的实际credential/actor/scope路径继续以源码核对；shared ask的图边也没有替代PG锁/事务证据。默认挂载未接入不能由窄图0caller推导全部产品状态。

## PG计数纠正与提交Root的受控入口

按原67collect实际nodeid逐文件统计：**public18 + question-credential25 + old-cookie24=67**。作者/初交接的public19+old48为手算误差；没有删case、调断言、改分母。新public PG文件与502原样，全部18完整case计划分为5/5/5/3四批。

自有PG入口已离线准备，没有打开PG、读取DPAPI或连接数据：

- `run_pg_review.py` SHA256 `9073e210f4a3421fe7823bd7a8fdd810c17fbf26c381d6d59cf77d8e1e7bf4cb`。
- `pg_controller_admission.json` SHA256 `b3a9090ca4176654c2e953d5bb13e64f5e1acf76e06d815563378f1440a93e96`。
- 固定WT/source3873，auth tag `r18-public-ask-review1-fix1`，labels `pg_public_1`—`pg_public_4`；`pg_batch_plan.json`保完整原nodeids。
- 原mature qcr controller 的58s总窗、48schild cutoff/清理余量、native9字段、Source OID10451302/10434264原样before-after、2 target+1 parent sampler、nonce/OID/owner/exact COMMENT/零连接后drop、birth清树、采样释放及secret scan保留。controller直接worker_entry运行pytest，未套nested普通checks。
- 适配仅改固定environment/metadata模块引用与owner/run标签前缀，移除本次不适用的旧cookie重映射；完整diff是 `pg_controller.from_mature.diff`。Root独占launcher、DSN/DPAPI/env与排窗，本 reviewer不会自行启用PG。

当前 actual PG=0，integration=`not_run`，不是集成passed。须由Root审核上述admission和完整case计划再发实际隔离窗口，复查quota rollback/replay、cookie/Bearer、两个owner、expiry/revoke、IO时撤销/current evidence、pending并发及原共享回归；Root旧route alias checkpoint另由原qcr reviewer复核。

## 产品与验收边界

source3873本身仍无默认App mount、Authorization CORS和公开AskRequest requestBody OpenAPI metadata；作者对此诚实披露，ownership属于Root，不能借当前isolated router验收默认公开产品。共享 strictJSON 的另一个修复切片也未混入本source。

模型/语义/费用/浏览器/e2e/live/性能/云CI/CD/人工仍未检查，fixture来源和data_mode没有伪装live。本报告不签整R18、T35、T51、阶段或评分优秀，状态登记由Root据完整新版本证据处理。

Verdict：**Must1离线关闭；PG待实际窗口，当前不签route验收。** 下一步运行完整18个新PG cases及必要原回归，默认产品挂载后另做fresh review。
