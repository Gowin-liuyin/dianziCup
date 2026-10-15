# R06-A · arXiv Atom 与 Trail of Bits RSS 内部解析切片

文档首次创建时间：2026-10-15T18:30:02+08:00
本次写作开始时间：2026-10-15T19:25:13+08:00
本次写作结束时间：2026-10-15T19:25:14+08:00
最后更新时间：2026-10-15T19:25:14+08:00
本报告证据截止时间：2026-10-15T18:30:03+08:00
实际工作活动开始：2026-10-15T18:04:33+08:00；纯编码起止历史未单独记录，不推算编码时长。
负责人：`/root/r06_feed_parsers`。
阶段：G-C 内部独立准备；G-B/G-C 阶段门本报告不作判断。
任务状态：awaiting_review；本工作包实现 complete；整张 R06/T12/T14 仍是 partial。
分支：`codex/r06-feed-parsers`；工作目录：`D:/wt/r06-feeds`。
基线：`7ed73540c001a4e7f5b5fa5dc2948c4b4635590f`。
已测代码冻结 SHA：`b1ff04a267babda5d57506d6e1e39006a2e4bb34`；src tree：`ef125130ebe25940844856413444eb3f39a3b8ef`。
独立审查：尚未运行，由主控派新的审查 Agent；不签 accepted；无 push。

## 1. 目标、合同与实际范围

读取 AGENTS、execution map、R06、T12/T14 卡、03/04/05/06/07 合同、progress 状态/交接及来源准备草案。既有 academic/feed 只接收预整形 dict，无法解析真实 XML，academic 缺 version 会默认为 v1。本包按主控冻结接口新增 `parse_arxiv_atom(bytes) -> ArxivDiscoveryPage` 与 `parse_trailofbits_rss(bytes) -> tuple[FeedEntry,...]`，复用原归一函数而不改默认行为；新 adapter 必须显式解析版本，缺版本整页失败。

没有改公共 schema、枚举、配置、迁移、锁、全局入口或进度。未接 API/worker/PG/UI；不把函数或留档回放当来源 live 接通。R06 来源八类、持续采集、断点事务、独立漏采参考集和时效仍待主控接线/验收。对应能力是 R06:T12/T14 的解析部分；T12-C01 的持久化证据、真实增量周期与 T14 的 PDF 部分未由本包完成。

## 2. 实现与复用

四个业务/测试文件：

- `backend/src/ai_intel/ingestion/sources/arxiv_atom.py`
- `backend/src/ai_intel/ingestion/sources/trailofbits_rss.py`
- `backend/tests/unit/test_r06_feed_parsers.py`
- `backend/tests/contract/test_r06_archived_feed_replay.py`

复用 `AcademicRecord`、`normalize_academic_record`、`FeedEntry`、`normalize_feed_entry`，保留既有 canonical URI 的跟踪参数过滤/内容参数及稳定 ID 规则。使用标准库 ElementTree、datetime/email.utils、dataclasses，不增依赖、包装框架、状态库或后台进程。两源的有界 TreeBuilder 使用各自的合同异常；未新增跨源共享公共接口。

arXiv 原论文 ID 形成 `arxiv:2609.05903`，明确 v1/v2 归同实体不同版本；历史同域 http 标识/PDF/alternate 映射 https，原值由调用方持久化的原字节保留。标题/作者/摘要/原始 UTC Z 时间保留；published 与 updated 分开，缺值 None，未来时间原样保留供采集指标单列；updated 早于 published 是冲突，整页失败。只存全文链接，`full_text_fetched=False`/`metadata_only`。只有 arxiv:comment 明确撤回陈述前缀可置 withdrawn=True；标题关键词、研究讨论、404 均不推断。False 表示未解析到明确通知，**不证明未撤回或当前可用**。

RSS GUID 不参与 canonical URI 的稳定 ID；pubDate 必须含显式时区，转换 UTC，原 RFC822 字面值仍在原始 XML/摘录。channel lastBuildDate 不填文章 modified。description 原字符串保留且所有条目加 `article_body` 缺失标记；缺 description 另保留 body missing。description 可含 HTML，**调用方不得直接渲染或当已抓文章全文**。同 URI 的下一次内容变动有新 hash、相同 ID；单页重复 ID/嵌套或错误命名空间条目明确失败，不吞掉。

## 3. 边界、安全与主控补冻结

两源各最多 2097152 bytes、1000 条、10000 XML 节点、深度32；任一限制超出整页失败，没有静默截断。只收 UTF-8（可带 UTF-8 BOM），拒绝 DTD、实体声明、未知实体、畸形 XML、其他声明编码、xml:base 和超深/超量节点。XMLParser 的 doctype callback 在内容展开前拒绝声明，不使用字符串移除 DTD。XML 内置 `&amp;`/`&lt;` 与文字里的 DOCTYPE 不当作外部实体。

输出抓取 URI 与 RSS/Atom id/link/GUID URL 只允许各固定官方源域；不允许 userinfo、非预期端口、控制字符、空白、反斜线、越域或跨论文版本 PDF/alternate。不联网、不解引用外部正文/PoC。

主控于本包期间补冻结：许可是元数据 identifier，不是抓取/再分发授权。CC BY `https://creativecommons.org/licenses/by/4.0/`、CC0 `https://creativecommons.org/publicdomain/zero/1.0/`、arXiv 官方许可标识按原值保留；未知普通许可文本、安全未知 http/https URI 也仅作为**未核实原文 identifier**保留，不自动成为可链接或许可已确认事实。危险 scheme/userinfo/控制字符 URI 拒绝；包括合法标识在内均不解引用（对应测试封禁 socket）。现有 AcademicRecord 没有许可核实状态，调用方不得自动链接未知 URI 或据此授权全文再分发；全文抓取链接仍限 arxiv.org https。此补充来自主控消息，本作者未自行放宽网关/许可。

security 层只有纯 XML/URI/限额负例得到证明；完整后端 security、租户、事务、重启、浏览器、外部网关 DNS/重定向在本包均 not_run。

## 4. 原始样本、许可与可推送内容

arXiv 原始 Atom 6101 bytes，sha256 `8fd7cd6d0f71f5540d099047a778e813d67b1392a21e7c089bd49bc80a6bb3f1`，来源准备记为 CC0 metadata；含2篇，未获取论文 PDF。公开包包含该元数据响应、原来源请求 metadata，不能把元数据许可扩展到 PDF。

Trail of Bits 完整 RSS 991606 bytes，sha256 `86a1faac2d08bd01281efcb72ebb6c57a9a4213aa61ebf055b77ceb093e476f0`，再分发许可 unknown。完整副本保留在 `D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-feed-replay/20261015/doh_05_trailofbits_feed.body`，原 `C:/Users/yinha/.codex/worktrees/r06-src/dianzi/reports/runs/recovery_r06_source_preparation_20261015/doh_05_trailofbits_feed.body` 不动；**完整 description 未进入本包可推送 commit**。

可推送的是明确标记的 `trailofbits_metadata_excerpt.xml`，6597 bytes、sha256 `ce9b990828a06b85bf17924f97b2c8ee769eb69e7710d177f5a82f2ea3719b2f`：原20项的 title/link/pubDate/guid 事实字段，仅首项9词必要短引文，其他 description 不存在；它是人工规则生成的元数据摘录，**不是原响应**。复杂/恶意 XML 是显式 synthetic unit fixtures。公开 metadata、storage/import receipt 只留原样本路径、hash、许可状态/模式，不含完整未知许可正文。私有完整20条回放见 `full_private_replay.*`，8个断言、零新 HTTP、零正文/PDF抓取；fixture/replay 都不计 live 来源数或时效分母。

## 5. 验证与失败保留

所有日志/JSON/JUnit 在 `reports/runs/recovery_r06_feed_parsers_20261015/`；每个 JSON 记录真实 argv、cwd、起止 +08:00、退出码和当时 HEAD。运行时工作树四个代码/测试文件与冻结 commit 字节相同，见 `code_snapshot.json`。pytest 使用 backend pyproject 原 `--cov-fail-under=60`；未覆盖/放宽分母、门槛或金标。

| 命令标签 | 开始 / 结束（Asia/Shanghai） | 退出码 | 实际计数（JUnit） | 原始日志 |
|---|---|---|---|---|
| parser_red | 2026-10-15T18:09:00+08:00 / 2026-10-15T18:09:06+08:00 | 2 | {'tests': 1, 'failures': 0, 'errors': 1, 'skipped': 0} | `parser_red.log` |
| targeted_green | 2026-10-15T18:11:10+08:00 / 2026-10-15T18:11:13+08:00 | 1 | {'tests': 76, 'failures': 0, 'errors': 8, 'skipped': 0} | `targeted_green.log.gz (lossless; original retained privately in worktree)` |
| unit_contract_1 | 2026-10-15T18:12:38+08:00 / 2026-10-15T18:12:51+08:00 | 2 | {'tests': 1, 'failures': 0, 'errors': 1, 'skipped': 0} | `unit_contract_1.log` |
| unit_contract_2 | 2026-10-15T18:14:01+08:00 / 2026-10-15T18:14:35+08:00 | 0 | {'tests': 1085, 'failures': 0, 'errors': 0, 'skipped': 0} | `unit_contract_2.log` |
| unit_contract_final | 2026-10-15T18:17:50+08:00 / 2026-10-15T18:18:25+08:00 | 0 | {'tests': 1100, 'failures': 0, 'errors': 0, 'skipped': 0} | `unit_contract_final.log` |
| unit_final | 2026-10-15T18:19:54+08:00 / 2026-10-15T18:20:31+08:00 | 1 | {'tests': 1086, 'failures': 1, 'errors': 0, 'skipped': 0} | `unit_final.log` |
| full_private_replay | 2026-10-15T18:23:06+08:00 / 2026-10-15T18:23:06+08:00 | 0 | not a pytest command | `full_private_replay.log` |
| unit_contract_packaged | 2026-10-15T18:23:07+08:00 / 2026-10-15T18:23:39+08:00 | 0 | {'tests': 1100, 'failures': 0, 'errors': 0, 'skipped': 0} | `unit_contract_packaged.log` |
| unit_recheck | 2026-10-15T18:23:57+08:00 / 2026-10-15T18:24:29+08:00 | 0 | {'tests': 1086, 'failures': 0, 'errors': 0, 'skipped': 0} | `unit_recheck.log` |
| mypy_final | 2026-10-15T18:18:33+08:00 / 2026-10-15T18:18:34+08:00 | 0 | not a pytest command | `mypy_final.log` |
| static_packaged | 2026-10-15T18:24:29+08:00 / 2026-10-15T18:24:29+08:00 | 0 | not a pytest command | `static_packaged.log` |
| format_packaged | 2026-10-15T18:24:29+08:00 / 2026-10-15T18:24:29+08:00 | 0 | not a pytest command | `format_packaged.log` |
| evidence_ruff | 2026-10-15T18:27:04+08:00 / 2026-10-15T18:27:04+08:00 | 0 | not a pytest command | `evidence_ruff.log` |

当前 pure unit：1086 passed、0 failed/error/skip，覆盖68.03%（6813 statements/2178 missed）；当前 packaged unit+相关合同：1100 passed、0 failed/error/skip，覆盖68.28%。包括79个新增 unit、2个新 contract、原T12/T14共12个 contract。全 src mypy84文件、全 backend Ruff、208文件格式检查通过。私有完整原响应的回放独立于公开摘录，结果不混称新 live。

验证状态：unit=passed；contract=passed；security=passed（仅本包纯解析负例）；integration/frontend/e2e/live/manual=not_run。上述状态不替代整张R06或阶段验收。

已保留问题：

| 问题 | 输入/预期/实际 | 根因或证据 | 修复与复验 | 当前状态 |
|---|---|---|---|---|
| R06-A-01 | 新 parser import 应可用；先写测试时模块不存在 | parser_red collected0/import error，退出2 | 新增两个模块后目标用例可执行 | 已修复，待独立核对 |
| R06-A-02 | 超节点/字节样本应检查拒绝；pytest默认 ID 达数MiB | Windows pytest CURRENT_TEST 环境变量超过32767字符；8个 setup/teardown错误事件，非业务成功 | 参数化案例用短 ID；后续相同负例通过；原17.4MiB log与4.5MiB XML保留为lossless gzip，原文件也留在WT，不删除 | 已修复，待独立核对 |
| R06-A-03 | unit+contract共同收集应无冲突 | 同 basename test_r06_feed_parsers 导入碰撞；unit_contract_1退出2 | contract更名test_r06_archived_feed_replay；完整运行通过 | 已修复，待独立核对 |
| R06-A-04 | typed URI 应与 Element分开 | RSS Atom link循环变量复用引起mypy两处类型错误 | 更名atom_link；84 src mypy通过，没有 cast/Any/ignore | 已修复，待独立核对 |
| R06-A-05 | 原R05 CPU_seconds=1忙子进程应在原测试8s内退出 | unit_final 首次1085 pass/1 failure；TimeoutExpired，根因未确证，未归咎本parser | 无共享代码/测试修改；同参数有限完整pure unit复跑1086全通过；失败日志保留供主控/独立review复查宿主敏感性 | 未确证根因，后续复查；不写成永久修复 |
| R06-A-06 | 未知许可完整RSS不得公开打包 | 原991606B含完整description，许可unknown | 保留仓外副本/原source-prep；公开包为6597B明确metadata-only摘录；完整原件hash核对+20项回放通过 | 公开打包限制落实，许可仍unknown |

targeted_green 原输出有72个collected用例，68个call通过及8个setup/teardown错误事件；JUnit共76条报告事件，不把它当72/72通过。原日志/计数不修绿。一次原有FastAPI/Starlette弃用警告保留，未增加依赖替换或全局忽略。

## 6. 调用链、索引与未接线

官方 portable CBM v0.11.0；WT独立缓存 `/tmp/dianzi-cbm-r06-feed-parsers-20261015`；范围仅 `backend/src`。基线1085 nodes/5218 edges，冻结代码内容索引1125 nodes/5390 edges，not_indexed/partial/unusable=0。get_graph_schema、get_architecture、前后trace原文留档。源码rg交叉核对：基线normalizer无产品callers；现在各由新pure parser调用，而两parser仍仅由本包tests/private replay调用。tests不在该src-only图内，不能把include-tests参数说成索引了测试；测试调用由rg/实际运行确认。

新链路是 `bytes -> bounded XML -> official source fields -> existing normalize -> immutable DTO`；没有数据库/外部IO/模型副作用。`SourceKind`、source_jobs/source_documents、默认app/API、worker、UI均未引用新parser，这属于派发允许的独立内部切片，不属于真实接通。主控后续必须统一来源注册、非漏洞知识实体原文/证据持久化、时间精度/未来值、增量/回补和相应浏览器入口后才能验收R06。

## 7. 六组必要案例与原T映射

正常：原Atom2篇、私有完整RSS20项、公开20项metadata摘录；缺失/冲突：版本必需、时间None/naive/非法/先后冲突、作者与重复字段；分页：total/start/itemsPerPage、空页/最后页/超限/重复/嵌套；身份与修订：v1/v2同paper、旧式arXiv ID、GUID变化/跟踪query/内容hash；安全：DTD/实体/非法编码/超节点/深度/字节/恶意URI/xml:base/许可URI；回放：hash核实、原响应与摘录模式明确分开。

这些只支撑T12-C02/C05/C06和T14-C01/C02/C03/C04的解析层，以及R06-C01/C02/C04的内部部分。T12真实版本持久化/正文/增量、T14全文PDF质量、R06重启/回补/漏采参考/八类真实来源/采集时效没有本包证据，不签原T整卡或评分达标。

## 8. 限制、移交与停止条件

当前支持上述固定公开来源UTF-8形态；XML节点上限与条目上限共同生效，大页会明确失败要求缩小请求，不会截断。Atom UTC只接受官方秒精度Z；RSS文章modified保持未知，后续靠正式正文hash与来源明确修订而非feed build时间。重复同版本/同canonical整页失败以避免隐藏冲突，需要采集层隔离留存而非静默丢记录。许可安全URI是文本标识，不能自动链接/推断授权。撤回通知未命中不等于未撤回。

交付一个可合并内部解析批次；主控负责新独立review、集成、共享配置/schema、private原件保管与阶段状态/Git push。没有替换mock、内存DB或静态展示来冒充真实能力，没有修改用户原有文件。后续第一步为冻结本代码+摘录+证据的候选版本，由未参与实现者复跑，然后按主控小合同接入真实PG采集链。

## 9. 文档修订记录

2026-10-15T18:30:03+08:00：首次落盘；记录真实失败、复跑、严格边界、许可补冻结、仓外原件与公开metadata摘录、未接线范围。修订人 `/root/r06_feed_parsers`。阶段结论、独立审查结论与push尚未发生。


### 2026-10-15T18:34:06+08:00 · 原字节封存修正

R06-A-07：封存核对发现 Git 默认将生成 JSON/Markdown CRLF 转为 LF，旧候选 8bb8bd56f92dff266b326aa634b425a2a617fe6b 的 manifest 与 47 个 Git blob 原字节 hash 不一致。验证非零后本调用中的后续 PowerShell native 命令仍执行，故该本地 docs commit 被保留为历史失败候选，不代表 hash 检查通过。业务代码、原 .body/XML、用例行为没有变化，也没有改写旧记录的时间/结果。

修正只在本 run 的 .gitattributes 增加 *.json -text/-diff（与 log/XML/body 同样保持原证据字节），任务报告明确保存 LF；显式 owned files 重登暂存并逐 blob 核对，最终以新候选与修正收据为准。既有失败候选不推送/验收。首次创建时间不改；完整源码测试结果不拿来为改变行为的代码背书。


## 修复轮1 · 独立初审三类 Must

本轮写作开始：2026-10-15T19:04:18+08:00；结束/证据截止：2026-10-15T19:04:18+08:00；首次创建时间保持不变。
作者状态 awaiting_review；三类问题已修复待原独立reviewer定向复核，不签accepted。
独立初审报告：`D:/dianzi/reports/reviews/recovery/G-C-R06-feed-parsers-review-1.md`，原固定8e4候选，结论needs_changes。
本轮代码冻结：`6b7dd7e881bb822e83b55f8302f7aefe565f4940`；src tree `15b19b26f68838fcb62c362f0b7370fc311a1b7b`。本轮4文件与冻结blob字节一致，证据 `fix1_code_snapshot.json`；旧b1ff/8e4结论与记录只对应各自历史版本。

### 确认问题、共同根因与修复

- R06-A-R1-01：total=100/start=0/items=10但仅1entry原来正常返回，遗漏位置1–9可能被后续caller跨过；当前没有产品caller，未声称实际漏采事故。现有范围校验后新增 `len(entries) < min(size,total-start)` 明确失败；保留正常空页、完整页与最终不足一页。新增3种不足页负例；原末页/真实2项Atom继续通过。
- R06-A-R1-02：RSS +1260被stdlib宽松折合+13小时形成确定UTC。先识别时间字段后紧随的数字zone，检查小时≤23/分钟≤59，再复用原stdlib日历/时区换算；不另写日期框架。覆盖正负非法偏移和合法+0000/-0400/+0059/-0001/+2359/GMT；合法 `-0400 (source reference +1260)` 注释不误当时区。缺时间/naive/未来值、Atom UTC-Z检查保持既有语义。
- R06-A-R1-03：原C0检查漏DEL U+007F，RSS输出link及许可原文可含DEL。对arXiv官方URI、许可identifier和RSS官方URI三个既有入口补DEL拒绝，覆盖feed id、entry/PDF、channel/article/GUID、普通许可文本及URI。没有把安全未知许可变成授权，也不改原文/全文状态。PDF/entry原来还受版本/path检查，补共享URI入口以统一边界。

23个新增unit加上原79个作者unit；原47独立例文件未编辑，当前sha256 `65b809db3152f99fdcc16dd7b2cff4fdbaaa050cc9ab57a21166c4425976e3fd`。原红仍在reviewer初审证据中，本作者另复现17红（独立4 + 新同根因13），未改红例期望/阈值/分母/skip。

### 实际执行与失败保留

| 标签 | 开始 / 结束（Asia/Shanghai） | exit | 原始JUnit事件数 | 参数/日志 |
|---|---|---|---|---|
| fix1_red_combined | 2026-10-15T18:56:03+08:00 / 2026-10-15T18:56:34+08:00 | 1 | tests=1170, failures=17, errors=0, skipped=0 | `fix1_red_combined.json/.log` |
| fix1_green_combined | 2026-10-15T18:57:16+08:00 / 2026-10-15T18:57:51+08:00 | 1 | tests=1170, failures=1, errors=0, skipped=0 | `fix1_green_combined.json/.log` |
| fix1_unit | 2026-10-15T18:59:04+08:00 / 2026-10-15T18:59:36+08:00 | 0 | tests=1109, failures=0, errors=0, skipped=0 | `fix1_unit.json/.log` |
| fix1_combined_recheck | 2026-10-15T19:00:11+08:00 / 2026-10-15T19:00:46+08:00 | 0 | tests=1170, failures=0, errors=0, skipped=0 | `fix1_combined_recheck.json/.log` |
| fix1_private_replay | 2026-10-15T19:00:46+08:00 / 2026-10-15T19:00:46+08:00 | 0 | N/A | `fix1_private_replay.json/.log` |
| fix1_mypy | 2026-10-15T18:57:59+08:00 / 2026-10-15T18:57:59+08:00 | 0 | N/A | `fix1_mypy.json/.log` |
| fix1_ruff | 2026-10-15T18:58:00+08:00 / 2026-10-15T18:58:00+08:00 | 0 | N/A | `fix1_ruff.json/.log` |
| fix1_format_check | 2026-10-15T18:58:00+08:00 / 2026-10-15T18:58:00+08:00 | 0 | N/A | `fix1_format_check.json/.log` |
| fix1_cbm_index | 2026-10-15T18:57:59+08:00 / 2026-10-15T18:58:05+08:00 | 0 | N/A | `fix1_cbm_index.json/.log` |
| fix1_cbm_trace_uri | 2026-10-15T19:00:22+08:00 / 2026-10-15T19:00:26+08:00 | 0 | N/A | `fix1_cbm_trace_uri.json/.log` |
| fix1_cbm_arxiv_uri | 2026-10-15T19:01:54+08:00 / 2026-10-15T19:02:02+08:00 | 0 | N/A | `fix1_cbm_arxiv_uri.json/.log` |
| fix1_cbm_rss_uri | 2026-10-15T19:01:54+08:00 / 2026-10-15T19:01:58+08:00 | 0 | N/A | `fix1_cbm_rss_uri.json/.log` |

纯unit最新1109 passed/0fail/error/skip，6818 statements/2177 missed，coverage68.07%原60门通过；组合1170 passed/0fail/error/skip（unit1109+相关合同14+原独立47），coverage68.32%。mypy84 src、全backend Ruff/208格式通过。零新HTTP/模型调用；仓外私有991606B原RSS20项8断言再次通过，许可unknown完整正文仍未入可推送包。

首次修复后组合`fix1_green_combined`有1169pass/1fail：唯一是未改的原R05 CPU_SECONDS=1忙子进程8秒墙钟TimeoutExpired，初审四红与新增边界均已通过。该失败与先前同类失败均保留；此后同参数pure unit及有限组合复跑通过，**不能说其宿主敏感根因已修复**；已向主控请求诊断，未改timeout、共享代码或skip。

src-only CBM同WT缓存刷新为1125 nodes/5391 edges，not_indexed/partial/unusable=0；源码rg核对所有URI/时间/pagination调用。第一次按短名_official_uri查询返回两个匹配ambiguous（CLI exit0不等于追踪已完成），留档后按实际qualified_name分别追踪两个源成功。不索引私有原件、holdout、报告或秘密；图无产品caller经源码确认，仍不声称真实接线。

### 当前边界与后续

复用原normalizer、stdlib和现有异常，没有新依赖/公共DTO/配置/迁移/锁/进度更改；只有原两parser/原unit和本包证据/报告变化。原artifact hash封存方案保持，最新manifest按原字节重新生成并校验。实现只属内部解析切片：API/worker/PG/UI、真实持续采集/漏采/时效、integration/frontend/e2e/live/manual仍not_run，整R06/T12/T14/G-C不验收。

2026-10-15T19:04:18+08:00：新增本修复记录，保留所有旧红、限额偶发失败和旧版本记录。修订人 `/root/r06_feed_parsers`；原独立reviewer后续定向复核冻结新版本。


## 修复轮2 · 数字时区的共同解析边界

本轮写作开始：2026-10-15T19:25:13+08:00；结束/证据截止：2026-10-15T19:25:14+08:00；首次创建时间保持不变。
作者状态 awaiting_review；原Must1/3在独立cb9复核已closed，本轮只修原Must2未关闭边界；没有签accepted、push或API/PG接线。
原独立复核报告：`D:/dianzi/reports/reviews/recovery/G-C-R06-feed-parsers-review-1-recheck.md`（cb9候选needs_changes）。`07:00:0 +1260`与`7:0:0 +1260`原2红未编辑；本作者新增13个同根因非法输入和13个合法对应输入，预期不从实现生成。

根因：第1轮数字zone检查仍依赖固定clock位数，而锁定Python3.12的stdlib接受更宽时钟拼写、附着offset、RFC850及部分ctime排列。不是新的来源事故，未声称真实上游已有该输入/实际指标受损。

修复：删除clock正则；新增私有`_timezone_token`只按实际标准库字段消费位置定位原始zone（可选weekday/逗号、RFC850日期拆分、附着zone、ctime字段交换），不解释日历或时钟。对实际数值zone使用相同int接受语义检查绝对HH≤23/MM≤59后，原`parsedate_to_datetime`完成日历/timezone/UTC转换。非数字GMT等仍交原库；-0000仍按原库未知zone拒绝；缺时间仍None。这里只补stdlib未校验原HH/MM的信任边界，没有私有stdlib运行时import或通用日期框架。

26个新增case覆盖短clock、无秒、点分、宽零填充、附着offset、RFC850/ctime、weekday无FWS、数字zone无sign/int下划线/Unicode、Unicode时钟；合法注释和尾部忽略token含+1260不误拒绝，未来RFC850年2060也不误当zone。支持范围仍是本项目锁定Python3.12布局；依赖升级若改变该消费布局须复核这些合同，而不是把原子串特判扩成另一日期解释器。

代码冻结：`9138e1741722491ca0c4df6b5540b76157a2b47e`；src tree `d7ba58c14999c79a01fe4d732235d5035a69793a`。只改原RSS parser/直接unit；arXiv、公共文件、DTO、配置、迁移、锁、认证、进度和所有独立期望不变。四业务/测试文件与冻结blob字节一致，见 `fix2_code_snapshot.json`；旧b1ff/6b7/cb9意见仅对应其历史版本，未覆盖其失败记录。

| 标签 | 开始 / 结束（Asia/Shanghai） | exit | JUnit事件数 | 参数/日志 |
|---|---|---|---|---|
| fix2_red_combined | 2026-10-15T19:17:40+08:00 / 2026-10-15T19:18:16+08:00 | 1 | tests=1198, failures=15, errors=0, skipped=0 | `fix2_red_combined.json/.log` |
| fix2_combined | 2026-10-15T19:19:05+08:00 / 2026-10-15T19:19:35+08:00 | 0 | tests=1198, failures=0, errors=0, skipped=0 | `fix2_combined.json/.log` |
| fix2_unit | 2026-10-15T19:21:19+08:00 / 2026-10-15T19:21:53+08:00 | 0 | tests=1135, failures=0, errors=0, skipped=0 | `fix2_unit.json/.log` |
| fix2_mypy | 2026-10-15T19:20:12+08:00 / 2026-10-15T19:20:13+08:00 | 0 | N/A | `fix2_mypy.json/.log` |
| fix2_ruff | 2026-10-15T19:20:13+08:00 / 2026-10-15T19:20:13+08:00 | 0 | N/A | `fix2_ruff.json/.log` |
| fix2_format_check | 2026-10-15T19:20:13+08:00 / 2026-10-15T19:20:14+08:00 | 0 | N/A | `fix2_format_check.json/.log` |
| fix2_private_replay | 2026-10-15T19:21:54+08:00 / 2026-10-15T19:21:54+08:00 | 0 | N/A | `fix2_private_replay.json/.log` |
| fix2_cbm_index | 2026-10-15T19:20:12+08:00 / 2026-10-15T19:20:18+08:00 | 0 | N/A | `fix2_cbm_index.json/.log` |
| fix2_cbm_timezone | 2026-10-15T19:21:29+08:00 / 2026-10-15T19:21:34+08:00 | 0 | N/A | `fix2_cbm_timezone.json/.log` |

先复现1198集合中的15红（原2+新增13）/1183通过，日志保留；修复后1198 passed/0fail/error/skip，coverage68.45%（6852 statements/2162 missed），原60门不变。最新pure unit1135 passed/0fail/error/skip，coverage68.20%（2179 missed）；包含原1135 unit + 14相关合同 + 47原独立边界 + 2新独立边界的组合如上。84 src mypy、全backend Ruff、208格式通过，原CPU_SECONDS=1/timeout=8用例本轮两次通过，旧偶发失败未删且不宣称根因已修复，没有进一步扩大重跑。

原公有arXiv2篇/明确RSS metadata-only20项随合同再次通过；仓外991606B完整原RSS20项8断言再次通过、零网络、未知许可全文不进公开包。原47+新2独立输入文件路径/hash由snapshot记录，作者未修改。索引仅本WT src、外部同缓存刷新1126 nodes/5394 edges，not_indexed/partial/unusable=0，trace+rg核对唯一caller `_published_at`；新增helper没有API/worker caller。复用stdlib/既有normalizer，没有新依赖。

实现仍仅内部parser；integration/frontend/e2e/live/manual均not_run，整R06/T12/T14/G-C不验收。本轮待原独立reviewer在新冻结候选复核Must2；若同根因再失败，由主控新诊断Agent处理，作者不继续扩大补丁。

2026-10-15T19:25:14+08:00：追加修复轮2及真实红→绿、合法形态保护、版本绑定与未验证范围。修订人 `/root/r06_feed_parsers`。
