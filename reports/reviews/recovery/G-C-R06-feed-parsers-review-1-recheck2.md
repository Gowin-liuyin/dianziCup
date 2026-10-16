# G-C / R06-A 独立初审1 · 第二轮定向复核

What this change does: 本轮只复核原Must 2的日期解析共同根因。新候选移除固定clock位数正则，用私有token定位函数找到锁定Python 3.12实际消费的原时区字段，再检查数值HH/MM；日历、clock解释和UTC转换仍由原标准库完成。

首次创建/写作开始：2026-10-15T19:34:07+08:00。结束/证据截止见文末收据。

审查者 `/root/r06_feed_parsers_independent_review`，未参与实现或两次修复。固定候选 **10c81f0cda6b8065ebb9f1fef10c8459975c2d26**；代码 **9138e1741722491ca0c4df6b5540b76157a2b47e**；候选tree=`15dd390bd91026d542a631de6e417aa67cea6c4a`；src tree=`d7ba58c14999c79a01fe4d732235d5035a69793a`。新独立detached WT=`D:/wt/r06-feed-review-recheck2`，不以作者变化中的WT作为通过证据。

结论：**原Must 2 closed。结合上一轮已关闭的1/3，本固定候选可有限Ship，范围仅R06-A内部parser批次。** 不签整R06/T12/T14/G-C、PG/UI/live或项目CPU缺陷修复，不写accepted。没有改业务/schema/锁/状态、提交、push或spawn；没有网络/付费、秘密或holdout读取。root既有未提交工作保留。独占报告与run先在独立WT形成，再复制到root同路径并逐文件核hash，见 `artifact_copy_hashes.json`。

## 原Must 2为何可关闭

`trailofbits_rss.py:94–133`的 `_timezone_token`仅复制锁定标准库在选择zone之前的字段定位步骤：可选weekday/逗号、RFC850日期拆分、附着offset分离、ctime的year/clock及year/zone换位。`_published_at:136–154`对该原token执行与标准库相同的int接受语义，拒绝绝对HH>23或MM>59，再调用原 `parsedate_to_datetime`；不解释日历、clock或推断发布时间。

亲自读取运行环境Python **3.12.13**的 `email._parseaddr._parsedate_tz`源码，留在 `stdlib_source.log`，逐段核对了上述token定位顺序和原int语义。业务代码没有运行时import该私有标准库函数；仍使用原public `email.utils.parsedate_to_datetime`。它没有把未来RFC850年2060或注释里的+1260错当zone，也没有继续依赖clock位数。

原初审 `07:00:00 +1260`、上一轮 `07:00:0 +1260`及`7:0:0 +1260`均明确拒绝。原47及原2独立文件字节/断言原样，分别sha256：

- `test_independent_r06_feed_boundaries.py`：`65b809db3152f99fdcc16dd7b2cff4fdbaaa050cc9ab57a21166c4425976e3fd`。
- `test_timezone_repair_boundary.py`：`4d2b198e5973eca99d7bb43f205750a2824469921558e1ac9d916c6d464d7244`。

作者新增26例（13非法+13合法）全部亲自复跑，覆盖短clock/无秒/点分/宽零填充/Unicode、附着offset、RFC850/ctime、无FWS、数字zone的无sign/int下划线/Unicode、合法GMT/注释/尾部token与2060年保护。

另补5个最小同根因独立检查，预期写成固定值而不是被测结果：实际zone置于year位置、month/day换位并附着offset，分别用非法+1260和合法-0400成对验证；合法两例仍得到 `2026-10-14T11:00:00Z`，非法两例为 `FeedParseError`；-0000保持标准库的未知来源zone并被显式拒绝，不升级为确定UTC。没有扩大到新来源、新日期功能或全项目审计。

这些断言验证可观察结果，而不是只验证helper返回字符。没有改原失败的预期、skip或覆盖门来转绿。未发现本范围内仍需修复的确认缺陷；没有用Agent/模型作人工金标。原Must1/3在上一轮已关闭，本轮未重开其审计；原47和原unit仍实际回归。

## 实际复跑与原质量门

| 检查 | 开始 / 结束（+08:00） | exit | 实际结果 |
|---|---|---:|---|
| pure unit | 2026-10-15T19:31:11 / 19:31:56 | 0 | 1135 passed、0fail/error/skipped；68.20%，6852 statements/2179 missed |
| unit+相关合同+原47+原2+最小5 | 2026-10-15T19:32:30 / 19:33:06 | 0 | 1203 passed、0fail/error/skipped；68.45%，6852 statements/2162 missed |
| mypy src | 2026-10-15T19:31:11 / 19:31:25 | 0 | 84 source files，无问题 |
| Ruff / format | 2026-10-15T19:31:25 / 19:31:25 | 0 / 0 | 整backend通过；208 files already formatted |
| verify_evidence | 2026-10-15T19:32:04 / 19:32:16 | 0 | 194原证据blob、2个lossless gzip及四代码/测试文件核验通过 |
| private_replay | 2026-10-15T19:32:16 / 19:32:17 | 0 | 指定991606B原RSS/sha256/20items；10元数据+2完整性断言；0网络/全文复制 |

组合数量：unit1135（含本轮作者新增26）+T12/T14/archived合同14+原47+原2=原1198，再加独立5，合计1203。所有实际命令argv/cwd/ISO秒级+08:00起止/exit及原log/JUnit/coverage在同名文件，完整账本附后；非pytest命令测试数N/A。原 `--cov-fail-under=60`与原CPU `cpu_seconds=1/timeout=8`未动，两次各1条既有FastAPI/Starlette弃用warning保留。

**Windows CPU原诊断缺陷仍open。** 本轮两次原测试恰好通过，不是诊断缺陷已修好，不替代主控独立诊断报告；没有改process_limits、原R05测试或skip。此parser修复无CPU/process-limit副作用，因此这里只给内部parser的有限结论，不给项目回归缺陷或阶段放行签字。

## 独立索引、caller与源码

CBM portable 0.11.0真实help已查看；新仓外独立缓存 `/tmp/dianzi-cbm-r06-feed-review-1-recheck2-20261015`，只索引本冻结WT的 `backend/src`，不持久化仓内图。实际1126 nodes/5394 edges，not_indexed/partial/unusable/skipped均0。运行schema与token/helper日期双向trace：token唯一直接caller为 `_published_at`，hop2为 `parse_trailofbits_rss`；日期函数唯一caller为RSS入口。

图仅含src，未声称tests已索引；用rg扫描全部src/tests并读源码核对所有caller。图不替代源码：外部标准库具体解释由本机3.12.13源码与实测核对，不能因图未解析其库内调用而忽略它。RSS入口将所有pubDate交同一日期路径，新helper没有API/worker/export调用。

`git diff --exit-code 9138 10c -- backend/src backend/tests`为0；四业务/测试文件逐Git blob也一致。相较cb9只改RSS与直接unit，arXiv、normalizer、DTO、依赖、锁、schema、配置、认证与指标合同未改。重读冻结规范、执行图/状态、作者修复记录并按原03/04/05/06/07与T12/T14要求定向核对；未扩展全项目审计。

版本绑定是明确限制：本轮对实际Python3.12.13布局作证，未检查其他Python版本或未来标准库变更。未来升级需要复跑同一token兼容合同；不能把此次本机结果扩大成所有版本兼容，也不提出新依赖/框架或另建日期解释器。

## Raw/Git bytes、来源回放与许可

原manifest不含自身194文件/6396701B全部逐 **Git blob原字节**核对字节数和sha256。13个普通文本在Windows checkout有换行转换，另用Git filter核对内容身份；没有把checkout与blob原字节混为一谈。两个既有大诊断gzip解压后的原字节/hash也匹配，前两轮红、失败和旧CRLF封存失败历史保留。

公开arXiv原元数据Atom6101B，sha256 `8fd7cd6d0f71f5540d099047a778e813d67b1392a21e7c089bd49bc80a6bb3f1`，2篇随archive合同再回放；来源准备的CC0只用于元数据，不能外推为PDF许可。

私有Trail of Bits完整RSS991606B，sha256 `86a1faac2d08bd01281efcb72ebb6c57a9a4213aa61ebf055b77ceb093e476f0`、许可unknown，只读指定source-prep仓外原件；20项ID/URI/title/published与公开摘录一致，modified未知、article_body缺失。没有复制或在log打印完整description。公开6597B摘录仍明确metadata-only，20项事实字段+首条9词短引文，不假称完整原响应。未把完整原RSS加入候选，回放0网络/全文抓取，不计live来源或时效分母。

独占run的 `.gitattributes`只对本run的JSON/log/XML保留原字节；root复制按实际bytes逐文件hash。coverage二进制和cache不交付，复制收据自身单独保持字节一致。真实凭据及完整秘密扫描仍归主控；未读取env/key/holdout。

## 未检与下一步

本轮unit/相关contract/原Must2定向边界=passed。integration/frontend/e2e/live/manual均not_run；没有产品caller、真实来源增量/持续窗口/漏采参考集/PG事务/UI/全文质量/正式评分证据，不给这些项目通过结论。安全独立理由保持：R06卡允许R05不阻塞独立来源适配，此修复是纯bytes→DTO，无付费问答、数据库事务、模型或外部IO副作用；不能由此签G-C阶段或整R06。

独立WT创建、fixture复制和最初只读工具调用未额外捕获ISO秒级起止，标not_recorded，不推算时长；正式检查均有实测记录。没有未运行却写通过、删难例、降门或伪造live能力。

下一步由主控据本固定版本的有限意见决定内部合并，并继续独立采集集成及CPU诊断缺陷处理；本review不改状态、不push，任务到此停止。

**Verdict: Ship，限10c81f0内部parser批次；原Must 2关闭，整R06/G-C与项目CPU缺陷仍不由本报告验收。**

<!-- GENERATED_COMMAND_LEDGER -->

## 实际命令账本

每个标签链接到root副本的真实argv/cwd/ISO秒级+08:00/exit原件；同名log保留输出。

| 标签 | cwd | 开始 / 结束 | exit | 命令 |
|---|---|---|---:|---|
| [sync](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/sync.json) | `D:/wt/r06-feed-review-recheck2/backend` | 2026-10-15T19:29:55+08:00 / 2026-10-15T19:30:01+08:00 | 0 | `uv sync --frozen --offline` |
| [cbm_help](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/cbm_help.json) | `D:/wt/r06-feed-review-recheck2` | 2026-10-15T19:31:11+08:00 / 2026-10-15T19:31:13+08:00 | 0 | `wsl -d Ubuntu-22.04 -- /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp --help` |
| [mypy](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/mypy.json) | `D:/wt/r06-feed-review-recheck2/backend` | 2026-10-15T19:31:11+08:00 / 2026-10-15T19:31:25+08:00 | 0 | `uv run --frozen --offline mypy src` |
| [stdlib_source](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/stdlib_source.json) | `D:/wt/r06-feed-review-recheck2/backend` | 2026-10-15T19:31:11+08:00 / 2026-10-15T19:31:12+08:00 | 0 | `uv run --frozen --offline python -c 'import sys, inspect, email._parseaddr; print(sys.version); print(email._parseaddr.__file__); print(inspect.getsource(email._parseaddr._parsedate_tz))'` |
| [unit](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/unit.json) | `D:/wt/r06-feed-review-recheck2/backend` | 2026-10-15T19:31:11+08:00 / 2026-10-15T19:31:56+08:00 | 0 | `uv run --frozen --offline pytest tests/unit --junitxml=D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/unit.xml --cov-report=json:D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/unit_coverage.json` |
| [cbm_index](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/cbm_index.json) | `D:/wt/r06-feed-review-recheck2` | 2026-10-15T19:31:13+08:00 / 2026-10-15T19:31:21+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-recheck2-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r06-feed-review-recheck2/backend/src --name r06-feed-review-1-recheck2-src --mode fast --persistence false` |
| [format](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/format.json) | `D:/wt/r06-feed-review-recheck2/backend` | 2026-10-15T19:31:25+08:00 / 2026-10-15T19:31:25+08:00 | 0 | `uv run --frozen --offline ruff format --check .` |
| [ruff](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/ruff.json) | `D:/wt/r06-feed-review-recheck2/backend` | 2026-10-15T19:31:25+08:00 / 2026-10-15T19:31:25+08:00 | 0 | `uv run --frozen --offline ruff check .` |
| [cbm_schema](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/cbm_schema.json) | `D:/wt/r06-feed-review-recheck2` | 2026-10-15T19:32:04+08:00 / 2026-10-15T19:32:08+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-recheck2-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_graph_schema --project r06-feed-review-1-recheck2-src --format json` |
| [verify_evidence](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/verify_evidence.json) | `D:/wt/r06-feed-review-recheck2` | 2026-10-15T19:32:04+08:00 / 2026-10-15T19:32:16+08:00 | 0 | `python D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/verify_fixed_evidence.py` |
| [cbm_timezone_token](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/cbm_timezone_token.json) | `D:/wt/r06-feed-review-recheck2` | 2026-10-15T19:32:08+08:00 / 2026-10-15T19:32:12+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-recheck2-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project r06-feed-review-1-recheck2-src --function-name _timezone_token --direction both --depth 3 --format json --include-evidence true --max-output-tokens 7000` |
| [cbm_published_at](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/cbm_published_at.json) | `D:/wt/r06-feed-review-recheck2` | 2026-10-15T19:32:12+08:00 / 2026-10-15T19:32:16+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-recheck2-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project r06-feed-review-1-recheck2-src --function-name _published_at --direction both --depth 3 --format json --include-evidence true --max-output-tokens 7000` |
| [private_replay](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/private_replay.json) | `D:/wt/r06-feed-review-recheck2/backend` | 2026-10-15T19:32:16+08:00 / 2026-10-15T19:32:17+08:00 | 0 | `uv run --frozen --offline python D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/replay_private_source_metadata.py` |
| [code_equality](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/code_equality.json) | `D:/wt/r06-feed-review-recheck2` | 2026-10-15T19:32:30+08:00 / 2026-10-15T19:32:30+08:00 | 0 | `git diff --exit-code 9138e1741722491ca0c4df6b5540b76157a2b47e 10c81f0cda6b8065ebb9f1fef10c8459975c2d26 -- backend/src backend/tests` |
| [date_callers](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/date_callers.json) | `D:/wt/r06-feed-review-recheck2` | 2026-10-15T19:32:30+08:00 / 2026-10-15T19:32:30+08:00 | 0 | `rg -n '_timezone_token\|_published_at\|parse_trailofbits_rss' backend/src backend/tests` |
| [diff_check](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/diff_check.json) | `D:/wt/r06-feed-review-recheck2` | 2026-10-15T19:32:30+08:00 / 2026-10-15T19:32:30+08:00 | 0 | `git diff --check cb9e3c53f5504b7c6ed3b65e40ba0b92c124fd9f 10c81f0cda6b8065ebb9f1fef10c8459975c2d26` |
| [unit_contract_boundaries](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/unit_contract_boundaries.json) | `D:/wt/r06-feed-review-recheck2/backend` | 2026-10-15T19:32:30+08:00 / 2026-10-15T19:33:06+08:00 | 0 | `uv run --frozen --offline pytest tests/unit tests/contract/test_t12_vendor_blog_connectors.py tests/contract/test_t14_academic_connector.py tests/contract/test_r06_archived_feed_replay.py D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/test_independent_r06_feed_boundaries.py D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/test_timezone_repair_boundary.py D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/test_timezone_token_compatibility.py --junitxml=D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/unit_contract_boundaries.xml --cov-report=json:D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/unit_contract_boundaries_coverage.json` |
| [finalize](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/finalize.json) | `D:/wt/r06-feed-review-recheck2` | 2026-10-15T19:36:23+08:00 / 2026-10-15T19:36:23+08:00 | 0 | `python D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/finalize_recheck.py` |
| [own_format_apply](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/own_format_apply.json) | `D:/wt/r06-feed-review-recheck2/backend` | 2026-10-15T19:36:23+08:00 / 2026-10-15T19:36:23+08:00 | 0 | `uv run --frozen --offline ruff format --config D:/wt/r06-feed-review-recheck2/backend/pyproject.toml D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015` |
| [own_ruff](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015/own_ruff.json) | `D:/wt/r06-feed-review-recheck2/backend` | 2026-10-15T19:36:23+08:00 / 2026-10-15T19:36:23+08:00 | 0 | `uv run --frozen --offline ruff check --config D:/wt/r06-feed-review-recheck2/backend/pyproject.toml D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_review_1_recheck2_20261015` |

写作结束/证据截止：2026-10-15T19:36:50+08:00。
