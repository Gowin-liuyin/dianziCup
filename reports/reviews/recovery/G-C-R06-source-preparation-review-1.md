# R06 来源准备包独立审查 1

What this change does: 本包新增八类×九通道来源草案、两批公开 GET 留档及离线样本检查。它为后续适配器提供输入证据与待冻结事项，没有接通新源产品链路，也没有推进 R06 或阶段状态。

审查编号：G-C-R06-source-preparation-review-1。结论：**Ship，仅 docs-only 来源准备范围**。准备包仍由主控处理 awaiting_review；本报告不写 accepted，不批准草案公共接口/分类变更，不为整 R06、G-B 或 G-C 签字。未发现需要返工的准备包 confirmed 缺陷。

## 冻结版本、独立性与范围

| 项目 | 实际值 |
|---|---|
| 审查提交 | `e4f20b0bf74ec8781bd1e5cede96daa6341c101d` |
| 审查 tree | `488a71d2b533d6539263d31331c3992347b78fc2` |
| 唯一父提交/基线 | `23c18784d71f1ed788072e6b3f2af70bac94fcb1` |
| 基线 tree | `ee04d6d1d9f977aed9449db249da9527a086bcef` |
| 作者 WT | `C:/Users/yinha/.codex/worktrees/r06-src/dianzi` |
| 独立审查 WT | `D:/wt/r06-prep-review`，detached HEAD；创建前路径不存在 |
| 真实环境 | 独立 WT 的 `.venv`，CPython 3.12.13；`uv sync --offline --frozen` 安装已有锁中的 69 包 |
| 审查日志 | [review run](D:/dianzi/reports/runs/recovery_r06_source_preparation_review_1_20261015/commands.jsonl) |

本审查者非作者，未继续派代理。采用 [Ponytail 5.2.0 review full](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)，按正确性、安全、预期负载、测试、速度和必要性检查；full 不削减约定范围。预期负载只是一名操作人顺序执行的有界准备批次，不能据此签多 worker 持续运行。

已读 `D:/dianzi/AGENTS.md`，目标 SHA 的 `00_execution_map.md`、恢复计划 §6.1、R06 卡、原 T08/T11–T16 卡及其 03/04/05/06/07/09 引用合同，以及冻结 task_state/context_handoff。进度中 R06 是 pending/not_started、各验证 not_run，recovery_stage 为 G-B；旧 T 卡/旧交接中的 accepted 不当作本轮验收。

基线到目标共 **117 个新增路径**，全部落在 `docs/design/recovery/r06_source_matrix_draft.md`、`reports/tasks/R06-source-preparation.md` 与其同名 run 目录。`backend/config/contracts/progress/fixtures` 差异为空。离线复跑 `inspect_samples.py` 会重写它的两个派生文件，但最终 Git status 仍为空，字节相同；没有覆盖原始来源历史。

本审查只写本报告及 `reports/runs/recovery_r06_source_preparation_review_1_20261015/`。未读 `.env`、密钥文件或 holdout，未访问网络/收费 API，未执行 PoC、写 PG、改业务/shared 状态、commit 或 push。

## G-B 未过门时为何可安全独立继续

执行索引要求跨阶段保留检查点；本次不是以 R06 产品开发越过 G-B，而是主控明确授权的准备包审查。R06 卡原文明确“R04；R05不阻塞独立来源适配”，本包实际又比适配更窄：仅冻结源码、公开响应字节、文档提案与离线解析。

它不依赖 R05 的生成/向量/问答结果，不把样本写入 PG、检索或演示，不修改认证、SourceKind、枚举、指标分母或任务状态。作者两批请求的每源 1 attempt、0 重定向、15 秒/2MiB 上限可从日志交叉核对；本 review 不新增请求。原 live 阻塞、阶段门和整卡六类验收保留。因此本包可以作为只读离线准备独立流转，不能作为启动无界采集、正式测评或接受 G-C 的许可。

## 八类、九通道与实际内容

矩阵恰好 8 个 canonical 类别、9 个业务通道，和冻结 `SourceCategory` 一致。C2 的 OSV/GHSA 只归结构化漏洞，不再同时凑社区；C3 的 vLLM 公告与 Ollama release 分别依实际内容归厂商/仓库。KEV/EPSS 是辅助富化，国内通道未核实仍待核实，ATLAS 不替代标准/政策。别名、转载、论文版本和多个入口不增加类别。

| 源 | 独立读取完整响应后确认的内容 | 计数与能力限制 |
|---|---|---|
| OSV | GHSA-fccc-8m69-8r78，CVE-2025-0315/GO-2025-3557，Go 包 github.com/ollama/ollama；schema_version 1.9.0 | 只取得单 ID；没有包 query POST 或自动发现 |
| vLLM | GHSA-6cxc-2vcg-w5qc，state=published，html_url 是 vLLM 仓库官方 security advisory | 探测 per_page=1；产品 `source_page_url` 当前 per_page=10。样本不能冒充产品 PG 接线 |
| AVID | 两项 type=dir：vulnerabilities/2022、vulnerabilities/2023，含 tree SHA | **只有目录发现，没有漏洞正文**。不能确认单件 schema/发布日期，也不能由年份判断全面停止更新 |
| Ollama | release 413093320，v0.40.5-rc0，prerelease=true，draft=false，target_commitish=main | 浮动 main 不是固定提交 SHA；release 不等于漏洞/修复已经确认 |
| Trail of Bits | RSS 20 项，description 含内容；包括 AI 审计、AI patching benchmark 分析标题 | 有限 feed 快照；独立正文获取、历史回补与再分发授权未证明 |
| arXiv | 2609.05903v2、2610.19452v1；OpenSearch totalResults=1065，只返回两项 | 不是 1065 项全量。v2 的 published 仍为首发时间，updated 是版本更新时间；未取全文 |
| NIST | AI100-1 / AI RMF 1.0 PDF，48 个物理页文本块，pdf-2.0.0 parsed；voluntary 在物理页 7/26/47 出现 | **自愿技术框架，不能硬说正式强制标准或法律义务**。标准计分类别尚待冻结，图表完整性未人工核验 |
| CAC | BodyLabel 中第15号、2023年7月10日签署和2023年8月15日起施行；pubtime 是2023年07月13日15:00 | 网页时钟无显式时区；签署/生效是 date-only，不能填午夜或抓取时间。当前适用性没有法律研判 |

NIST 离线规范文本 SHA256 为 `33ff9e31cb19e9e9c5c09de333adee238805f11dbee6b5d7e95f6af3bfc91d0f`，与作者派生结果相同。八份原始响应总计 **3,015,622 bytes**。

## 16 attempt 的身份、时间和字节审计

独立脚本把两个 summary、16 个单件 metadata、两条 stdout 批次记录、实际 Windows argv/cwd、源 URL、时间、原文字节和提交 blob 全部交叉核对。36 条作者 command 的 72 份 stdout/stderr SHA256 与目标提交 blob 相同；8 份 source body 也与提交 blob 完全相同。不是只运行作者自检后相信其结论。

第一批使用 `D:/dianzi/backend/.venv/Scripts/python.exe`，cwd 为作者 WT，`2026-10-15T17:24:37+08:00` 开始/结束，system DNS **8 次 NetworkPolicyViolation**；status/header/body/hash/bytes 全部 null，没有 body 文件。它是 Windows 调用，不能改称 WSL HTTP 失败。脚本 exit0 仅表示留档成功，不表示网络通过。

第二批使用作者 WT 自有 Windows `.venv/Scripts/python.exe --resolver cloudflare_doh`，同 cwd，`2026-10-15T17:27:55+08:00` 至 `2026-10-15T17:28:09+08:00`，8 次 HTTP200，脚本 exit0。每份 attempts=1、max_response_bytes=2097152、timeout=15、redirect_hops_allowed=0、credentials_used=false、is_synthetic=false；敏感响应头若存在均为 REDACTED。

| source | 起止（均 2026-10-15 +08:00） | bytes | 耗时秒 | 独立重算的 body SHA256 |
|---|---|---:|---:|---|
| doh_01_osv_ollama | 17:27:56 → 17:27:57 | 1403 | 1.484 | `88f1a1b11217d64b92220f4fba6fc22c9ec8f75e36ed7dd9b17c38d2f7a2ce8e` |
| doh_02_vllm_vendor | 17:27:57 → 17:27:59 | 8800 | 1.469 | `f084ddcb1eecd43494ac0244dd3b650431727add18deb330bc3df1722912cedf` |
| doh_03_avid_community | 17:27:59 → 17:28:00 | 1387 | 1.234 | `38b6aa04da36751af80d74c07cd0aa46a2e6ab6ba351ce0572b56e2ed45ca3c9` |
| doh_04_ollama_release | 17:28:00 → 17:28:02 | 30767 | 2.391 | `a1b9f1508600e196230a37afc05d6ff8666aa3a6363d28ca32ee2e2789044173` |
| doh_05_trailofbits_feed | 17:28:02 → 17:28:04 | 991606 | 1.562 | `86a1faac2d08bd01281efcb72ebb6c57a9a4213aa61ebf055b77ceb093e476f0` |
| doh_06_arxiv_ai_security | 17:28:04 → 17:28:05 | 6101 | 1.172 | `8fd7cd6d0f71f5540d099047a778e813d67b1392a21e7c089bd49bc80a6bb3f1` |
| doh_07_nist_ai_rmf | 17:28:05 → 17:28:08 | 1946127 | 2.641 | `7576edb531d9848825814ee88e28b1795d3a84b435b4b797d3670eafdc4a89f1` |
| doh_08_cac_generative_ai | 17:28:08 → 17:28:09 | 29431 | 1.265 | `7fae988c064dde72c95e96e5727bf9abee4b3a5a1ea817606a9ca1f97ffac54b` |

完整 ISO 秒级时间及身份见 [独立审计 JSON](D:/dianzi/reports/runs/recovery_r06_source_preparation_review_1_20261015/independent_evidence.json)。arXiv final_url 把 `%20` 规范为 `+`，解析后的 origin/path/query 相同，原 URL fingerprint 仍匹配；不是重定向。DoH 另有 A/AAAA 解析流量，16 只计来源 attempt，不计全部网络包。

本 review 禁止重新联网，因此确认的是冻结日志、内容、边界和字节一致性，没有第二次现场观察上游响应。哈希一致不能独立证明远端发布者真实性；发布者判断同时依 URI、内容身份和已有官方研究。

## 源码调用链、配置和最小设计

使用官方 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` 0.11.0，先实际读取 top-level/cli/index/schema/trace help。独立 `CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-prep-review-1-20261015` 在仓外；只 index 本 WT/backend/src，fast **1081 nodes / 5195 edges**，not_indexed/skipped/partial/unusable 均 0。get_graph_schema 和 7 次 trace_path 全部 exit0。未加载作者 cache 或索引 holdout。

| 草案判断 | CBM + 源码 + 独立 rg 核对 |
|---|---|
| 产品只支持两个来源 | `source_jobs.py:57` 的 SourceKind、`source_documents.py:58/82` 定义及 route 参数仅 nvd_ollama/vllm_vendor；`runtime.py:92` 接 build_source_page_handler |
| 两源真实路径可复用但非通用 | `source_jobs.py:295–299` 固定两域 JSON；nested collect_page 的 335/339/346 行先建固定 URL、persist、计算下一页，再页事务提交。CBM 的 nested caller 只是 heuristic，已读源码确认 |
| 新源 normalizer 无产品 caller | OSV/feed/repository/academic/policy 5 个 trace 的 callers=0；全 backend/src rg 只找到定义，源码没有 XML/新源接线 |
| 原文路径事件耦合 | `_PreparedDocument.external_ids` 只允许 cve/ghsa，prepare/persist 走 EventSubmission/知识事实；非漏洞 paper/standard/policy 需要先冻结实体存储，不强造漏洞身份 |
| OSV 分支风险 | `osv.py:93–117` 把多个 ranges 的 events 合并，只留末个 ranges_type；raw_record 保留。草案明确此限制，不能按31 fixture通过认定 R11 完整区间合同已满足 |
| 旧协议不足 | `connectors.py:15/22` 只有 fetch_document；05合同 §5 有 discover/fetch/normalize/probe，草案准确标明差异 |
| 配置别名/UUID | academic/standards/policies/blog/community/repository 的6个 category别名确与 canonical 不同；vendor合法。vendor/standards/policies/repository 的4个示例ID含非hex字符；其余 a/b/c 示例ID是合法hex |

七 YAML 的 origin 都是 example.invalid，capability_status 都是 configured_not_live；注册模板另为同类示例，不能计真实来源。草案没有自行扩枚举、替换历史 source_id 或执行迁移。

设计沿用四段 connector 与 PG 游标/租约/outbox 权威，输出 raw 引用/hash、稳定 ID、分页完结状态、时间原值/精度/未知状态；normalizer 不写 Claim/Assessment 或调用 LLM。按来源增加小型纯转换，公共持久化和路由交一个集成人，没有新 BaseService、通用 CRUD 或第二套业务状态库。

时间与分页提案保留关键限制：OSV 纳秒 raw；GitHub Link 数字仓库路径与不透明 after 不能当任意 URL；release created/published 分立且缺 modified；RSS RFC822 -0400 明确，20 项有限窗口；arXiv 版本、首发/更新和排序位移分立；NIST HTTP Last-Modified 不作发布日期；CAC date-only/缺时区保持未知。不把缺失、空页、失败、304、draft、撤回或权限不足统成成功。

许可/配额提案保守区分上游记录、代码仓库许可证与正文再分发；GitHub 三源共享匿名预算，论文元数据与全文分离，未知转载权限不发布正文。本 review 未重复联网核验未留存的官方 API/许可证网页，故 OSV 当前配额、arXiv CC0、AVID MIT、最新 API 示例日期等研究声明仍须主控冻结时按官方快照核验，不能作为已取得全面再分发授权。样本 header 可直接确认 GitHub limit=60 与 selected API=2022-11-28。

## 实际复跑与退出码

全部命令精确 argv、cwd、起止 ISO 秒级 +08:00、exit 和 stdout/stderr hash 保存在 [commands.jsonl](D:/dianzi/reports/runs/recovery_r06_source_preparation_review_1_20261015/commands.jsonl)，完整展开表见 [command_summary.md](D:/dianzi/reports/runs/recovery_r06_source_preparation_review_1_20261015/command_summary.md)。下表 W=`D:/wt/r06-prep-review`，B=`W/backend`；时间均完整 +08:00。

| 命令/标签 | cwd | 起止 | exit | 真实结果/计数 |
|---|---|---|---:|---|
| git worktree add --detach W e4f20b0… | D:/dianzi | 2026-10-15T18:05:24+08:00 → 2026-10-15T18:05:28+08:00 | 0 | 路径不存在后创建；detached |
| uv sync --offline --frozen | B | 2026-10-15T18:08:30+08:00 → 2026-10-15T18:08:37+08:00 | 0 | 本地缓存，69包；未网络下载 |
| codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r06-prep-review/backend/src --name r06-prep-review-1 --mode fast | W | 2026-10-15T18:07:21+08:00 → 2026-10-15T18:07:27+08:00 | 0 | 1081节点/5195边，4类缺失计数0 |
| get_graph_schema --project r06-prep-review-1 | W | 2026-10-15T18:07:59+08:00 → 2026-10-15T18:08:02+08:00 | 0 | schema 29项，无has_more |
| 7×trace_path --direction both --depth 2 --limit 50 --max-output-tokens 2200 --include-evidence true | W | 2026-10-15T18:08:03+08:00 → 2026-10-15T18:08:24+08:00 | 全0 | 2产品链+5未接线normalizer；不计测试 |
| check_preparation.py（own env） | W | 2026-10-15T18:09:25+08:00 → 2026-10-15T18:09:25+08:00 | 0 | 8×9、16attempt、36command、31JUnit及coverage失败一致 |
| inspect_samples.py（own env） | W | 2026-10-15T18:09:25+08:00 → 2026-10-15T18:09:26+08:00 | 0 | 8份完整性+8源形态；offline，0网络/0PG |
| Python -m pytest T11/T12/T13/T14/T15五合同文件 -q --junitxml=review_run/baseline_source_contracts.xml | B | 2026-10-15T18:09:26+08:00 → 2026-10-15T18:09:32+08:00 | **1** | **31 passed / 0 failed / 0 error / 0 skip；coverage9.32% < 60%，命令failed** |
| Python -m pytest tests/security/test_t08_network_and_sources.py -q --junitxml=review_run/t08_security_contracts.xml | B | 2026-10-15T18:09:32+08:00 → 2026-10-15T18:09:34+08:00 | **1** | **8 passed / 0 failed / 0 error / 0 skip；coverage10.15% < 60%，命令failed** |
| audit_saved_evidence.py（格式/自检修正后） | W | 2026-10-15T18:15:39+08:00 → 2026-10-15T18:15:44+08:00 | 0 | 117限定路径、16attempt、8body+72stream提交blob、内容/时间/UUID/JUnit交叉 |
| ruff check / format --check 作者run | W | 2026-10-15T18:11:52+08:00 → 同秒 | 各0 | 4个Python留档文件；不计全backend新增检查 |
| git diff --check baseline target | W | 2026-10-15T18:11:52+08:00 → 同秒 | 0 | 冻结完整docs diff；局部 -text/-diff 仅原始留档，hash已另核 |
| git diff --name-only baseline target -- backend config contracts progress fixtures | W | 2026-10-15T18:14:44+08:00 → 同秒 | 0 | 输出为空，无保护范围改动 |
| git status --porcelain=v1 --untracked-files=all | W | 2026-10-15T18:15:44+08:00 → 同秒 | 0 | 输出为空，审查 WT 干净 |
| ruff check / format --check 审查audit脚本（confirmed） | W | 2026-10-15T18:19:04+08:00 → 同秒 | 各0 | 自身脚本lint/format均通过 |

五合同文件实际为 `tests/contract/test_t11_osv_connector.py`、`test_t12_vendor_blog_connectors.py`、`test_t13_community_repository_connectors.py`、`test_t14_academic_connector.py`、`test_t15_standards_policy_connectors.py`。没有 `--no-cov`、改阈值、删除难题或更改分母；两个 coverage 文件隔离存放在 review run。断言通过不将整个 pytest 命令改列 passed。

本 review ledger 共46条命令，worktree创建另1条。没有全backend类型/格式检查、完整unit回归或数据库集成复跑；本包没有业务diff，这些项目列未运行，不按已有结果填passed。

复跑初始曾借作者冻结 env，但 PYTHONPATH 指向独立 WT；随后离线创建 own env 并重新跑两脚本和所有上述合同，最终结论采用 own env。审查工具失败均留档：最初尚不存在 WT 的 cwd 导致工具未启动shell；独立审计01错误要求 arXiv final_url 字符串完全相等，02错误要求OSV package字典不能有合法purl扩展，03错误预期CAC原文日期用ISO拼写，名为final的04遇到Windows默认GBK解码；这些是审查脚本问题，不是来源/产品缺陷。按已读源码/原文改为同URI语义、指定关键字段、原文拼写和UTF-8后05及verified运行通过。审查脚本lint的re.I规则及随后长行format问题只在自身run修正，红日志未删除。

## confirmed、缺测与推测的区分

**Confirmed 准备缺陷：0。** 没有 Must fix / Should fix 编号项，也没有为了缩短实现建议删掉原验收范围。作者关于 AVID、NIST、per_page差异、API版本、fixture与coverage的关键限制和实际证据相符。

**Confirmed 基线缺口，非本包新增缺陷：** 六类别名/四非法示例UUID，五类normalizer未产品接线，旧 SourceConnector 缺完整四段协议，OSV多ranges整形不能保留独立分支。草案已明确披露并置于待冻结/后续实现范围，不以本准备包修复为验收条件。

**缺测：** 新源PG/UI/安全E2E、实际第二页/有界窗口、401/429/结构漂移真实录制、重启回补/并发/旧租约、A→B→A、独立漏采参考集合、持续采集窗口、无时间/未来时间指标、≤6h、AVID单件正文、NIST/CAC更新索引与视觉质量。R06-C01只有部分真实输入证据，C02–C06仍有上述未完成项；整原T卡C01–C06不能因此被签字。

**未证实的推测，不报成缺陷：** system DNS失败的更深系统根因、当前AVID更新活性、官方许可/配额网页今天是否变动、NIST是否最终符合组织方标准类别计分。没有第二次外网访问或组织方确认，所以保留未知。

## 评分证据和下一步

F1/R1只能引用类别/通道分离、固定入口身份、公开原文hash和能力限制；8个HTTP200不等于8类产品来源全通过。P1只能引用分页/时间/漏采设计要求，本包没有时效或连续运行指标。E1可引用冻结diff、原始字节保真、真实exit/JUnit、独立源码图和离线复跑。各项未覆盖内容保持not_run/待冻结，不替代G-B/G-C检查点。

下一步由主控处理本准备包review结论，冻结分类、时间精度/时区、GitHub API版本、非漏洞实体持久化与注册配置迁移边界，再按明确所有权开展小型source adapter。继续补AVID单件、合法许可快照、NIST/CAC更新入口及逐源PG→UI/分页/恢复/持续观测；不能提前签整R06。

Verdict: **Ship，仅来源准备包**。

Not checked: 新源产品集成、正式live/持续时效与评分、组织方类别边界和未留存官方网页的当前许可/接口内容。
