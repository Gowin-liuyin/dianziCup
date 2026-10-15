# R04 PDF/JSON 解析切片独立审查 1

初审首次创建/写作开始：2026-10-15T12:32:41+08:00；初审写作结束：2026-10-15T12:34:51+08:00；报告最后更新时间：2026-10-15T12:41:17+08:00。审查者 `/root/r04_pdf_json_independent_review`，未参与实现。初审结论针对下列固定提交：**needs_changes / partial**；不签整 R04、T09 或 G-B，不改 progress。

**当前结论（2026-10-15T12:40:02+08:00）：48ad907 的解析组件技术定向复核 passed，初审问题1/2和当前数值覆盖缺口3已关闭。** 下文f2初审与失败事实完整保留；复核范围、命令和未测限制见末尾附录。整R04、R04:T09完整闭环、整T09与G-B均未接受。

What this change does: 此变更用 pypdf 6.20.1 的受控独立进程替换伪 TEXTLAYER 解析，保留实际 PDF 页码和规范文本区间；JSON 改为严格重复键、非有限数和 RFC6901 叶路径处理。PDF 子进程隔离和版本兼容路线合理，但 JSON 尚有两处可复现的证据输入缺陷。

## 固定对象与边界

- 基线：`7f9b6f14e3c7c5ff451fab183f959a11d8daf114`。
- 被审 SHA：`f2c5873fa8c2695ae81d673e7107ada3e9b52a81`；Git tree `c8f89d09f3e44804247893ced89f7fa05aeb0f82`；`backend/src` tree `1bbf6fb1f0c181625f3a08d7bfdf84b01779c323`。
- 独立干净 WT：`C:/Users/yinha/.codex/worktrees/recovery-r04-parsing-review/dianzi`，branch `codex/recovery-r04-parsing-review`。仅新建 WT、独立 venv、自己的探针/日志/本报告；业务、锁、合同、progress 未改，无提交/push。
- 必读：AGENTS、execution_map、R04 卡、T09 卡、03 数据合同、04 工作流、CR-R04-R04_document_parsing、R04-parsing 报告与固定树进度；新版插件 ponytail-review 和 PDF 技能已读。
- 实际独立执行日志始于 `2026-10-15T12:22:49+08:00`。全部带收据命令的 argv/cwd/起止秒/exit/timeout 在 `reports/runs/recovery_r04_parsing_review_1_20261015/*.receipt.json`；汇总与源码/锁/合同/PDF hash 在 `evidence_index.json`。
- 未读 `.env`、KEYS、DPAPI、holdout、私有 DSN；未启动 PG/Docker、未调用付费 API、未运行外部附件命令。

## Must fix

1. **JSON 字符串叶被重新转义，原始 Unicode 引文无法定位**（`backend/src/ai_intel/ingestion/parsing/parsers.py:116–117`，P2，确证）。

   - What this is：json2 应保存 RFC6901 字段路径和原始 Unicode 值，供 `locate_evidence_span` 精确回切。
   - Problem：合法 `description` 值含换行、`"1.2"` 和 `C:\app` 时，`json.dumps(value)` 把真实换行/引号/反斜线改成 JSON 转义表示。结果状态为 parsed，但按原始解码值定位整个引文会抛 `ValueError`。独立探针 `json_original_unicode_value_quote` 两次复现；不涉及金标。
   - Fix：字符串叶直接保存已解码值，路径保留在既有 `field:` 定位信息；数字/布尔/空值仍使用确定性表示。补换行、引号、反斜线和 emoji 的整体引文 roundtrip；不重写 json1 历史 revision。
   - If we skip it：结构化公告中含这些字符的原文值无法建立真实引文，违反 CR 的“原始Unicode值”和 W02 字段证据定位要求。
   - 复验要求：同一独立输入必须为 parsed，whole-value 引文精确回切、UTF-8 hash 可计算；旧 revision 的已保存文本/偏移不变。

2. **孤立代理码点被当成成功文本，后续 UTF-8 链直接失败**（`parsers.py:106–117,129–141`；下游 `knowledge/evidence.py:36`、`knowledge/revisions.py:187`，P2，确证）。

   - What this is：JSON 原始字节通过 UTF-8 解码后，还允许 JSON 的 `\u` 转义生成无法 UTF-8 编码的 Python 字符串。
   - Problem：实际输入 `b'{"description":"\\ud800"}'` 返回 parsed；其 `normalized_text.encode("utf-8")` 抛 `UnicodeEncodeError`。严格初始 byte decode 没有校验解码后的键和值；当前 catch 只含 UnicodeDecodeError。
   - Fix：JSON 键和字符串值在输出前严格验证 UTF-8 可编码，拒绝孤立高/低代理码点，按既有 unparseable/invalid json 失败；合法代理对/emoji 仍应通过。同步检查不能进入 PG 文本的 NUL 字符。
   - If we skip it：解析成功记录不能被规范文本 hash/证据 hash 或 PG 文本存储消费。此处确证的是内存输出和 UTF-8 编码失败；产品解析尚未装配，未声称已经复现线上数据库故障。
   - 复验要求：键与值的孤立代理/NUL 都应明确拒绝，合法 emoji、普通中英文和原始字符串定位不受损。

## Should fix / 验证缺口

3. **纯 unit 的实际覆盖率低于原 60%，不能用 unit+contract 的 61.10% 代替**（`backend/pyproject.toml:63–65`、`.github/workflows/ci.yml:81–82`，确证数值缺口）。

   - What this is：CI 用 `scripts/dev.py check --scope unit`，与把 T09 contract 加入同一 coverage 会话不同。
   - Problem：独立 pure unit 和真实 dev 入口都为 248 passed，coverage 为 **59.98%**。两命令实际 exit 均为 **0**，日志同时打印 `FAIL Required test coverage of 60% not reached`；不伪写成 exit1。锁定 pytest-cov 的结束检查按 coverage 默认 precision=0 四舍五入，但 summary 比较原值，解释了 exit0/FAIL 同时出现。
   - Fix：补 PDF IPC 错误输出、超时、清理等必要可观察行为 unit，使纯 unit 本身达到既有数值门；保留阈值、分母和原案例。不靠增入合同测试、放宽阈值或 skip。
   - If we skip it：数值门未满足却被 scope 结果当绿灯，报告中“unit passed”会掩盖精确覆盖率缺口。本条不把依赖的显示/rounding 差异误报为新业务 bug。
   - 复验要求：原 dev unit 命令与 pure unit 都显示实际 coverage≥60，无 FAIL 门限信息，计数/exit 如实记录。

## 独立命令与结果

下表中时间均为 2026-10-15、+08:00，含秒。完整命令不靠表中缩写复现，而以各收据 argv 为准；测试数不把探针或静态检查混算成 pytest。

| 收据 / 实际命令概要 | 开始–结束 | exit | 真实结果 |
|---|---|---:|---|
| `sync_locked`：backend `uv sync --locked` | 12:22:49–12:22:54 | 0 | 新 WT 独立 venv，68 packages，pypdf6.20.1 |
| `full_unit_t09`：`uv run --locked pytest tests/unit tests/contract/test_t09_document_parsing.py -v --junitxml=…` | 12:23:13–12:23:40 | 0 | 255 passed、0 fail/skip、1既有弃用 warning；cov61.10%，原60门 |
| `static_ruff`：`ruff check src` + 两解析测试文件 | 12:23:13–12:23:14 | 0 | all checks passed |
| `static_format`：parsing/ + 两解析测试 `ruff format --check` | 12:23:14–12:23:14 | 0 | 7 files formatted |
| `static_mypy`：backend `mypy src` | 12:23:13–12:23:23 | 0 | 64源码文件无问题 |
| `official_pdfinfo_2` / `official_render` | 12:24:59–12:24:59 / 12:24:33–12:24:34 | 0/0 | 官方PDF4页、非加密、260044bytes；四页PNG均实际视觉检查 |
| `independent_probe` | 12:27:06–12:27:11 | 1 | 28自主断言：25pass/3fail，其中1为审查探针标题空格预期错误、2为上文JSON确证 |
| `independent_probe_2` | 12:29:40–12:29:45 | 1 | 保留首轮；更正第3页仅取实际标题文字，26pass/2fail，剩余均JSON确证 |
| `process_boundaries` | 12:28:09–12:28:31 | 0 | 8自主行为检查全通过；真实20.015s timeout、kill/reap、释放容量、协议错误、限额不可用fail closed |
| `large_inputs` | 12:30:23–12:30:24 | 1 | 百万字实际限额与JSON32MiB边界通过；压缩流探针缺Font资源导致未进入解码，属审查输入错误 |
| `large_stream_corrected` | 12:31:27–12:31:28 | 0 | 保留上述失败；补真实Font资源后9MiB解码流明确text extraction failed/unparseable |
| `pure_unit_original_gate` | 12:29:40–12:30:01 | 0 | 248passed/0skip，cov59.98，数值不足原60 |
| `dev_unit_original_2`：真实 `dev.py check --scope unit --timeout-seconds 600` | 12:31:52–12:32:10 | 0 | scope输出tests248/failed0/errors0/skipped0/tool_exit0；cov59.98/FAIL信息保留 |
| `manifest_validation`：`scripts/verify_plan.py` | 12:28:09–12:28:10 | 0 | PLAN_OK，仅结构校验 |
| `credential_shape_scan`：`scripts/security_scan.py --repository-root [独立WT]` | 12:28:09–12:28:12 | 0 | 19已登记历史synthetic形态，无未分类项；exact_scan=not_run，无真实秘密值可比对 |
| `source_callers` / `diff_check` | 12:28:49–12:28:49 | 0/0 | rg调用链交叉 / 无空白错误 |
| `linux_host_environment` | 12:29:40–12:29:40 | 0 | WSL宿主Python3.10.12、pypdf未安装；不是冻结项目的3.12运行环境 |
| `evidence_index` | 12:32:36–12:32:37 | 0 | SHA/tree/hash收据绑定，WT status为空，自有报告日志形态扫描0；actual exact scan未运行 |

仪器错误全部保留、不当产品缺陷：首次 `cli help` 实际unknown tool exit1，后按CLI `--help`、各tool `--help`成功；首次pdfinfo底层exit0，审查runner打印GBK替代字符触发UnicodeEncodeError后wrapper exit1，改为UTF-8并另名复跑；`dev.py test` 参数错误底层exit2后按已读CLI更正为check。初始化复合PowerShell的一次未引号 `^{tree}` 和不存在 `blocks.py/jobs` 路径/通配查询错误仅在tool原始记录，后续明确引号/实际text_blocks/workers路径纠正；这些早期读命令没有独立起止收据，未重建或编造它们。

## 已确证的 PDF 与兼容证据

- 官方四页实际 parsed、页号 `[1,2,3,4]`、3882字符；分别定位到页1赛题名 `[35,58)`、页2“六、评价指标” `[1060,1066)`、页3“线下决赛” `[2697,2701)`、页4“八、参赛平台” `[3844,3850)`，均从规范文本精确回切。0.485/0.578秒只为单次解析诊断，不是问答/性能/连续运行指标。
- 真实独立合成空页、零页、加密、混合1/空2/3、301页、损坏、假TEXTLAYER均没有伪造parsed全文。混合保留页1/3并列第2页缺口；加密明确要求授权解密。
- actual1,029,000字符输入（21页×49,000）在固定100万阈值下返回partial、20块/980000字、`pdf text limit exceeded`。实际9MiB解压stream在8MiB限制下拒绝文本抽取；PDF32MiB+、JSON32MiB+、JSON33层和10001叶均受控拒绝。
- Windows本机 `_bound_memory()` 的真实独立子进程32MiB分配成功，600MiB分配MemoryError；返回Job handle存在。不是仅mock flag或依赖作者结果。Native两worker同时存活时第三请求拒绝；两子进程均回收；合成环境秘密marker未继承。
- 父超时路径用审查者自己固定的sleep子进程实际等20秒，确认kill/reap及信号量释放；非零exit、非JSON/错结构/页号0都返回固定错误。限额不可用以独立子进程明确模拟OSError，输出固定failure；没有把平台mock当真实OS限额。
- synthetic image-only fixture fresh checkout字节与Git blob完全一致：657bytes，SHA256 `e8bacebdfd08c04860e1d143dd3b36bddb7f04ac6908109eac7249cbc592cb6a`，strict pypdf读取1页/1×1 Image，startxref=482。`.gitattributes`新增仅该确切PDF `-text -diff`。C04 caseID和拒绝无文本语义保留，非gold/holdout改动。
- 无新增schema/迁移；text_blocks、normalizer1、既有evidence与历史读取模块在基线diff中未改。parser版本pdf2/json2明确，不能据此声称已验证真实PG中升级前后的旧PDF/JSON revision。

## CBM 与真实调用链

CBM v0.11.0，由同一 `wsl -u root`、独立cache `/tmp/dianzi-cbm-r04-parsing-review-1-20261015`、allowed root仅上述WT `backend/src`执行。`--persistence false`，索引不落仓、无秘密/holdout/runs纳入。`cbm_index` 12:24:33–12:24:38 exit0：64Python文件、812nodes/3576edges、0partial/unusable/skipped。`cbm_architecture`、`cbm_schema`、`cbm_pdf_trace`、`cbm_json_trace` 于12:25:33–12:25:40均exit0。

图中两个入口callers_total均为0；`rg backend/src`证实只有parsing模块定义/导入和构建块，没有API或来源worker调用。这是图与源码交叉结论，不仅凭“图没边”。独立单元直接调用能证明解析器能力，**不能证明真实来源→保存raw→解析revision/页路径→API→浏览器闭环**。现有PG `add_text_block`并没有本切片的page/path装配证据；报告自身也准确承认待后续，本审不把这点改写成整卡通过。

## 不通过、未检查与有限结论

确证需要修复：问题1、2；问题3的实际数值门需要补必要unit后复验。官方4页解析、fixture原字节、Windows硬内存、父进程墙钟/回收、JSON重复键/非有限/深度/路径边界得到独立支持。未发现需要额外架构层或删除成熟PDF库的理由；固定小进程和本机Job/RLIMIT实现有实际安全用途，不作主观复杂度扣分。

未测：Linux生产Python3.12/pypdf worker的512MiB地址空间、15CPU秒和实际容器路径；宿主仅Python3.10且无库，没有擅自安装或放宽限额。未测真实PG历史PDF/JSON引用、持久page/path、parser任务装配、API浏览器e2e、真实两源采集/live、表格布局语义、OCR、第三方扫描与实际秘密精确比对。原T09-C05现有测试只是HTML同版本重跑，不能代表跨pdf1/json1→pdf2/json2持久历史验收。manual仅四页视觉检查，不等于业务人工验收。

合同与计划偏差：本次允许成熟pypdf、保持normalizer1和原C04语义，未变阈值/分母/skip/金标；数值coverage与scope exit事实分别列明。F1/F2/F3/R1本轮只获得解析和内存定位证据，不登记整评分项优秀；R04/T09/G-B仍待来源、持久化、页面和最终前置/切片要求。

下一任务建议：作者对1/2做最小修复并补unit，冻结新SHA后由本非作者定向复核；随后再接真实来源解析/持久页路径与API链。旧f2所有失败日志/报告保留。

Verdict: fix 1 and 2 first; verify the original pure-unit coverage requirement. Not checked: 上述Linux生产限额与产品闭环、历史数据库、live和实际秘密精确比对。

## 48ad907 定向复核附录

复核写作开始：2026-10-15T12:40:02+08:00；复核写作结束/最后更新时间：2026-10-15T12:41:17+08:00。本附录为新固定提交上的独立意见，不覆盖f2初审结果。

- 新被审SHA：`48ad907218155481d7d7fd16261a6a555559f4a8`；tree `a756999642570ec2d1a1eaa0d26d188b0e831a9d`；backend/src tree `09c1f08a2a7e97a432e6da46d357dc38fba42c86`。
- 第二个干净WT：`C:/Users/yinha/.codex/worktrees/recovery-r04-parsing-review-recheck/dianzi`，branch `codex/recovery-r04-parsing-review-recheck`。新独立venv sync成功；业务/锁/合同/状态未改、无push。未使用root可变网络文件当通过证据。
- 定向业务差异仅为JSON键和值的UTF-8/NUL验证、字符串叶直接保留原始值、异常捕获UnicodeError、相应Unicode与PDF IPC unit。阈值/分母/原T09案例/normalizer1未变；json2此前为待验收实现，未拿新结果覆盖已保存历史。
- 48ad整树另包含R03网络/0012迁移等独立切片；本报告**不审签这些实现/迁移**。仅运行固定树共同unit作为真实回归。其SQL拆字串、schema/网络live等不能由本解析结论背书。
- 8个文件的Git blob双提交相同，见 `evidence_index_recheck48ad.json`：`_pdf_worker.py`、`pdf_text.py`、`text_blocks.py`、`knowledge/evidence.py`、pyproject、uv.lock、image-only fixture、官方PDF。因此初审的实际PDF百万字/压缩流/Windows512MiB/父20s/并发2/清理证据继续只适用于这些相同实现，本轮没有无新变化地重复完整资源压力实验。

| 新收据/实际检查 | +08:00开始–结束 | exit | 结果 |
|---|---|---:|---|
| `recheck48ad_sync`：backend `uv sync --locked` | 12:35:52–12:35:56 | 0 | 新WT68包/pypdf6.20.1 |
| `recheck48ad_json`：独立新探针 | 12:36:47–12:36:47 | 0 | **17/17**：原完整换行/引号/反斜线/emoji值精确回切与hash、非BMP字段RFC6901、合法代理对、重复词歧义及指定出现区间；高低孤立代理键/值、NUL键/值、嵌套无效字符串、转义重复键、NaN/溢出均拒绝 |
| `recheck48ad_pure_unit`：`uv run --locked pytest tests/unit --junitxml=…` | 12:36:47–12:37:12 | 0 | **268 passed**，0fail/errors/skip、1既有warning；coverage61.42%，原60门 |
| `recheck48ad_dev_unit`：真实 `dev.py check --scope unit --timeout-seconds 600` | 12:37:51–12:38:10 | 0 | scope tests268/failed0/errors0/skipped0/tool_exit0，coverage61.42%，无FAIL门信息 |
| `recheck48ad_coverage_raw_export`：`coverage json -o …` | 12:38:35–12:38:36 | 0 | 实际2326/3787行，**未舍入61.42064959070505%≥60**；不是凭exit0/显示rounding通过 |
| `recheck48ad_t09`：原T09文件 `-v --no-cov` | 12:37:25–12:37:27 | 0 | 7/7原合同，包括C01–C06；本次只是独立合同回归，未用其提高pure unit覆盖值 |
| `recheck48ad_ruff` / `recheck48ad_format` / `recheck48ad_mypy` | 12:36:47–12:36:48 / 12:36:47–12:36:47 / 12:36:47–12:36:57 | 0/0/0 | src+解析unit Ruff0、6格式文件通过、64源码类型0 |
| `recheck48ad_manifest` / `recheck48ad_shape_scan` / `recheck48ad_diff_check` | 12:37:51–12:37:51 / 12:37:51–12:37:54 / 12:37:51–12:37:51 | 0/0/0 | PLAN_OK；19历史synthetic已分类/exact_scan未跑；diff空白0 |
| `recheck48ad_cbm_index` / `recheck48ad_cbm_json_trace` / `recheck48ad_source_callers` / `recheck48ad_cbm_architecture` | 12:35:52–12:35:57 / 12:37:25–12:37:28 / 12:37:25–12:37:25 / 12:39:59–12:40:02 | 0/0/0/0 | 新独立索引64文件/813nodes/3584edges/0partial；JSON0业务callers仍由rg交叉，架构重新核对 |
| `recheck48ad_evidence_index` | 12:39:32–12:39:33 | 0 | 新SHA/tree/blob比较、raw coverage、收据绑定，WT status空；自有日志形态扫描0，实际秘密exact仍未跑 |

新增PDF IPC unit用明确ChildFixture测试损坏协议和超时调用顺序；它们是必要纯函数/进程接口回归，并非实际native进程的新性能数据。真实native超时、双worker和硬内存实测保留在f2初审，PDF资源源文件相同。新Unicode探针独立构造输入，没有引用实现输出做expected。

原问题1闭合：完整23字符Unicode值在json2规范文本 `[14,37)` 精确回切，独立SHA256一致；原值字符不再被JSON二次转义。原问题2闭合：键/值非法代理和NUL明确unparseable，合法emoji代理对与UTF-8无损通过。原问题3当前数值缺口闭合：两个实际纯unit入口均268pass，raw61.42064959070505严格超过原60，不再依靠舍入。

pytest-cov的raw summary与precision=0退出判定差异仍是工具未来严格门保障问题，建议R20整改并保留f2反例；**当前48ad的raw已达门，本遗留不再阻断当前解析组件技术复核**。不得据此称工具已改或f2覆盖通过。

CBM新cache `/tmp/dianzi-cbm-r04-parsing-recheck48ad-20261015`，allowed root仅第二WT backend/src，project `dianzi-r04-parsing-recheck48ad`，同WSL root/不持久仓内。原evidence_index和所有f2失败输出未覆盖；新原始coverage JSON含空字符串字段名，审查者首次PowerShell ConvertFrom-Json读取失败后用`-AsHashtable`读取成功，属于审查仪器边界，无产品修改。

复核有限结论：**JSON缺陷及当前数值门关闭，解析组件可继续集成；本review的代码级技术检查passed。** Linux生产3.12 worker限额、PG历史/持久页路径、parse任务/API/真实两源/浏览器闭环/业务人工验收/实际秘密精确比对仍为not_run/待后续，不接受整R04、R04:T09全部验收、整T09或G-B。未签R03网络/0012迁移。下一步将此解析器接入受控来源保存与永久revision证据路径，并补独立集成/生产限额证据。

Verdict for the reviewed parsing component at 48ad907: Ship to the next integration step. Not checked: Linux production limits and the full persistent/live/API/browser path described above.
