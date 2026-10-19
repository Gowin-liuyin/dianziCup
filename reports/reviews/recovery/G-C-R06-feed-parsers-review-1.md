# G-C / R06-A 内部 feed parser 独立初审 1

What this change does: 本批新增 arXiv Atom 与 Trail of Bits RSS 的纯解析入口，复用既有 academic/feed normalizer，返回不可变元数据 DTO。它没有产品 caller，没有获取文章或论文全文，也没有接通来源采集、PostgreSQL 或 UI。

首次创建/写作开始：2026-10-15T18:49:25+08:00。实际写作结束/证据截止见文末生成收据。

审查者：`/root/r06_feed_parsers_independent_review`，未参与本批实现；只拥有本报告与 `reports/runs/recovery_r06_feed_parsers_review_1_20261015/`。固定候选 `8e4d8a0a149980d92f972d510b6d8849298bcadb`，基线 `7ed73540c001a4e7f5b5fa5dc2948c4b4635590f`，作者代码 `b1ff04a267babda5d57506d6e1e39006a2e4bb34`。独立 detached WT：`D:/wt/r06-feed-review`；作者 `D:/wt/r06-feeds` 未修改。结论状态为 **needs_changes**，不是 accepted；没有提交、push 或状态文件变动。

候选 tree：`c7f990d0d3077e67a5d5096c03b0186975432fa7`；`backend/src` tree：`ef125130ebe25940844856413444eb3f39a3b8ef`。四个业务/测试文件的候选 Git blob 与作者代码 SHA 一致，最终独立 WT `git status --short` 为空。主仓库的已有未提交修改完整保留。

## 范围与合同

已读固定 SHA 的 AGENTS、execution map、progress 状态/交接、恢复 R06 卡、T12/T14、03/04/05/06/07 合同、README、作者 `R06-feed-parsers.md`、delivery manifest。按用户派发固定两个接口：`parse_arxiv_atom(bytes) -> ArxivDiscoveryPage(records: tuple[AcademicRecord,...], total_results, start_index, items_per_page)`；`parse_trailofbits_rss(bytes) -> tuple[FeedEntry,...]`。许可证只是未核实元数据标识，不能推导抓取或再分发授权；未知版本不能猜成 v1；RSS description 是 feed 内容，article_body 仍缺失，channel lastBuildDate 不代表文章修改时间。

审查四文件：`backend/src/ai_intel/ingestion/sources/arxiv_atom.py`、`trailofbits_rss.py`、`backend/tests/unit/test_r06_feed_parsers.py`、`backend/tests/contract/test_r06_archived_feed_replay.py`；另读它们调用的 `academic.py`/`feed.py` 与原 T12/T14 合同测试。没有改变业务、schema、锁、配置、金标、分母或门槛。

G-B 仍在审查中。本切片可安全独立准备的依据是恢复 R06 卡明确“R05不阻塞独立来源适配”，且源码显示输入仅为 bytes，输出为 DTO，无数据库事务、模型调用、付费 API、任务提交或外部 IO。它不触及 G-B 的付费问答与事务修复，故可以审其内部代码；这一理由不能放行 G-C 阶段或整 R06，更不能替代 PG/UI/live 验收。

## Must fix

1. **非末页缺条仍被当作可用分页结果**（`arxiv_atom.py:233–236`，P1）。

   What this is：分页返回 total/start/itemsPerPage，同时函数文档声称拒绝截断页语义。恢复 R06 验收②要求分页边界不漏，04/W01 第4条要求每条记录已持久化或形成可恢复失败后才提交页游标。

   Problem：合成 Atom 报 `totalResults=100,startIndex=0,itemsPerPage=10`，仅含一条合法 entry。期望明确 `AcademicContractError`，实际返回 `records=1,total_results=100,start_index=0,items_per_page=10`；当前检查只拒绝过多条目、越界和空的非末页。`test_atom_underfull_nonfinal_page_is_not_success` 为红，原始 XML 和实际输出完整保存在 `defect_observations.log`。

   Fix：在现有冻结接口内，拒绝 `len(entries) < min(size, total-start)` 的非完整页，保留正常空页和最终不足一页的行为。如果未来确认上游允许稀疏页，应由主控显式建立 incomplete 与不推进游标的合同，不能静默成功。

   If we skip it：未来若按 `start+items_per_page` 推进，上述输入会跳过位置1–9。**本轮已确认的是 parser 接受不完整页；没有产品 caller，也未验证真实 arXiv 会产生该页或观察到实际漏采。** 后续 caller 风险是条件推论，不能冒充已发生事故。复验需此负例转绿并保留原正常/最后页/空页测试、组合回归与原60%门。

2. **非法 RSS 时区分钟值被换算成确定发布时间**（`trailofbits_rss.py:88–97`，P2）。

   What this is：`pubDate` 被解析并转为 UTC，供后续发布时间及采集延迟使用；非法或无时区应明确失败，而未知发布时间不能被猜测。

   Problem：输入 `<pubDate>Wed, 14 Oct 2026 07:00:00 +1260</pubDate>`。数字偏移的分钟60不合法，期望 `FeedParseError`；实际 `parsedate_to_datetime` 宽松地把它等同+13小时，输出 `published_at=2026-10-13T18:00:00Z`。`test_rss_invalid_numeric_timezone_minutes_are_rejected` 为红。这是纯业务输入失败，不是环境缺失或覆盖门失败。

   Fix：调用现有标准库解析器前，对出现的数字时区显式检查小时和分钟范围，至少拒绝分钟大于59；仍用标准库完成日历和时区换算，不新造日期解析框架。

   If we skip it：来源异常时间会成为确定 UTC 元数据，后续时效统计与排序可能使用它。尚未运行采集指标 caller，因此不声称实际 P1 分数已受损。复验需 +1260 转绿，正常 -0400/+0000、缺失、naive、非法日历和未来时间路径仍符合原合同。

3. **DEL 控制字符绕过链接和许可标识边界**（`trailofbits_rss.py:77–84`、`arxiv_atom.py:123–141`；同模块官方 URI 判断 `arxiv_atom.py:96` 有同样检查方式，P2）。

   What this is：新 parser 负责拒绝 URI 中的控制字符，许可标识也有明确的控制字符拒绝约束；固定源域约束不能替代字符合法性。

   Problem：RSS `<link>https://blog.trailofbits.com/review/&#127;</link>` 实际返回 `canonical_uri="https://blog.trailofbits.com/review/\u007f"`；Atom `<arxiv:license>https://publisher.invalid/&#127;</arxiv:license>` 实际保留 `license_identifier="https://publisher.invalid/\u007f"`。期望分别为 `FeedParseError` / `AcademicContractError`。U+007F 是 DEL 控制字符，但代码只检查 `<32`，`isspace()` 不拒绝它；两个独立负例均红。

   Fix：在各现有字符校验中补上 ASCII DEL 拒绝，并为输出链接和许可值保留这两条负例；无需改 DTO 或加依赖，也不能把未知许可 URI 改成已授权。

   If we skip it：纯 parser 会输出违反已冻结控制字符边界的 URI/identifier。未执行解引用或浏览器渲染，未证实任意外域访问、利用、日志注入或再分发；这不是已发生的 SSRF 事件。复验需两例转绿，普通未核实许可文本/安全 http(s) 标识仍仅保留为文本，既有 socket 封禁与固定域测试仍通过。

## 亲自复跑的结果

所有正式命令、cwd、ISO秒级+08:00起止、退出码见文末命令账本及同名 JSON；pytest 原 `--cov-fail-under=60` 完整保留，没有 skip、增加原8秒 timeout 或降低门槛。

| 检查 | 退出码 | 真实结果 |
|---|---:|---|
| frozen/offline sync | 0 | 按该 WT 的冻结锁安装；无新网络或大模型下载 |
| 全 unit | 0 | 1086 passed、0 failed/error/skipped；覆盖68.03%，6813 statements/2178 missed |
| 全 unit + T12/T14/archived合同 + 独立边界 | 1 | 总1147：1143 passed、4 failed、0 error/skipped；覆盖68.30%，6813 statements/2160 missed |
| 上行中的原测试分类 | — | 原1100全部通过（unit1086 + 原T12/T14共12 + 新archive合同2）；独立47例为43 passed/4 failed |
| mypy src | 0 | 84 source files，无问题 |
| Ruff / format（整个 backend） | 0 / 0 | 全部检查通过；208 files already formatted |
| diff --check（基线→候选） | 0 | 无空白错误 |
| 最终 manifest / archive 核验 | 0 | 114个原证据 Git blob 与 manifest 字节数/hash匹配；2个gzip解压原字节/hash匹配；四代码/测试文件与b1ff04一致 |
| 私有完整原 RSS 离线回放 | 0 | 991606B、指定sha256、20items；10个元数据断言 + 2个完整性断言；0网络、0全文抓取/复制 |

原 R05 `test_real_native_cpu_limit_terminates_busy_child` 在两次完整 unit 执行中均通过，原 `cpu_seconds=1`、`timeout=8` 未改。作者曾有一次超时的历史仍存在，本轮未重现；不能据两次通过宣称其环境敏感根因已修复。FastAPI/Starlette 的既有弃用 warning 保留，两次运行各1条。

本轮独立 fixture 覆盖：DTD/外部实体/参数实体/内部实体声明、UTF-16/32/Latin-1/非法UTF-8/UTF-8 BOM、空/精确2MiB/超字节、精确10000节点与超节点、精确32深度与超深度、1000条边界与不截断、未知版本、缺时间与全文能力、channel修改时间隔离、恶意URI、PDF版本冲突、未核实许可不赋权、description只属feed、GUID不变身份/正文修订hash，以及上述四条红例。作者79个新 unit 与原测试也实际执行。没有使用实现输出来生成预期，没有把 Agent 或模型当人工金标。

## 调用关系与实现检查

已先查看 CBM 0.11.0 的真实 help/工具参数，再建仓外独立缓存 `/tmp/dianzi-cbm-r06-feed-review-1-20261015`，项目 `r06-feed-review-1-src`；输入仅 `/mnt/d/wt/r06-feed-review/backend/src`，未持久化到仓库。实际索引1125 nodes/5390 edges，not_indexed、partial、unusable、skipped均0；84个src文件。第一次空参 schema 命令返回缺 project 的错误，留档后按真实 help 指定项目成功；不把错误当通过。

独立 `get_graph_schema` 与双向 `trace_path` 显示：Atom 经 bounded XML、字段/URI/时间校验到 `normalize_academic_record -> AcademicRecord`；RSS 经对应校验到 `normalize_feed_entry -> canonicalize_uri -> FeedEntry`。两个 parser 的图内 inbound caller 都为0。图仅索引src，**不能由图断言 tests 已索引**；另外用 `rg` 扫描实际 src/tests，逐一核对测试 import 与调用，确认新 parser 未接 API、source_jobs、worker、SourceKind、应用或 UI，`sources/__init__.py` 没有重新 export 入口。图是索引辅助，结论来自源码和实跑。

仅增加两个标准库纯解析模块；normalizer、锁和依赖没有变化。结构限制在构建XML树时生效，不是构建大树之后才检查；拒绝DTD，无外部实体展开/解引用。许可已知/未知安全identifier保留、论文全文能力始终 metadata_only；RSS输出modified为None、article_body缺失。duplicate canonical/version、错误namespace/嵌套条目和 xml:base 均明确失败。测试证明的是纯 parser 边界，不替代网关 DNS、重定向、租户或完整 security 检查。

## 原样本与封存事实

arXiv公开原元数据响应6101B，sha256 `8fd7cd6d0f71f5540d099047a778e813d67b1392a21e7c089bd49bc80a6bb3f1`；已亲自运行archive合同重放2篇。许可记录为CC0元数据，不能外推到论文PDF。

Trail of Bits未知再分发许可的完整原 RSS 991606B，sha256 `86a1faac2d08bd01281efcb72ebb6c57a9a4213aa61ebf055b77ceb093e476f0`；仅只读指定 source-prep 私有路径，不修改其WT，不在报告/log复制完整description。私有回放确认20项的ID/URI/title/published与公开摘录一致、modified未知、article_body缺失；其10元数据断言不是10个人工金标，也不是live源接通。

公开候选仅含明确metadata-only摘录6597B，sha256 `ce9b990828a06b85bf17924f97b2c8ee769eb69e7710d177f5a82f2ea3719b2f`，20条事实字段，首条9词必要短引文，其他description缺失；不能称完整原响应。候选两个R06 evidence子树的 `git ls-tree` 未列入完整 `doh_05_trailofbits_feed.body`。真实凭据与完整秘密扫描交主控，审查者没有读取 `.env`、key或holdout。

作者旧8bb8bd候选47处CRLF→LF封存错误历史未覆盖。新候选114 blob逐一匹配，lossless压缩2项也通过。本轮自己的首次核验脚本把Windows正常checkout换行等同Git原blob而在作者md处失败（`verify_evidence` exit1）；修正为比较Git blob与manifest，checkout变化另用Git filter核验，`verify_evidence_corrected` exit0。11个文本checkout转换已单列于结果JSON，原失败日志保留；这不是新候选manifest失真。

独立运行附件也保留首次自身Ruff失败、仅限owned脚本的格式/import调整与最终检查。47例原执行文件原字节存为 `tested_independent_47.py.txt`；可复验的 `.py` 保留47例，后续排版与不可变属性测试变量命名改动没有修改四条红例。四红fixture/input函数的语法树一致性及文件hash见生成收据，不拿排版后的文件伪称首次原字节。

## 未检、偏差与交接

本批 unit=passed、相关contract=passed；独立安全/业务边界=failed（四红）。integration/frontend/e2e/live/manual 均 not_run；不签整R06、T12/T14、G-C、PG/UI、八类真实来源、持续采集、断点事务、漏采参考集、正文解析、全文PDF质量、性能或正式评分。F1/F2/R1只有T12/T14元数据解析的局部代码证据；P1时效、持续运行与漏采没有本轮live证据。

源码无产品caller是派发批准的内部切片边界，不当作本轮缺陷；公共 DTO 没有许可核实状态/论文撤回unknown联合值也是既有合同，调用方必须遵守未知不等于否定，不由本review擅改。未发现需要新增框架、通用BaseService或依赖的理由；没有Lean删除项。缺测与假设已经与上面的确认缺陷分开。

bootstrap的worktree创建、第一次help、只读文档/源码命令由工具真实执行，但当时未额外捕获ISO秒级起止，标记 **not_recorded**，不补算为测试时长或通过证据。所有正式测试/审查命令均由run wrapper记录真实参数、cwd、ISO秒级+08:00起止和退出码；账本中的非pytest检查测试数为N/A，不凑数量。

下一步：原作者最小修复上述1–3；保留原47例/四红输入，交新冻结SHA供本reviewer定向复核，重跑原unit、相关合同、独立负例与静态门；主控随后才决定内部批次是否可合并。此次不等待修复，不扩散补丁、不派子Agent、不写accepted、不push。

最小复验资产：`D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/test_independent_r06_feed_boundaries.py`；精确synthetic XML/实际DTO：`defect_observations.log`；组合原命令与JUnit：`unit_contract_independent.json` / `.xml`。四红函数名分别为 `test_atom_underfull_nonfinal_page_is_not_success`、`test_rss_invalid_numeric_timezone_minutes_are_rejected`、`test_rss_del_control_character_uri_is_rejected`、`test_arxiv_del_control_character_license_is_rejected`。

**Verdict: fix 1, 2 and 3 first.** 结论仅适用于上述固定候选的内部parser批次。

<!-- GENERATED_COMMAND_LEDGER -->

## 实际命令账本

每行链接指向参数原件JSON；同名.log保留原输出。所有时间均+08:00。

| 标签 | cwd | 开始 / 结束 | exit | 原命令 |
|---|---|---|---:|---|
| [cbm_schema](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/cbm_schema.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:40:05+08:00 / 2026-10-15T18:40:09+08:00 | 1 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_graph_schema '{}'` |
| [sync](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/sync.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:40:20+08:00 / 2026-10-15T18:40:26+08:00 | 0 | `uv sync --frozen --offline` |
| [cbm_index](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/cbm_index.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:40:42+08:00 / 2026-10-15T18:40:48+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r06-feed-review/backend/src --name r06-feed-review-1-src --mode fast --persistence false` |
| [unit](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/unit.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:40:42+08:00 / 2026-10-15T18:41:36+08:00 | 0 | `uv run --frozen --offline pytest tests/unit --junitxml=D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/unit.xml --cov-report=json:D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/unit_coverage.json` |
| [static_mypy](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/static_mypy.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:41:17+08:00 / 2026-10-15T18:41:27+08:00 | 0 | `uv run --frozen --offline mypy src` |
| [static_ruff](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/static_ruff.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:41:27+08:00 / 2026-10-15T18:41:28+08:00 | 0 | `uv run --frozen --offline ruff check .` |
| [static_format](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/static_format.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:41:28+08:00 / 2026-10-15T18:41:28+08:00 | 0 | `uv run --frozen --offline ruff format --check .` |
| [callers](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/callers.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:41:51+08:00 / 2026-10-15T18:41:51+08:00 | 0 | `rg -n 'parse_arxiv_atom\|parse_trailofbits_rss\|normalize_academic_record\|normalize_feed_entry\|arxiv_atom\|trailofbits_rss' backend/src backend/tests` |
| [cbm_schema_indexed](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/cbm_schema_indexed.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:41:51+08:00 / 2026-10-15T18:41:55+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_graph_schema --project r06-feed-review-1-src --format json --diagnostics full` |
| [cbm_trace_arxiv](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/cbm_trace_arxiv.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:41:55+08:00 / 2026-10-15T18:41:59+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project r06-feed-review-1-src --function-name parse_arxiv_atom --direction both --depth 3 --format json --include-evidence true --max-output-tokens 7000` |
| [cbm_trace_rss](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/cbm_trace_rss.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:41:59+08:00 / 2026-10-15T18:42:03+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project r06-feed-review-1-src --function-name parse_trailofbits_rss --direction both --depth 3 --format json --include-evidence true --max-output-tokens 7000` |
| [unit_contract_independent](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/unit_contract_independent.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:43:40+08:00 / 2026-10-15T18:44:30+08:00 | 1 | `uv run --frozen --offline pytest tests/unit tests/contract/test_t12_vendor_blog_connectors.py tests/contract/test_t14_academic_connector.py tests/contract/test_r06_archived_feed_replay.py D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/test_independent_r06_feed_boundaries.py --junitxml=D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/unit_contract_independent.xml --cov-report=json:D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/unit_contract_independent_coverage.json` |
| [private_replay](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/private_replay.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:44:49+08:00 / 2026-10-15T18:44:49+08:00 | 0 | `uv run --frozen --offline python D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/replay_private_source_metadata.py` |
| [verify_evidence](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/verify_evidence.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:44:49+08:00 / 2026-10-15T18:44:49+08:00 | 1 | `python D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/verify_fixed_evidence.py` |
| [defect_observations](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/defect_observations.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:46:07+08:00 / 2026-10-15T18:46:08+08:00 | 0 | `uv run --frozen --offline python D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/observe_confirmed_inputs.py` |
| [diff_check](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/diff_check.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:46:07+08:00 / 2026-10-15T18:46:08+08:00 | 0 | `git diff --check 7ed73540c001a4e7f5b5fa5dc2948c4b4635590f 8e4d8a0a149980d92f972d510b6d8849298bcadb` |
| [preflight_fixed_git](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/preflight_fixed_git.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:46:07+08:00 / 2026-10-15T18:46:07+08:00 | 0 | `git show --format=fuller --no-patch 8e4d8a0a149980d92f972d510b6d8849298bcadb` |
| [verify_evidence_corrected](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/verify_evidence_corrected.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:46:07+08:00 / 2026-10-15T18:46:16+08:00 | 0 | `python D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/verify_fixed_evidence.py` |
| [cbm_help](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/cbm_help.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:46:27+08:00 / 2026-10-15T18:46:28+08:00 | 0 | `wsl -d Ubuntu-22.04 -- /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp --help` |
| [cbm_index_help](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/cbm_index_help.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:46:28+08:00 / 2026-10-15T18:46:29+08:00 | 0 | `wsl -d Ubuntu-22.04 -- /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli index_repository --help` |
| [cbm_trace_help](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/cbm_trace_help.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:46:29+08:00 / 2026-10-15T18:46:31+08:00 | 0 | `wsl -d Ubuntu-22.04 -- /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli trace_path --help` |
| [delivery_scope](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/delivery_scope.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:48:08+08:00 / 2026-10-15T18:48:08+08:00 | 0 | `git ls-tree -r --name-only 8e4d8a0a149980d92f972d510b6d8849298bcadb -- reports/runs/recovery_r06_source_preparation_20261015 reports/runs/recovery_r06_feed_parsers_20261015` |
| [own_ruff](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/own_ruff.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:48:08+08:00 / 2026-10-15T18:48:09+08:00 | 1 | `uv run --frozen --offline ruff check --config D:/wt/r06-feed-review/backend/pyproject.toml D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015` |
| [own_format_apply](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/own_format_apply.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:48:40+08:00 / 2026-10-15T18:48:40+08:00 | 0 | `uv run --frozen --offline ruff format --config D:/wt/r06-feed-review/backend/pyproject.toml D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015` |
| [own_imports_fix](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/own_imports_fix.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:48:40+08:00 / 2026-10-15T18:48:41+08:00 | 0 | `uv run --frozen --offline ruff check --select I --fix --config D:/wt/r06-feed-review/backend/pyproject.toml D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015` |
| [own_ruff_final](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/own_ruff_final.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:48:41+08:00 / 2026-10-15T18:48:41+08:00 | 1 | `uv run --frozen --offline ruff check --config D:/wt/r06-feed-review/backend/pyproject.toml D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015` |
| [own_format_check](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/own_format_check.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:51:57+08:00 / 2026-10-15T18:51:57+08:00 | 0 | `uv run --frozen --offline ruff format --check --config D:/wt/r06-feed-review/backend/pyproject.toml D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015` |
| [own_format_final_apply](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/own_format_final_apply.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:51:57+08:00 / 2026-10-15T18:51:57+08:00 | 0 | `uv run --frozen --offline ruff format --config D:/wt/r06-feed-review/backend/pyproject.toml D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015` |
| [own_ruff_pass](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/own_ruff_pass.json) | `D:/wt/r06-feed-review/backend` | 2026-10-15T18:51:57+08:00 / 2026-10-15T18:51:57+08:00 | 0 | `uv run --frozen --offline ruff check --config D:/wt/r06-feed-review/backend/pyproject.toml D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015` |
| [report_finalize](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/report_finalize.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:51:58+08:00 / 2026-10-15T18:51:58+08:00 | 0 | `python D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/finalize_review.py` |
| [fixed_final_status](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/fixed_final_status.json) | `D:/wt/r06-feed-review` | 2026-10-15T18:52:21+08:00 / 2026-10-15T18:52:21+08:00 | 0 | `git status --short` |

写作结束/证据截止：2026-10-15T18:52:21+08:00。生成收据：`review_summary.json`。
