# G-C / R06-B · 仓库与社区适配器独立定向复核

评审人：`/root/r06_repository_community_independent_review`，原非作者 reviewer。**原 Must 1 在本冻结版本限定关闭；Verdict: Ship，仅限 R06-B 内部适配器及本次 null 修复。**本报告不登记 accepted，不签整 R06/T11/T13、G-C、产品接线或 live；Windows CPU 限额问题仍待独立修复。

文档首次创建：2026-10-15T19:23:22+08:00；最后更新时间：2026-10-15T19:23:54+08:00。
证据截止：2026-10-15T19:21:37+08:00。工作目录：`D:/wt/r06-repos-review-recheck`，新 detached worktree；建立前确认路径未占用，保护主控既有未提交文件，未修改作者 `D:/wt/r06-repos`。

| 版本 | SHA / tree |
|---|---|
| 本次完整代码及证据 | `84faff95c20cdf98e411875349d5e48960a478ad` / `976b5d572e12d82dbcc07a27bf7fe0bc859f551c` |
| 修复代码 | `d4e22fab7ad4be7bb6281d5d8dd9db3ea53729a6` / `323e2bc94baadb6052e88278a3571a8c03291d3c` |
| 原 Must 版本 | `5e952f25d7a1c03296e1a8801a757c9c0317af99` / `c99ba0178c781e3d48555b5ddbd8d9743c420d8a` |
| 原项目基线 | `1ff54965a0dd2e4f4a13245cee8dd59d2b3fdcfc` |
| 本轮 diff | `git diff 5e952f25d7a1c03296e1a8801a757c9c0317af99 HEAD` |
| 独立 run | `reports/runs/recovery_r06_repository_community_review_1_recheck_20261015/` |

What this change does: OSV 两个数组 helper 现在只接受 list。允许缺键的 caller 提供默认空列表，显式 JSON null 仍由严格类型边界拒绝；不修改原始输入，也不改变旧范围分支及关系语义。

## 1. 原 Must 1 的输入、修复与关闭证据

原触发输入 `{"id":"OSV-REVIEW","affected":[{"ranges":[{"type":"SEMVER","events":null}]}]}` 返回空 events 且 unsupported_scheme=false。预期是 `OsvContractError`；同根因还涉及 aliases/related/upstream/affected/ranges/versions，原 reviewer 七个拒绝断言两次稳定失败，原日志与初审报告仍保留。

本次逐行核对 `backend/src/ai_intel/ingestion/sources/osv.py:67`、`:91`：移除两个 `None → 空集合` 分支，仅允许 list；七个缺省 caller 位于 `:118–120`、`:125`、`:138`、`:143`、`:159`，均明确 `.get(field, [])`。`bounded_package_query:192` 是 `_objects` 的另一 caller，既有结果 list 校验保留，坏第二条记录不会被过滤掉。此次只有 osv.py 与其既有 unit 文件改变，d4e22fab→84faff95 的 backend diff 为空。

原独立25项测试直接按原字节复制到本轮 run，SHA256 `ac8d997b0bbfa85d9d1f44b88b6d7f00dc0b5cdcfd27531e423477acca3b9491`，与原 reviewer 文件、作者提交的 `null_fix_independent_boundaries.original.py` 及 provenance 完全一致；没有修改断言、fixture、阈值或金标。原七条现在全部抛出预期异常。新增13项作者测试覆盖七类显式 null、顶层/嵌套缺键、显式空数组、SEMVER/GIT/FUTURE 第二分支的 null 整条失败，全部通过；缺键与原 raw 没有被补出假字段。

**关闭理由：**触发输入、错误分类与全部受影响 caller 均有源码和可观察断言支持，原25项、新增13项、原 T11/T13 合同及相关回归通过。并非用作者通过日志、覆盖率或改预期代替原拒绝断言。没有新增确认缺陷或需先修的范围内缺测项。

## 2. 新版本调用链与安全独立边界

AGENTS、执行图、原 T11/T13 引用合同、manifest、progress 和 pyproject/lock 相对原 Must 版本均未改变；沿用初审已完整阅读的 03/04/05/06/07 与 Ponytail 5.2 review/full，并重新核对 R06 当前卡、状态及作者新增修复报告。冻结状态仍将 R06 记 pending，历史验收记录不作为当前产品能力证明。

在 WSL Ubuntu-22.04 实际核对官方 portable CBM0.11.0 help，重新建立本次源码图，读取 schema/diagnostics 后 trace `_objects`、`_string_tuple`、`normalize_osv_record`、`bounded_package_query`，再用 `rg` 全 src/tests 核对实际调用点。索引仅 `/mnt/d/wt/r06-repos-review-recheck/backend/src`，独立仓外缓存 `/tmp/dianzi-cbm-r06-repository-review-1-recheck-20261015`，项目 `dianzi_r06_repos_review_1_84faff9`：1103 nodes / 5361 edges；not_indexed/partial/unusable均0，无复用旧图。

`_string_tuple` 唯一源码 caller 为 normalizer，含4个调用点；`_objects` 两个 caller 为 normalizer 与 bounded query，含3+1个调用点。后两函数均无产品源码入边，和 rg 结果一致；未将源码图零测试边等同于没测试。完整 trace/schema、caller日志保存在本轮 run。

本批仍是纯适配：不改 source_jobs/source_documents、PG事务、迁移、认证、API、UI、状态权威或预算。因此这项 null 修复与当前 G-B 事务修复可以安全独立合并审查；两个批次彼此的通过不证明对方正确。新 DTO 未返回 release flags/body/canonical URI 与社区时间精度、全部原始引用，主控接线时仍必须持久化和读取完整原文；不能只保存 DTO、把 date-only 补午夜、把 prerelease 的显示名称当稳定版本，或从空引用列表推断无风险。

## 3. 独立复跑的真实结果

本轮建立新仓外离线环境 `D:/dianzi-runtime-cache/r06-repository-community-review-1-recheck/venv`，Python3.12.13，uv frozen/offline sync，editable包指向本次冻结 WT。未新增依赖/锁改动、联网、付费、主动读取秘密/env/DPAPI/holdout、运行外部PoC或再派agent。

测试命令为该环境 `python -m pytest tests/unit tests/contract/test_t11_osv_connector.py tests/contract/test_t13_community_repository_connectors.py tests/contract/test_r06_repository_source_samples.py tests/security/test_t08_network_and_sources.py tests/security/test_r03_network_transport.py ../reports/runs/recovery_r06_repository_community_review_1_recheck_20261015/test_independent_boundaries.py --junitxml=../reports/runs/recovery_r06_repository_community_review_1_recheck_20261015/unit_contract_security_independent.junit.xml`。

| label / cwd | 实际开始 | 实际结束 | exit / 结果 |
|---|---|---|---|
| environment_sync / WT | 2026-10-15T19:16:45+08:00 | 2026-10-15T19:16:51+08:00 | 0，frozen/offline |
| unit_contract_security_independent / WT/backend | 2026-10-15T19:17:11+08:00 | 2026-10-15T19:17:50+08:00 | 0，1250 pass / 0 fail / 0 error / 0 skip |
| mypy / WT/backend | 2026-10-15T19:17:11+08:00 | 2026-10-15T19:17:21+08:00 | 0，84源文件 |
| ruff / WT/backend | 2026-10-15T19:17:21+08:00 | 2026-10-15T19:17:22+08:00 | 0，两改动文件 |
| format / WT/backend | 2026-10-15T19:17:22+08:00 | 2026-10-15T19:17:22+08:00 | 0，两改动文件 |
| cbm_help / WT | 2026-10-15T19:17:11+08:00 | 2026-10-15T19:17:12+08:00 | 0 |
| cbm_index / WT | 2026-10-15T19:17:13+08:00 | 2026-10-15T19:17:20+08:00 | 0，独立src-only索引 |
| cbm_schema / WT | 2026-10-15T19:18:05+08:00 | 2026-10-15T19:18:09+08:00 | 0 |
| cbm_trace__objects / WT | 2026-10-15T19:18:09+08:00 | 2026-10-15T19:18:13+08:00 | 0 |
| cbm_trace__string_tuple / WT | 2026-10-15T19:18:13+08:00 | 2026-10-15T19:18:17+08:00 | 0 |
| cbm_trace_normalize_osv_record / WT | 2026-10-15T19:18:17+08:00 | 2026-10-15T19:18:21+08:00 | 0 |
| cbm_trace_bounded_package_query / WT | 2026-10-15T19:18:21+08:00 | 2026-10-15T19:18:25+08:00 | 0 |
| raw_evidence_integrity / WT | 2026-10-15T19:18:16+08:00 | 2026-10-15T19:18:21+08:00 | 0，样本/原失败gzip核验 |
| repair_provenance / WT | 2026-10-15T19:19:33+08:00 | 2026-10-15T19:19:43+08:00 | 1，reviewer误将普通task报告当作-text raw，见下节 |
| repair_provenance_recheck / WT | 2026-10-15T19:20:56+08:00 | 2026-10-15T19:21:09+08:00 | 0，严格raw核验及普通报告换行核验 |
| frozen_diff_check / WT | 2026-10-15T19:19:33+08:00 | 2026-10-15T19:19:33+08:00 | 0 |
| public_pattern_scan / WT | 2026-10-15T19:19:33+08:00 | 2026-10-15T19:19:33+08:00 | 1，rg0匹配，26改动文件 |
| reviewer_ruff / WT | 2026-10-15T19:21:26+08:00 | 2026-10-15T19:21:26+08:00 | 0，本轮4个脚本 |
| reviewer_format / WT | 2026-10-15T19:21:26+08:00 | 2026-10-15T19:21:27+08:00 | 1，reviewer校验脚本一行格式 |
| reviewer_format_recheck / WT | 2026-10-15T19:21:37+08:00 | 2026-10-15T19:21:37+08:00 | 0，仅格式化本人脚本，原25文件未动 |

1250=1102 unit+15 contract（T11六项、T13六项、真实样本三项）+108 network/source security+25原独立检查。原60覆盖率门保留，实际70.83%，6818 statements/1989 missed；删除两个缺省分支自然减少4个代码statement，不是改评分分母或阈值。唯一warning是既有StarletteDeprecationWarning。所有精确argv/cwd/ISO秒级起止/exit及日志、JUnit在对应命令证据中；不将作者1250日志计作本轮结果。已有检查通过后不重复扩大测试。

## 4. 原始样本、历史失败与新旧冻结证据

原64个run Git blob与5e952逐字节相等；新23个run文件与当前Git blob/checkout逐字节相等。加上修订的task报告，此轮证据共24项文件变动。旧 `evidence_commit_inventory.json` 的64条目全部按5e952 Git blob核验；其中旧报告hash只核旧版本，未错误要求旧hash等于新报告。新 `null_fix_inventory.json` 有23条目，覆盖22个run文件和更新报告，不自哈希；inventory自身作为第23个新run Git blob另行核验。

新 provenance 的代码SHA/tree、原25文件SHA、1250记录和修订报告raw hash全部匹配。新task报告普通Git文本采用LF，而Windows checkout为CRLF：raw19888bytes、SHA256 `1c8613c5fb8a2af4da88cfb2bd3a2ae4babf958159fd3eacd28351e3a0f96483`；Git blob19747bytes、SHA256 `56bfbc051b937a2369defcc5d9efb67d7dd63bdc3bcb9ef0487acba6e01c15f5`。按仅该普通task报告的CRLF规则比较后内容完全相同。reviewer首次把它与-text原始响应作相同byte比较造成exit1，保留原失败日志；随后修正校验范围，记录两哈希。所有run原始响应/日志/record/gzip始终严格逐字节核验，未修改证据或放宽全仓属性。旧报告SHA256仍为 `9b718c5cc3174e2ce7a2c3c59160ee51bfc6c581b767d3da1162957f8ad492e2`。

AVID两个API blob base64解码与原正文相等，Git blob SHA1仍为 `00fb8988850933aa6b17933990a5a02bdc26f828` / `5e9419c9bfce72868a5e9ea32314d6fbae293f72`，原metadata SHA256/尺寸一致。Ollama/OSV原始字节与已审准备包仍相等。日期仍是AVID date-only与release/OSV原始有时区字符串；真实release id/flags/body与原OSV纳秒字段、aliases/ranges的原断言通过。许可范围沿用初审准备包官方AVID MIT来源说明，没有新联网确认，也没有将原作引用内容视为全量公开再分发许可。

亲自再展开原17,016,093bytes失败日志及4,484,295bytes JUnit的gzip，原文与归档双hash/尺寸、作者WT仍保留的未跟踪原文件再次一致；原失败内容没有被删除或覆盖。作者本轮null_independent_red保留7 fail/18 deselected、原拒绝断言名称完整；作者绿灯不是用删除旧红例得到。详见 `evidence_verification.json`、`repair_provenance_verification.json`、`report_newline_difference.json`。

public pattern检查只是公开格式扫描且0匹配，不代替root的实际秘密逐值扫描；本reviewer没有读取实际秘密。run局部-text/cr-at-eol继续只保护本run原字节，业务文件检查未关闭。

## 5. 未检、CPU诊断、评分证据与交接

本轮既有CPU1秒/8秒负例通过，不能关闭 [G-C-native-cpu-limit-diagnosis.md](G-C-native-cpu-limit-diagnosis.md) 已确认的Windows缺陷：Job1秒配置读回正确，但受限worker在约8秒时已累计7.703125秒用户CPU仍active。该诊断不是“资源不足导致没用满1秒”的猜测；本轮没有改8秒timeout/skip/原limiter，也没有独立复验或修复其内核终止保障。适配器不调用limiter/PDF/semantic worker，所以本null修复可限定Ship；整个G-B/G-C工程门必须继续保留CPU缺口。

未检：PG raw→revision→outbox/cursor事务与并发、SourceKind注册/产品worker、新源真实分页/权限/429/回补/持续运行、API/UI/frontend/e2e、真实模型、live/性能/正式评测/人工。这些仍为not_run或整卡既有blocked；没有产品caller不能被写成来源能力已接线。主控持久化原文、日期精度、release flags/body等要求不变。

本轮没有计划/公共合同/认证/依赖主版本/阈值/金标/评分分母偏差。F1/F2/E1只补证内部严格解析与原始证据保存，P1持续时效和P2资产研判/准确率没有新增验证；不签整R06/T11/T13或阶段通过。reviewer仅交付此报告与自己的run，未修改业务、shared、progress，未push/accepted。

下一步：root完成实际秘密扫描后，可以按本限定意见集成84faff95；继续独立处理CPU修复、产品原文持久化及来源接线，待相关事务/live证据齐全再进入阶段验收。

**原 Must 1：关闭（仅本冻结内部适配器范围）。Verdict: Ship.** Not checked：产品入口/live和CPU修复仍未证明；该限定结论不覆盖这些门。
