# G-F · 安全、标注与评测准备

文档首次创建时间：2026-10-16T21:14:23+08:00
本次写作开始时间：2026-10-16T22:30:16+08:00
本次写作结束时间：2026-10-16T22:30:16+08:00
最后更新时间：2026-10-16T22:30:16+08:00
阶段实际开始/结束时间：提前独立准备；正式阶段尚未开始 / 尚未结束
本报告证据截止时间：2026-10-16T22:30:16+08:00
主控/实现Agent：/root及本报告第3节指定作者
独立审查Agent与报告：仅组件限定意见；正式阶段新reviewer尚未委派
阶段状态：in_progress
实现状态：partial
各层验证状态：unit/contract/integration/security/frontend/e2e/live/manual整阶段均not_run，组件范围另列
工作分支：codex/full-delivery-recovery
已测代码SHA：组件限定SHA见第5节；阶段候选未冻结
已审代码SHA：组件限定SHA见第3节；整阶段未审
提交/推送结果：尚未发生阶段push；见reports/push/recovery_push_log.jsonl

## 1. 本阶段要解决的用户问题与验收范围

R19/R20/R21；T46/T45/T47/T48/T49/T50/T51；P1/P2/P3/A1/E1/X1，工具准备不代表正式gold冻结或性能已测。 原分母、盲测隔离、双人独立标签、完整耗时与未知状态保留。授权允许安全独立准备，不代表阶段门放行。

## 2. 当前真实状态与修改

G-F标注工具已有1个真实dev候选/0人工gold，直接最终路径写入中断截断已作者复现，原子发布修复在隔离WT进行。G-G已有R24候选骨架，正式评测、干净复现、最终Word/PDF/PPT/视频尚未形成可验候选。主控仅此真实时点创建报告，历史首次写作未伪造。

## 3. 并行执行与独立审查

R19作者独占scripts/annotation/prepare.py+新测试；R20新loader reviewer仅读9c043脱敏冻结；R24 preparation独立17988bb1f0eed6eb665ff75b13e15e44507b317d只批准早期骨架。Root公共合同/状态/迁移/锁/集成/Git/push，作者不签accepted。见progress/recovery_workstreams.md。

## 4. 问题台账

- R19-atomic：发现实际时间见作者ownrun（本报告不补造）；强制中断最终写入会留截断JSON，影响annotation导入/导出。Root已批准完整fsync+同目录排他hardlink，作者修复中/待非作者复核；Windows掉电目录持久性不声称保证。
- R20-secret-boundary：Root原ea stage失败却commit，局部ZIP7与13paths25未注册匹配，未push。32分类已有新独审，Root精确追加登记/锁ZIP边界尚未实现；实际秘密6refs窄比较0命中仍不证明全资产上下文，freshreview进行。
- R20-cpu：合法近阈输入误杀及异常child pipe EOF/handle归属未闭合；仍needs_changes，不降低原CPU门。
- Human-gold：双人独立核验与裁决人未提供，正式冻结外部阻塞。只有候选/工具，人标0；PPT模板后置未取消。

## 5. 实际验证

只引用已真实组件记录：R20 provenance新独审32分类/227边界；9c043窄比较6/6refs/10values/20forms/13paths+15members0exact，未作为整secret门；R24 prep独审36static/46paths/287证据/166路径。命令、UTC或+08时间、exit、rawhash见各冻结报告/ownrun；本报告创建不补造重跑命令。整阶段性能/恢复/CI/e2e/live/manual均not_run，fixture不计live；正式指标、分子分母、持续采集窗均未取得。

## 6. 合同与计划差异

无评分/gold/阈值/分母新差异。R19原子文件修复兼容原排他输出，无新公共schema/action；具体源码仍awaiting_review。G-G严格R24-A→R23→R24-B，preparation不算A候选ready。

## 7. 评分和场景证据

当前证据只证明工具/材料准备与局部安全边界；P1/P2/P3/A1/E1/U14完整证据未满足，无优秀/满分自评。逐条T00–T59/R00–R24映射由原manifest维护，未因重排漏项。

## 8. 阶段结论和下一步

允许继续不受阻塞影响的内部准备，不能通过本阶段门。下一：完成R19原子恢复与新独审、精确秘密门/真实恢复CI；六业务/变化前置闭合后同条件基线/消融/完整性能；人工冻结后R22正式运行，再R24-A候选、R23干净复现、R24-B最终冻结。没有暗中后台自动化或公开部署。

## 9. 文档修订记录

2026-10-16T21:14:23+08:00 /root首次创建：真实准备状态、未满足前置/未运行检查与问题登记。未声称历史已有本阶段报告。

## 2026-10-16T22:30:16+08:00 · 滚动并行与限定验证修订

R19标注FD fix6298由原非作者094c定向27green限定Ship；旧118超cap4仍失败。ContentStore首次独审14fe三负例证实cleanup覆盖主错误，213重跑pass但首峰11触cap10失败保留，修复c56待定向独审。secret-loader显式guard合成预期通过但两次runner收尾失败/保守峰9超cap8，已派新诊断；backup恢复独立开发，安全/人工金标/正式门未通过。

主控/root修订，整阶段仍in_progress/partial，各整阶段层not_run，无本阶段push；历史首次创建时间不变。新的报告/材料SHA与真实运行范围分别记录，不把局部结论累加为阶段通过。

## 当前集成证据与滚动并行 · 2026-10-17T00:40:47+08:00

本次写作开始时间：2026-10-17T00:40:47+08:00；证据截止时间同写作开始。Root 基线 a576fc1f88cd82bc13e5bed9a4c7a013bb8cd74b，batch11 是未放行阶段的 checkpoint；G-C/G-D/G-E/G-F 均 in_progress/partial，整卡各层未因此改绿。origin 2026-10-17T00:37:39+08:00实际读取仍为授权URL；本批尚未push，最后已核远端仍G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。

复用与必要新增：来源保存链复用 SourceResponse 与既有不可变修订，来自 a3e918ac 的服务器可信 data_mode 不信任远端 metadata，mode 改变产生新修订而不覆盖旧历史；Root 默认 worker 仅注入已有 settings.data_mode，新增2个注册回归。文件存储复用标准库 os.link 做原子排他发布，保留原主异常和 foreign 文件，NTFS以外无成功承诺。Detached 完成端口沿已有 fresh PG transaction、租约/attempt/完成逻辑增加可选四参数guard，None兼容，不新增状态权威、数据库表或依赖。

独立源审查：模式 source a3e918ac268fa4a7dcddd89a849ec406faf331b8 / review dcf1701ee258b3464d2d67de4844b2b97b82799d（386离线+12真实PG）；存储 source e2f11a687dfe1c3d7b9cbde61ab6c5ba299661c7 / review cdfeff49c92dfc34da36b41f0f54b859cabe293d（233不同离线，仅NTFS）；完成端口 source 968c71b6ed5e3991edd49bedfef765b36fdbda3d / review e98f82f8dd3a40b1f617a77ab0a4457c66dfb849（158离线+27真实PG）。这些限定源结论不代签Root新组合/default/live/fan-in，审查材料在各自冻结WT/Git提交中可复取。

Root本批实际自检：工作目录D:/dianzi/backend；2026-10-17T00:17:25+08:00至00:17:37+08:00，21明确相关unit/contract文件339passed/0fail/error/skip，mypy6源、Ruff7文件和backend100 format检查均exit0。原命令/日志/XML/起止时间在 reports/runs/recovery_reviewed_integration_20261016/source_storage_batch11_checks.json 与同前缀文件。此批无PG/Redis/model/sourceHTTP；integration/security/frontend/e2e/live/manual=not_run。此前各模块真实PG不拼成此新组合通过，测试时长不称持续采集。

CBM本批2026-10-17T00:31:04+08:00至00:31:28+08:00：当前backend/src独立缓存，2803nodes/16382edges，parsepartial/unusable0；index/schema/architecture/workflow.tool/consume_job五命令exit0，source_storage_batch11_index_source_files.json保存当前WIP逐源hash，cross-check源码/rg。秘密、fixtures、holdout、报告不入索引；缓存留工作区外。工具完整并发cap没有本批采样，not_run，不能冒充资源验证通过。

问题/传播：R14 read fix1的真实复验298=294passed/4failed，其中37PG通过；4红为 compare_versions未知后仍inventory及旧Assessor已完成节点恢复时三策略停止原因错误。冻结修复者新WT只workflow/graph+直属tests，原Oracle不改。R14默认broker单独原case已执行返回，但composite因共享fixture权限错误失败，恢复/重启段未执行，仍待复核。Root UI独审82frontend/64backend/474SDK/12diagnostic通过，但真实Edge首屏超时/0业务断言/ordinary consume未运行；新诊断只入口，不以组件测试替代浏览器成功。所有失败原日志保留。

并行所有权：Root独占公共合同/配置/schema/迁移/锁/progress/App/Git。r14_unknown_boundary_root_cause_fix2仅workflow/graph、新tests；r17_browser_entry_timeout_diagnosis仅自己诊断脚本/报告；r18_public_producer_fix2_independent_recheck只审c8ab/3b冻结公开读取；r07_default_bridge_consumer_implementation只reader factory和直属tests，真实Root consumer尚未接。两旧独审只封存/复核，不修改业务，未签全卡accepted，子Agent不push。最多16宿主槽，实际滚动分工而非虚构后台。

合同差异：CR-R16_completion_fanin于2026-10-17T00:31:04+08:00补本attempt typed verified-bytes、64MiB去重/原R11较低限、精确owner/context/epoch/CAS与无外部IO finalguard；消费者source d550仍需新独审。原T卡验收、two-types、金标/阈值/分母不变。只有原page-budget指针按completion manifest解析获准，原drive retry Oracle未实跑先保留。source-mode CR b578未新增公共schema。

下一步：冻结本batch11给新的非作者默认入口/真实PG/单来源验收；通过后创建干净Product fullSHA，重绑定已审CORE/OPS，由新激活审查者检查schema0030/DB OID+COMMENT/nonce/预算，实际启动同版本受控6h。旧Product1cdb不得启动，新窗口尚未开始。父PG资源deadline 2026-10-17T21:49:15+08:00不延长。R16 fan-in、历史/撤回/negative watch、公开tasks/ask/stack/HTTP-MCP及三插件、R19人工金标、R20秘密/CPU/CI/索引恢复、R21/R22/R24仍有内部工作；不能称只剩外部。

评分证据范围：F1/E1支持可信来源模式与原文原子保存；A1/E1支持内部最终事务guard。九维/来源广度/完整Agent/准确率/P95/正式分母与6h稳定运行本批没有新结果。费用unknown，无本批产品API付费调用。用户tsbuildinfo rawSHA 3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d未改未stage，push ledger未纳本批。

本次写作结束时间：2026-10-17T00:40:47+08:00；修订原因：精确集成3份已独审源，保留新组合证据限制与4红传播；修订人Root。

## 集成与并行续接 · 2026-10-17T01:31:38+08:00

本次写作开始时间：2026-10-17T01:31:38+08:00；证据截止时间：2026-10-17T01:31:38+08:00；Root当前代码HEAD 1c3c33808053227b8502443ebdff4c848c66e62b。G-C/G-D/G-E/G-F仍in_progress/partial，阶段未放行/未push；最后已核远端仍G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。原T卡、金标/阈值/分母不变。

本批采用备份source12f9e8cd2f1e7073427c2959fdbc799b90fc44fe已独审ab04855085f828548222443c31020852f7ca2970的4个文件，复用官方pg_dump/pg_restore、现有ContentStore与PG事实，没有新增依赖/平行数据库。独审40不同案例含2真PG/fresh进程，69表/18记录/2原文对象，indexes=rebuild_required；不是Root本批重新跑PG。本批Root 2026-10-17T00:56:48+08:00开始32离线案例passed（0fail/error/skip，0.49s），strict1源/Ruff3文件/backend100格式3文件均exit0。新RootPG/MinIO/实际索引重建/完整恢复/CI仍not_run。命令/起止时间见backup_batch12_checks.json。2个已冻结Windows测试依赖从ab048精确取回，PG2仅collect-only，未连接数据库；旧外层checks.py未采用，runbook改为实际存在且已测的offline命令，PG须用受控资源窗口。22个历史plan证据输入按已有immutable hash复核后入本checkpoint，不把旧报告结论迁给新代码；verify_plan exit0仅结构，不是产品验收。

新真实来源专项review ac6a0ed2efccc4b5af12888605d959937b57d982只签f3c2e41e31fd5b0f1be004b379f5ed775c95f287：339离线=318unit21contract+7实际PG；DoH配置hash6b69fe8e10f9ba85d756061fc2be242bde0a468d6b2b5d3879fed20e7b3e2076，2026-10-17T00:57:32+08:00至00:57:58+08:00，两源HTTP200/defaultAPI→outbox→真实broker普通worker→30trusted-live修订/211证据/2游标→list/detail200。各源仅1页partial/source_page_limit_reached，不能称全来源/6h。旧system DNS非公网拒绝、首次RedisAUTH红保留；旧DTO把None/fixture返回live的真实负例failed，是内部待修而非外部完成。资源最终0，角色superuser CONNLIMIT不硬限，连接峰未采不冒称通过。

R14共享读取消费者+unknown恢复最终source1dafd15ff1c25d08489fd69efa44e8481d6dda22/material43d4eeb89610d04c6eab6816d42c482f5dd6c2be，经原独立reviewer新WT 0e8352564ecd2e39c359aef9f831c90077f7e709限定Ship；348离线+38真PG=386不同用例，真实PGcheckpoint三策略incoming unknown、终态Reporter/read_result、权限/lease/epoch优先与旧37均passed。PG窗口01:18:33.849–01:21:06.606+08约152.76s、进程峰7<=10，DB/schema/连接/进程0，原固定库comment恢复NULL。原fix1/fix2的4红/5红及元数据失败保留。Root尚未集成此source，不签九完整职责/模型live/历史HTTP/UI。

R18 public read fix3 source99ea5e507d1530ce930d2cc078d929881ee3d2be/material60e3223c2be5a4d13c8a310259a5ee16c7774abf经a2ccaa0ae8940a2717536e94afc311a8b32423af限定Ship：141离线、原40PG(8+32)+独立hypothesis1共182不同用例。human完整3quote available/current且PG真实origin/assertion/source_verified保持，模型假设仍blocked/unknown。01:05:09至01:08:03+08总174s<=新240窗口，旧超时/nonce长度setup错误保留。Root还未装配公开producer/typed task/ask/stack/HTTP-MCP/三插件，整R18partial。后续diagnosis123bf91aad8bf7ed1834a370a7ac4c6f9584f80b又以10真实shape离线探针确认来源报告被强图资格误降blocked；这个新已证缺口不由早先限定Ship关闭。

R17默认UI正式bundle真实静态10断言通过，source产品a576；独审b4b1bfa8643c2caeba2e9de8c65cd99715d36c90，实际4.609s/Win峰13/资源0。原runner main500、Edge路径及控制shell错误全部留原收据。仅React挂载/匿名/390窄屏/reduced-motion，调查业务、ordinaryconsume与当前f3浏览器仍not_run。新版资源窗待分配，不能组件替业务。

R16 source d550/032 首审a55b48c49326e698fb7f264557d7271034d1b17c needs_changes：194+4离线green，26PG23pass/3fail（旧drive把retry_wait当终态两红、新assetID创建fixture404）。首PGstdout/cap未落盘，保持unknown；实际owner/OID/COMMENT清理0。fix1 b2b0d8d495bc41af14f5c0db19b7c9a4621bf222/aecfe8535f05f59d54d7785b08f6f722ef1b2d73仅3tests，业务source不变；原194+新driver20=214离线passed，3PGcollect-only；有界真实到期重试journal、原排序/终态业务assert/two-types原字节保持，待原独审定向PG，Root未集成。

滚动并行所有权：Root独占main/共享合同/App/schema/迁移/锁/progress/Gitpush。R06绑定author候选COREa13f67c2ee836c9cee1750a3477f2904efb5d21e/OPS4dfe106a505bc80d1357b3178bcf1513b1711351/materialda221caff24704c8b35f471fd5ae7a9075887cd5只自己23控制文件5处绑定与报告；Product独立D:/wt/r06-product-f3-runtime-20261017仍clean f3，217源+迁移raw/Git分开，22guardspassed，七false/readyfalse/OIDNone，无provision/start/6h。原42ledger不reset/旧namespace是否空闲未测/COMMENTexact9无字面nonce/superuser连接门尚待新独审核，不误写启动。R07内部bb04 reader、91b工厂、c2f helper（304offline）Root未接Enricher；新123bf诊断建议先来源报告分类旁路，原Graph/current_supported/unknown不放宽；graph_apply默认无消费者，另须Root冻结R10协调合同，不挪R16 fan-in。Agent只自己的WT/source/tests/报告，不push/accepted；人工双核/授权资产/CNNVD输入之外还有这些内部工作。

下一动作：冻结已合备份与历史输入，再Root集成已限定通过的R14/R18接口；在新批实现SourceEnricher实际输出UTF8预算及public typed reports后交新非作者，不沿旧审签新code。新R06激活review须先核实际parent健康/OID/COMMENT/ledger/旧namespace空闲/关机/资源，再实际开始同版本墙钟21600s+关闭900s，父deadline2026-10-17T21:49:15+08:00不延长。R19人工gold/秘密和CPU门/索引恢复与CI/R21/R22/R24仍有缺口。费用unknown；此批产品model/API付费调用0。用户tsbuildinfo hash 3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d不改不stage；push ledger不纳本批；本报告写作时push尚未发生。

本次写作结束时间：2026-10-17T01:31:38+08:00；修订人Root，保留各文档首次创建与所有历史修订。
