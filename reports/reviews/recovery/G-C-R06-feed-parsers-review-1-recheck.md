# G-C / R06-A 独立初审1 · 定向复核

What this change does: 本轮只复核原三项Must的修复及其共同路径影响。新候选补充arXiv不足页拒绝、RSS数字时区范围检查，以及两个来源URI/许可入口的DEL拒绝；没有增加产品接线或全文抓取。

首次创建/写作开始：2026-10-15T19:11:21+08:00。写作结束/证据截止见文末生成收据。

审查者：`/root/r06_feed_parsers_independent_review`，沿用初审独立身份，未参与实现或本次修复。固定最终候选 **cb9e3c53f5504b7c6ed3b65e40ba0b92c124fd9f**；代码 **6b7dd7e881bb822e83b55f8302f7aefe565f4940**；原初审候选8e4d8a0。新独立detached WT为 `D:/wt/r06-feed-review-recheck`；作者WT未读取其正在变化的工作树作为通过证据，也未修改。候选tree=`160d283147d6cf379e6e8ef1be442b9e1e0191af`；src tree=`15b19b26f68838fcb62c362f0b7370fc311a1b7b`。

结论：**needs_changes，原Must 2仍未完整关闭；原Must 1与3关闭。不能Ship该固定候选。** 未修改业务/schema/锁/状态、未提交/push、未写accepted、未派子Agent；没有网络、付费调用、秘密或holdout读取。root已有未提交工作完整保留。本报告与独占run目录先写在独立WT，再按字节复制到root同路径，hash收据见 `artifact_copy_hashes.json`。

## 原三项复核结论

| 原编号 | 修复与本轮证据 | 结果 |
|---|---|---|
| 1 分页不足页 | `arxiv_atom.py:243–244`在既有范围检查后拒绝 `len(entries) < min(size,total-start)`。原total100/start0/size10/1entry负例、新增3种不足页及原空页/最后页/真实2篇回放都通过。保持冻结返回接口，不引入假游标成功。 | closed，仅本批parser |
| 2 非法数字时区 | `trailofbits_rss.py:97–102`只在时钟形状满足新正则时检查数字偏移；标准07:00:00 +1260原红例及作者新例已通过。但紧邻的标准库可接受形状07:00:0或7:0:0绕过该检查，非法+1260仍被换算为确定UTC。 | **Must仍保留** |
| 3 DEL控制字符 | `arxiv_atom.py:98/129`、`trailofbits_rss.py:79`补上U+007F拒绝。原RSS link/Atom licence两红例、作者feed id/entry/PDF/channel/article/GUID及普通许可文本新例全部通过。原安全未知许可identifier仍只保留文本，不赋予获取/再分发授权。 | closed，仅已冻结ASCII控制边界 |

原47例原断言未改，文件sha256始终为 `65b809db3152f99fdcc16dd7b2cff4fdbaaa050cc9ab57a21166c4425976e3fd`。本轮原1170全部通过，不能据此宣称修复边界已完整覆盖。

## Must fix · 沿用原编号2

2. **数字时区校验与下游日期解析器接受的时钟形状不一致**（`backend/src/ai_intel/ingestion/sources/trailofbits_rss.py:97–107`，P2）。

   What this is：新正则要求分钟及可选秒均为两位；未匹配时直接交给 `email.utils.parsedate_to_datetime`。后者接受单数字段，仍会把偏移的60分钟宽松折合成额外一小时。

   Problem：最小合成RSS如下，把秒由00改为0便可重现。期望整页 `FeedParseError`，实际 `published_at="2026-10-13T18:00:00Z"`。`Wed, 14 Oct 2026 7:0:0 +1260`有相同结果。两者都含原问题的非法+1260，并非新业务范围或真实来源观测；即使决定不支持这种时钟形状，也应显式拒绝，不能让它进入宽松下游解析。

   ```xml
   <rss version="2.0"><channel><link>https://blog.trailofbits.com/</link><item><title>Boundary article</title><link>https://blog.trailofbits.com/review/</link><pubDate>Wed, 14 Oct 2026 07:00:0 +1260</pubDate></item></channel></rss>
   ```

   Fix：让数字zone校验覆盖下游实际接受的时钟形状，或在进入下游前明确拒绝不支持的形状；校验应针对实际zone字段，保留已有合法偏移/GMT以及注释含+1260的原测试。继续复用标准库做日历与UTC换算，不引入日期框架、依赖或放宽失败合同。

   If we skip it：同一非法时区仍可进入确定发布时间，后续排序或延迟统计可能使用它。当前没有产品caller，未观察到真实上游产生该形状或实际时效指标受损；该影响是条件推论。此为原Must2未封住的共同根因，不能按“原4红变绿”关闭。

   精确复验文件：`test_timezone_repair_boundary.py`，仅新增2个合成用例；原始输入/实际输出见 `timezone_repair_observations.log`。预期断言为 `pytest.raises(FeedParseError)`，当前两个参数均 `DID NOT RAISE`。业务源码未改；没有改原47例、作者新增23例或任何已有预期。

## 亲自执行的门与计数

| 命令标签 | 开始 / 结束（+08:00） | exit | 实际结果 |
|---|---|---:|---|
| unit_combined | 2026-10-15T19:08:14 / 19:08:57 | 0 | 1170 passed、0failed/error/skipped；68.32%（6818 statements/2160 missed） |
| unit_combined_repair_boundary | 2026-10-15T19:09:32 / 19:10:07 | 1 | 1170 passed、2failed、0error/skipped；68.32%，失败仅为上面两例 |
| mypy | 2026-10-15T19:08:14 / 19:08:25 | 0 | 84 source files，无问题 |
| Ruff / format | 2026-10-15T19:08:25 / 19:08:25 | 0 / 0 | 整backend通过，208 files already formatted |
| verify_evidence | 2026-10-15T19:09:32 / 19:09:45 | 0 | 159个原证据Git blob与manifest字节/hash全部匹配；2个gzip解压原字节匹配；四业务/测试文件与6b7一致 |
| private_replay | 2026-10-15T19:09:45 / 19:09:45 | 0 | 指定991606B原RSS/sha256/20items，10元数据+2完整性断言，零网络/复制全文 |

第一行完整执行所有unit1109（含作者新增23）+相关T12/T14/archived合同14+原独立47。第二行在完全相同原集合上加2条同根因边界，没有改skip、原8秒超时、金标、分母或原60%覆盖门。两次中的原CPU忙子进程测试均通过，本轮没有重现其偶发TimeoutExpired；作者旧超时和17红历史保留，不宣称其宿主敏感根因已修复或替代主控另派诊断。

测试不是模型/Agent人工金标。两次各有1条既有FastAPI/Starlette弃用warning。全部正式命令argv/cwd/ISO秒级+08:00起止/exit与原日志在同名JSON/log；非pytest命令测试数为N/A。独立WT创建、fixture复制和最初只读文档工具调用未额外记录ISO秒级起止，记not_recorded，不推算为通过数量或耗时。

## 调用路径与范围核对

重新读取固定SHA的规范、执行图/状态和作者修复记录，复核原T12/T14/03/04/05/06/07合同在本修复范围的要求，不重开全项目审计。旧初审是8e4上的历史意见，新版本结果只由本轮证据支持。`git diff --exit-code 6b7 cb9 -- backend/src backend/tests`为0，159 blob核验中的四文件也逐blob相同。

独立CBM 0.11.0重新查看help，仓外缓存 `/tmp/dianzi-cbm-r06-feed-review-1-recheck-20261015`，仅索引 `/mnt/d/wt/r06-feed-review-recheck/backend/src`，不写仓内图。1125 nodes/5391 edges；not_indexed/partial/unusable/skipped均0。已运行schema、分页入口、日期函数、两个源完整qualified name的URI入口双向trace；图只含src，不声称测试也被索引。

源码与rg交叉核对：`parse_arxiv_atom`在调用 `_parse_record`前统一校验页计数；各feed/entry/author/PDF相关官方URI都经过该源 `_official_uri`。`parse_trailofbits_rss`将pubDate统一交 `_published_at`，channel/article/GUID等URL交RSS `_official_uri`；未知许可进入独立 `_license_identifier`，没有解引用。修复没有新caller/export/后台任务；两个parser仍只有tests/离线回放调用，未接API、worker、PG、UI，normalizer未变。图是辅助，源码与实跑决定结论。

G-B仍在审查时允许这次独立内部复核的理由保持：R06卡允许R05不阻塞独立来源适配；这些纯函数无付费问答或数据库事务副作用，本修复只改两个parser与相应测试。该独立性不等于穿越阶段门或验收整R06。没有公共DTO、依赖主版本、schema、锁、认证或指标合同变化。

## 原始样本、许可与封存

候选manifest的159文件/4790191B（不含manifest自身）全部逐Git blob核对，12个普通文本的Windows checkout转换另用Git filter核验；没有把checkout换行差异误报为封存失败。两旧大诊断gzip的解压原字节/hash也一致，旧红和失败历史未覆盖。

真实arXiv原Atom6101B（sha256 `8fd7cd6d0f71f5540d099047a778e813d67b1392a21e7c089bd49bc80a6bb3f1`）的2篇离线回放再次随合同通过；来源准备的CC0是元数据许可，不扩展到PDF。

Trail of Bits完整RSS为991606B，sha256 `86a1faac2d08bd01281efcb72ebb6c57a9a4213aa61ebf055b77ceb093e476f0`，许可unknown；只读指定source-prep私有原件，20项与公开摘录的ID/URI/title/published逐项一致，modified仍None、article_body缺失。私有回放输出只有hash与元数据断言结果，不复制完整description。公开摘录6597B、20项、首条9词短引文，仍明确标记metadata-only摘录，不假称完整响应；候选未加入完整 `doh_05_trailofbits_feed.body`。所有回放均是offline，不计live来源、持续监测或延迟分母。

## 交接与未检

本轮unit/相关contract=passed；原Must1/3关闭，Must2同根因边界=failed；integration/frontend/e2e/live/manual=not_run。本报告不验收整R06/T12/T14/G-C、PG/UI、持续采集、参考漏采集、正式性能或评分。真实凭据与完整秘密扫描仍由主控处理，未读env/key/holdout，不以未知或空结果冒充否定。

下一步只需原作者补齐原Must2日期输入边界，保留原47+新增2、原23和合法注释/GMT等测试，再冻结候选给同一独立reviewer定向复核。不修改原四红期望，不删除两个新负例，不靠重跑覆盖失败。审查者本轮到此停止，不等待修复或扩大补丁。

**Verdict: fix 2 first.** 仅针对cb9固定候选的内部parser修复；不写accepted或push。

<!-- GENERATED_COMMAND_LEDGER -->

## 实际命令账本

每个标签链接到root副本的真实argv/cwd/ISO秒级+08:00/exit原件；同名log保留输出。

| 标签 | cwd | 开始 / 结束 | exit | 命令 |
|---|---|---|---:|---|
| [sync](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/sync.json) | `D:/wt/r06-feed-review-recheck/backend` | 2026-10-15T19:07:49+08:00 / 2026-10-15T19:07:55+08:00 | 0 | `uv sync --frozen --offline` |
| [cbm_help](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/cbm_help.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:08:14+08:00 / 2026-10-15T19:08:15+08:00 | 0 | `wsl -d Ubuntu-22.04 -- /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp --help` |
| [mypy](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/mypy.json) | `D:/wt/r06-feed-review-recheck/backend` | 2026-10-15T19:08:14+08:00 / 2026-10-15T19:08:25+08:00 | 0 | `uv run --frozen --offline mypy src` |
| [unit_combined](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/unit_combined.json) | `D:/wt/r06-feed-review-recheck/backend` | 2026-10-15T19:08:14+08:00 / 2026-10-15T19:08:57+08:00 | 0 | `uv run --frozen --offline pytest tests/unit tests/contract/test_t12_vendor_blog_connectors.py tests/contract/test_t14_academic_connector.py tests/contract/test_r06_archived_feed_replay.py D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/test_independent_r06_feed_boundaries.py --junitxml=D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/unit_combined.xml --cov-report=json:D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/unit_combined_coverage.json` |
| [cbm_index](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/cbm_index.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:08:15+08:00 / 2026-10-15T19:08:23+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-recheck-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r06-feed-review-recheck/backend/src --name r06-feed-review-1-recheck-src --mode fast --persistence false` |
| [format](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/format.json) | `D:/wt/r06-feed-review-recheck/backend` | 2026-10-15T19:08:25+08:00 / 2026-10-15T19:08:25+08:00 | 0 | `uv run --frozen --offline ruff format --check .` |
| [ruff](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/ruff.json) | `D:/wt/r06-feed-review-recheck/backend` | 2026-10-15T19:08:25+08:00 / 2026-10-15T19:08:25+08:00 | 0 | `uv run --frozen --offline ruff check .` |
| [timezone_repair_observations](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/timezone_repair_observations.json) | `D:/wt/r06-feed-review-recheck/backend` | 2026-10-15T19:08:44+08:00 / 2026-10-15T19:08:45+08:00 | 0 | `uv run --frozen --offline python D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/check_timezone_repair.py` |
| [cbm_schema](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/cbm_schema.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:09:32+08:00 / 2026-10-15T19:09:39+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-recheck-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_graph_schema --project r06-feed-review-1-recheck-src --format json` |
| [unit_combined_repair_boundary](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/unit_combined_repair_boundary.json) | `D:/wt/r06-feed-review-recheck/backend` | 2026-10-15T19:09:32+08:00 / 2026-10-15T19:10:07+08:00 | 1 | `uv run --frozen --offline pytest tests/unit tests/contract/test_t12_vendor_blog_connectors.py tests/contract/test_t14_academic_connector.py tests/contract/test_r06_archived_feed_replay.py D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/test_independent_r06_feed_boundaries.py D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/test_timezone_repair_boundary.py --junitxml=D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/unit_combined_repair_boundary.xml --cov-report=json:D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/unit_combined_repair_boundary_coverage.json` |
| [verify_evidence](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/verify_evidence.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:09:32+08:00 / 2026-10-15T19:09:45+08:00 | 0 | `python D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/verify_fixed_evidence.py` |
| [cbm_paging](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/cbm_paging.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:09:39+08:00 / 2026-10-15T19:09:45+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-recheck-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project r06-feed-review-1-recheck-src --function-name parse_arxiv_atom --direction both --depth 3 --format json --include-evidence true --max-output-tokens 7000` |
| [cbm_date](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/cbm_date.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:09:45+08:00 / 2026-10-15T19:09:50+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-recheck-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project r06-feed-review-1-recheck-src --function-name _published_at --direction both --depth 3 --format json --include-evidence true --max-output-tokens 7000` |
| [private_replay](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/private_replay.json) | `D:/wt/r06-feed-review-recheck/backend` | 2026-10-15T19:09:45+08:00 / 2026-10-15T19:09:45+08:00 | 0 | `uv run --frozen --offline python D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/replay_private_source_metadata.py` |
| [callers_and_repaired_paths](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/callers_and_repaired_paths.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:10:12+08:00 / 2026-10-15T19:10:12+08:00 | 0 | `rg -n 'parse_arxiv_atom\|parse_trailofbits_rss\|_official_uri\|_license_identifier\|_published_at\|numeric_zone\|len\(entries\) < min' backend/src/ai_intel/ingestion/sources backend/tests/unit/test_r06_feed_parsers.py backend/tests/contract/test_r06_archived_feed_replay.py` |
| [cbm_arxiv_uri](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/cbm_arxiv_uri.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:10:12+08:00 / 2026-10-15T19:10:16+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-recheck-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project r06-feed-review-1-recheck-src --function-name r06-feed-review-1-recheck-src.ai_intel.ingestion.sources.arxiv_atom._official_uri --direction both --depth 3 --format json --include-evidence true --max-output-tokens 7000` |
| [diff_check](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/diff_check.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:10:12+08:00 / 2026-10-15T19:10:12+08:00 | 0 | `git diff --check 8e4d8a0a149980d92f972d510b6d8849298bcadb cb9e3c53f5504b7c6ed3b65e40ba0b92c124fd9f` |
| [cbm_rss_uri](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/cbm_rss_uri.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:10:16+08:00 / 2026-10-15T19:10:19+08:00 | 0 | `wsl -d Ubuntu-22.04 -- env CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-feed-review-1-recheck-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project r06-feed-review-1-recheck-src --function-name r06-feed-review-1-recheck-src.ai_intel.ingestion.sources.trailofbits_rss._official_uri --direction both --depth 3 --format json --include-evidence true --max-output-tokens 7000` |
| [all_source_callers](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/all_source_callers.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:10:38+08:00 / 2026-10-15T19:10:38+08:00 | 0 | `rg -n 'parse_arxiv_atom\|parse_trailofbits_rss\|arxiv_atom\|trailofbits_rss' backend/src backend/tests` |
| [source_commit_equality](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/source_commit_equality.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:10:38+08:00 / 2026-10-15T19:10:38+08:00 | 0 | `git diff --exit-code 6b7dd7e881bb822e83b55f8302f7aefe565f4940 cb9e3c53f5504b7c6ed3b65e40ba0b92c124fd9f -- backend/src backend/tests` |
| [finalize](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/finalize.json) | `D:/wt/r06-feed-review-recheck` | 2026-10-15T19:13:45+08:00 / 2026-10-15T19:13:46+08:00 | 0 | `python D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/finalize_recheck.py` |
| [own_format_apply](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/own_format_apply.json) | `D:/wt/r06-feed-review-recheck/backend` | 2026-10-15T19:13:45+08:00 / 2026-10-15T19:13:45+08:00 | 0 | `uv run --frozen --offline ruff format --config D:/wt/r06-feed-review-recheck/backend/pyproject.toml D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015` |
| [own_ruff](D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/own_ruff.json) | `D:/wt/r06-feed-review-recheck/backend` | 2026-10-15T19:13:45+08:00 / 2026-10-15T19:13:45+08:00 | 0 | `uv run --frozen --offline ruff check --config D:/wt/r06-feed-review-recheck/backend/pyproject.toml D:/wt/r06-feed-review-recheck/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015` |

写作结束/证据截止：2026-10-15T19:13:58+08:00。
