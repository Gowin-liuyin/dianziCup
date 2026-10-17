# R18 trusted task QA reader · 首次独立审查

本变更增加固定的同事务 QA 读取端口，复用 owned answer 读取与当前证据重验；旧同步读取保留 expiry、认证及历史行为。本次结论为 **needs_changes：先修复下列 1、2 两项**。338 项既有离线通过不能覆盖独立负例；本报告不验收完整 R18、T35、默认产品链路或 live。

## 固定范围与依据

- Source：`b46e4642a22920256be4d769dc0373232658cf71`，从该 Git 提交创建 `D:/wt/r18-qa-reader-review1` / `codex/r18-trusted-qa-reader-review1`。基线：`9d8b222cd6cfcc87e618867c918a1b8fcdafa32f`。
- 待审相对基线仅 7 文件：`answering/service.py`、新增 `api/public_task_result_reader.py`；直属两个 unit、一个 contract、一个 security、一个 integration 测试。没有使用作者移动工作树的业务文件。
- f316 的八个固定依赖由 `git show f316c7af54bfc14de3b345c39d90aac2b9699872:<path>` 逐原始字节读取，含 binding、0031 及六个测试；逐文件 hash 与 byte count 见 `dependency_receipts.json`。这些仅为审查输入，没有提交、修改或当作本作者新实现。
- 已读 AGENTS、执行地图、R18 恢复卡、T35、T34、公共问答/任务合同、数据/工作流合同和 T45 安全卡；应用 Ponytail **5.3.1 review**。标准与合同按项目权威顺序核对。
- Root 正式 CR：`docs/decisions/CR-R18_task_qa_publication_receipt.md`，原字节 SHA256 `aa4b3cc6c1c3fb5e305fcea07ecd5da7beaba06e0c8963c32d675b4f8146f760` 已一致。建设授权允许提取同 Session seam 并定义内部 receipt，不代表实现符合其“模型 prompt/request digests 全部匹配”的要求。
- 本轮只写本报告与 `reports/runs/r18_trusted_qa_reader_review1_20261017/`。不改业务、schema、locks、Root state、金标、分母，不操作 Source 库，不读取或解密秘密，不 push，不登记 accepted。

## Must fix

### 1. [P1] critic 回执没有绑定它实际检查的声明

位置：`backend/src/ai_intel/api/public_task_result_reader.py:107–134` 与 `:302–326`。

职责：reader 应证明同一任务的真实 generation/critic 回执支持当前回答，而非只检查存在一个成功 verdict。当前 `_model_output` 仅检查 operation 的 request SHA 是 64 位 hex，再使用这一行的同一值重算 call_key；完全不比较 attempt 的 `prompt_sha256/schema_sha256/body_sha256`，也不重建 critic 实际输入。`SupportVerification` 只有 claim_index 和 verdict，不能单凭编号证明它检查过当前 draft。

实际触发和结果（显式 fixture，不是 live/PG 证明）：

1. 将 QA/critic attempt 摘要改为 `not-a-digest`、空串和 `invalid`；reader 仍返回 completed。
2. 用实际 `GenerationRequest`、schema/system/user/wire 编码算法构造另一 question、另一 claim 的 critic request/prompt/schema/body 摘要，重算该 operation 的 call_key，保留其 claim_index=1 的 supported verdict；reader 仍返回原声明 completed。

原观察命令 `independent_receipt_negative` 退出 0 只是观察脚本成功执行，**不是安全测试通过**。独立回归 `independent_regression_expectations` 中对应两例均失败：`DID NOT RAISE PublicTaskIntegrityError`，没有改金标、skip 或扩大误差。

影响：不可变记录存在仍不足以证明 critic 检查过当前声明；不符合已批准 CR 的输入摘要绑定要求。当前尚无 default publisher，因此本次没有证明公开接口可被远程利用；问题在受信 reader 的验证边界本身。

最小修复条件：从该任务的固定实际请求及同组不可变证据输入重建 generation/critic 请求，等值核对 operation request 摘要与 attempt prompt/schema/body 摘要；critic 的 claims 与 selected citations 必须绑定当前 draft。若现有记录不足以重建，明确拒绝并由 Root 走最小合同细化，不能只验证 hex 格式。`AttemptMetadata.response_sha256` 是原始 wire body hash，不能把它与 canonical value hash 错比。

复验条件：冻结原探针，两例变为明确拒绝；合法实际编码请求仍通过；重跑本切片及相关回归，并以真实隔离 PG 核验成功不可变记录的绑定。修复后的源码另需新非作者审查。

### 2. [P2] 无关 context 假设会撤销合法的已确认支持

位置：`backend/src/ai_intel/api/public_task_result_reader.py:354–376`。

职责：`uncertain_support` 应检查回答依赖的关键支持。当前查询对被引用 span 的所有 current claim 一票否决，没有区分 `supports/refutes/context`、验证状态、事件/修订闭包或 ACL。

实际触发：同一公共 span 支持 claim A（supported/true/current、supports/validated），同时 claim B 为 unverified/unknown/current，只以 context/unverified 引用该 span。回答只陈述 A，QA/critic/receipt 全部相同。该并存情况在知识发布合同中合法：`KnowledgeRepository._validate_submission` 允许初始 unverified/model_hypothesis，并只对 supported 要求 validated supports（`knowledge/persistence.py:361–372、423–457`）。

独立探针让 reader 执行其真实 SQLAlchemy 查询，经 SQLite 编译并执行于隔离内存表：无 B 时 accepted；加入 B 时实际命中 `unrelated_hypothesis`，reader 返回 `public_task_answer_support_not_current`。仅业务 Session 与其余证据闭包使用显式 fixture；**未把 SQLite 结果写成 PG 通过**。独立回归第三例要求合法答案继续可读，实际失败。

影响：无关背景假设可使已真实支持的 QA 不可用；同 span 的不可见或其他事件关联也可能扩大错误拒绝范围。这里不是把实际关键 unknown/conflict 放宽为 current。

最小修复条件：负查仅检查实际参与当前关键命题支持/反驳、已验证且位于已锁定可见闭包的关系；仅 context 或无关声明不能否决 A。保留真实关键 unknown/conflict、撤回及权限下降的拒绝。

复验条件：原 A/B 并存探针从拒绝变为接受；同一关键命题的真实冲突/未知仍拒绝；补真实隔离 PG 并存及权限场景，重跑当前 ACL 锁和 epoch 用例，不以删难题或缩分母过门。

## 已核对且本轮未发现新增阻断的边界

公共调用路径为 `PublicTaskBindingService.publish_result_in_session/read_in_session → _read_result → PublicTaskResultReader`。binding 的 `_connection/_session_fence` 核 service Engine、所有 metadata 表绑定、每条语句实际 Connection 和 Session/ConnectionTransaction 身份；直接 reader 调用目前只有测试。reader 抑制 autoflush，执行 SELECT/FOR SHARE；不启动新模型、配额扣减、外部 IO、commit/close/expiry 更新。

首次 publish 与 replay 在 reader 返回后重新核 PG clock、actor、lease、attempt、deadline；read 最终再认证。新 reader 核 owned/completed answer、task/request/owner/workflow/job、publication 固定 key/kind/role/status、canonical response hash、admission/completion/latency、draft claims 与 rendered 文本、逐声明支持覆盖。实际枚举与现有 operation 表/完成后 immutable trigger 一致。

证据仍复用有界 Source/Document/Revision/Event/Claim/Evidence 闭包、加锁、引用原文与 Unicode span/hash/locator、当前 epoch 与 ACL 重验。历史 answer 没有被写回；旧 `read_grounded_answer` 保留 expiry → 初始 auth → shared read → final auth，AST 合同核非读取节点未变。

## 实际执行与限制

执行工作目录：`D:/wt/r18-qa-reader-review1`；所有普通业务检查使用本 ownrun 的 `review_checks.py`，base Python 3.12 与已批准 site-packages。内核边界为 512MiB/process、1GiB/job、约 2 CPU、60 秒、native active 9 / full Win 10；每个 `.command.json/.limits.json` 留实际 argv、时间、退出码、PID/birth/control chain，owned 残留全为 0。`--no-cov` 只用于限定功能切片，未签全仓覆盖门。

| label | 真实结果 |
|---|---|
| `reader_new_94`：两 unit + contract + security，pytest --no-cov -q | exit 0；94 passed，3.37s |
| `reader_old_244`：R05 grounded/question + R18 credential/binding 原 unit/contract/security | exit 0；244 passed，10.16s |
| `collect_pg_19`：新 PG 文件 --collect-only --no-cov | exit 0；19 collected、0 executed |
| `independent_receipt_negative` | exit 0；两种错误 receipt 均 accepted，缺陷观察 |
| `independent_context_negative` | exit 0；无 B accepted，有 B support_not_current，缺陷观察 |
| `independent_regression_expectations` | exit 1；3 failed、0 skipped，1.59s；两拒绝预期与一个合法保留预期失败 |
| `reader_mypy`：--follow-imports=silent --cache-dir nul --show-traceback，两目标源 | exit 0；2 source files 无问题；没有跳 imports、抬内存或忽略类型 |
| `reader_ruff` / `reader_format` | 各 exit 0；7 文件 check/format |
| Git source diff/check | 文本 diff 空；待审源仍为固定 b46；未 stage 业务 |

PG v2 启动包只核读、未启动：controller SHA `d8f32a4206189e8f186e2d021309ad93d002d88b16ddfdfe808674cc7eac1124`；admission SHA `036a1d3ef5f9eadbf759a7ee4b6ec20bec67258b94148ef30219b4f22af6be84`。12 entry hash 全匹配，253 source/dependency/fixture hash 与独立 Git 输入全匹配。两个 checkout CRLF 差异已从 b46 Git blob 恢复原字节，逐笔见 `checkout_line_endings_receipt.json`，语义/文本 diff 空。包固定 7 单标签组、19 原用例、nonce DB/schema/原 OID、head0031、target2+sampler1、58 controller/48 child/60 native、Source 不改；只有 Root 可注入 memory-only DSN 并执行。原 PG19 后续即使绿也不能覆盖上述独立红例。

Root 授权的受影响 CBM 独占窗已执行并明确释放：新 project/current b46，加 f316 固定依赖；200 个 Git 原字节 snapshot，8 CLI 均 exit0/isError=false，28.828 秒，combined peak15≤16，Windows/guest owned birth 残留均0，Ubuntu-22.04 默认用户。index 2817 nodes/16820 edges、not_indexed/partial/unusable=0，但工具默认排除 assets 一目录；不是全仓完整索引。guest 是 GOMEMLIMIT 软限制与 2CPU affinity，未声称 guest 硬内存通过。图中具体 reader caller0；动态 Protocol 由全源码 rg 补核，不能凭图的0掩盖 `_read_result`。shared read 的两个直接 caller 是旧 engine wrapper 与新 reader `_read`；legacy route/ask 间接调用保留。

integration 实际执行 `not_run`；live/manual `not_run`。新 publisher 未产生 receipt、默认 App 未装配具体 reader；stack、资产、多事件、会话和历史 task 范围明确 unsupported，当前旧同步回答不会自动变 task success。真实模型、多跳、9职责最终能力、客户端/插件/吞吐/持续运行均未在本轮验收。

## 原材料冻结与下一任务

原探针 SHA256：`probe_receipt_digest.py=40f80f4a6caab8e5e25cd499c10944e82001a4030a1a98b3747f294051dd8c5d`；`probe_unrelated_context.py=0a8d92de2dedd5d255ff16d2eaf36407ba41b2d3f6883f99ccef038125680784`；`test_review_negative_cases.py=e7a9d75a3340045f67e15a84720bd2015282ec957e7c74e4a6d698d3f37f5351`。完整原字节、JUnit、stdout/stderr 与命令回执保存在 ownrun，封存 manifest 另列文件 hash。没有代作者修代码，也没有覆盖历史红例。

原 context 回归中 `matched_claim=unrelated_hypothesis` 是本次错误查询确实命中 B 的观察佐证；修复过滤条件后该字段可为 None。修复复验的业务条件是 A 与仅 context 的 B 并存仍可读，真实关键冲突仍拒绝；不能要求正确实现复现错误查询的内部命中。保留原文件原字节，后续评审应独立核对这个区别。

首次材料提交的 `git diff --check` 为 exit 2，来自保留原字节的 CRLF JSON 与借用控制脚本，被 Git 当作尾部 CR whitespace；原输出和退出码保留为 `material_diffcheck_initial.*`。追加的 ownrun 局部属性仅将原始 JSON、原控制输入、日志/XML 和 CBM snapshot 作为字节材料保存，不改 probe、业务检查或测试期望；最终材料检查另有记录。初红没有删去。

评分证据只支撑 A1/E1/X1、T35 的该只读验证边界审计；未贡献真实多跳、模型准确率或性能分。下一任务是唯一 reader fixer 按冻结负例修 1、2 后，新非作者重审，再做 Root 隔离 PG 与独立 publisher/default wiring。**有限结论：needs_changes；未验项不得据已有绿数签整体 R18。**
