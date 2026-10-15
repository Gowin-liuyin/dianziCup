# R07 · 公共结构化信号实现包 A

文档首次创建时间：2026-10-15T23:31:09+08:00
本次写作开始时间：2026-10-15T23:31:09+08:00
本次写作结束时间：2026-10-15T23:31:09+08:00
最后更新时间：2026-10-15T23:36:47+08:00
证据截止时间：2026-10-15T23:31:09+08:00
实现 Agent：/root/r07_public_signal_implementation；主控/后续接线：/root。
任务状态：awaiting_review；本包实现状态complete；整R07/G-C未验收，原T卡全部合并条件保留。
本包层级：unit passed；contract passed；integration not_run；security仅unit边界及继承纯回归，产品权限security not_run；frontend/e2e/live/manual not_run。完整相关回归failed。
工作分支：codex/r07-public-signals；worktree：D:/wt/r07-public-signals。
起点：098502991f617a5fa9fdfb9c3da91e54aee7ff06；固定自检代码：7142c38620150d5f2b7d81963389bdf8b725c316。
代码编写开始/结束精确时刻：历史未完整记录；第一次实际系统时钟读取为2026-10-15T22:57:52+08:00；不以mtime伪造工时。测试/文档时长与外部观察窗口分别记录。
独立审查：尚未发生，交主控新reviewer；没有自行签accepted、改共享state或push。

## 1. 范围与可观察行为

R07:T19/T23公共CVSS、EPSS、KEV、CWE候选适配，F2/P2的结构值/来源/维度状态切片；不代表T13/T19/T20/T22/T23/T41整卡完成。四维之外ATLAS/版本/文献/PoC/暴露由其他工作包及root负责，R08真实供应商、PG最终发布和U场景全链均不能由本报告涂绿。

`enrich_structured_fields(context, tuple[EnrichmentDocument,...])`始终按cvss/epss/kev/cwe返回四个DimensionAttempt。输入是服务端派生可见修订、已被来源支持的CVE和永久JSON叶块；不把新源CVE添入context。输出只有候选，不含可自填supports_claim/human_confirmed，不连接PG，不调模型，不发外部请求，不发布事实。

CVSS保留standard_version/vector/base_score/source authority/scored_at。NVD复用normalize_nvd_record；不把published/lastModified当评分时间。厂商保留publisher.login字段证据；没有明示评分机构就blocked，不填默认机构。支持2.0/3.0/3.1/4.0的基准语法和值、重复键/向量版本一致性；不独立重算分数，非基准可选指标只保存其源语法，不声称全部CVSS数学一致性已验证。

EPSS真正0可available；probability/percentile/date严格校验。FIRST API version='1.0'留在响应语义，model_version=None。KEV保留catalogVersion/dateAdded/requiredAction/dueDate/已知勒索利用语义；完整且逐项有效的目录里未命中才可not_found，绝不由外部失败/跨CVE/坏行变零或安全。无支持CVE的EPSS/KEVnot_applicable；CWE无目录blocked，其余维成功保留。

CWE须NVD/厂商字段ID加官方MITRE目录版本、ID、name证据一起支持；不靠CWE正则、供应商display name或有限内置白名单当目录验证。合法但没在目录选中项中确认的IDblocked。NVD-CWE-noinfo/Other为pending，明确缺字段也是pending，带scope/time/完整块的显式空字段才能not_found。不同CWE标签可以并列；同ID同taxonomy版本的名字分歧conflict。CVSS同CVE同标准的score/vector差异conflict；同分不同机构、不同CVE或标准并列，不挑最高分。

## 2. 修改、复用与必要新增

仅四个新文件：backend/src/ai_intel/enrichment/signals.py（723行）、signal_sources.py（429行）、tests/unit/test_r07_public_signals.py（517行）、tests/contract/test_r07_public_signal_sources.py（233行）。1902行是实际diff大小，不是通过或节省量证据。没有改core seam、Claim/公开schema、API/worker/来源共享函数、迁移、锁、配置、前端或金标。

复用Pydantic冻结九维值/候选/逐维尝试、严格JSON重复键与非有限数边界、NVD/厂商现有正规化、JSON叶块解析、NormalizedSourceDocument和标准库date/ZIP/XML/hash。必要新增只为本包闭集请求、不同出版社真实wire、CWE目录安全解析/紧凑选取、四维语义与精确字段证据。没有BaseService/通用CRUD/新事实库/自制网络客户端/新依赖。采用本机Ponytail5.2 full；未用旧全局同名技能。

候选引用必须命中唯一块的json_pointer及其规范文本`pointer: value`，Unicode坐标相对真实块，quote哈希按原字符串计算；同值在别块、错pointer、追加同值、重复pointer都拒绝。publication再加永久块start_offset。来源/time取输入；freshness默认unknown，不假设当前。重复同输入输出可重复一致，业务幂等/冲突权限仍交现有PG服务，不建立内存业务台账。

## 3. Root接线协议与边界

`build_public_signal_request('epss', cve)`固定GET https://api.first.org/data/v1/epss?cve=精确CVE，host api.first.org，application/json，256KiB，12秒，0redirect；`kev`固定GET https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json，8MiB，同12秒/0redirect。构造时拒绝非CVE及query注入，无任意URL/shell/SQL工具。root使用共享NetworkGateway，HTTP非200不进入成功正规化，遵守任务并发/次数/费用边界。

`select_public_signal_document(signal, original_raw, cve)`返回NormalizedSourceDocument；只选0/1记录。payload：schema_version=public-signal-selection-1，signal，selection{requested_cve_id,source_response_sha256,source_total_count,source_record_index|null,complete_response=true,query_scope=single_cve|complete_catalog}，response{EPSS status/status-code/version/data或KEV catalogVersion/dateReleased/vulnerabilities}。CISA每次完整目录原body只在对象存储留一次，不为每个事件复制1745条；挑选范围/总数/hash不会抹去。publisher必须核选取hash对应其已保存真实gateway原body并重新检查选择，形状校验不能证明目录真实或完整。

`select_cwe_catalog_document(original_raw XML|ZIP, cwe_ids<=20)`返回标准类NormalizedSourceDocument。payload：schema_version=cwe-selection-1，taxonomy_version，selection{source_response_sha256,source_xml_sha256,total_weaknesses,requested_cwe_ids,complete_catalog=true}，weaknesses选中{cwe_id,name,source_locator}，missing_cwe_ids，copyright/license/license_uri。MITRE版权和许可原文随选取资料保留。根源URI固定 https://cwe.mitre.org/data/xml/cwec_latest.xml.zip；当前物理版本从XML Version读，不能拿latest URL或网页4.20当目录版本。

root保存原ZIP/XML仓外对象/hash/获取时间、source registration和选中文档；loader令EnrichmentDocument.source_version=taxonomy_version、source_category=technical_standard、kind=standard；另三源用固定注册类别、服务器source_id/record_id、原observed_at及固定当前revision。JSON payload的SHA是选择文档bytes哈希，source_response_sha256另指原响应，不混淆。先按parse_json_document保存完整选择文档叶块，再向helper提供json_pointer/块身份/hash；当前200块/2MiB seam限制是明确选择范围，不称全目录入此seam。

CWE输入8MiB、ZIP解压最多32MiB、一个固定安全XML basename、禁加密/目录路径/压缩比>200，内存解析不extract；UTF-8严格，拒绝DTD/外部实体/自定义实体，树深64/节点250000/Weakness最多5000。解析后选0/20条并明确missing，实际目录未取时blocked。root负责整个worker的wall/内存/CPU、源码许可和阶段live，不能据本包纯函数将其计为产品在线能力。

## 4. 真实资料复放与工具链定位

新source/model/测绘live调用均0；`replay_recorded_responses.py`复用主控旧21:22批次两份公开body，检查原receipt SHA/HTTP200，再纯解析，不计live。运行：2026-10-15T23:23:20+08:00 → 2026-10-15T23:23:20+08:00，见recorded_response_receipt.json/recorded_response_replay.log。EPSS原203B/单CVE-2024-37032，候选available四字段证据，model_version未知；CISA原1787354B/1745项完整有效，CVE-2024-37032真实not_found，实际首条CVE-2026-105134 available/6个证据，选取1947B，不复制全文。NVD已有公开录制样本CVE-2024-28224，CVSS available/5字段证据、CWE blocked缺目录；评分/观察时间未记录处保持None。

官方文档依据：[FIRST数据用途](https://www.first.org/epss/data)、[FIRST endpoint/schema](https://api.first.org/epss/)、[CISA官方目录](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)、[CWE下载](https://cwe.mitre.org/data/downloads.html)、[CWE许可](https://cwe.mitre.org/about/termsofuse.html)。CISA网页403和ZIP在web工具unsupported不等于其真实body不可解析；原公开body复放已证实。CWE页显示4.20只作研究观察，实际目录body没有在本包取得，无真实目录候选验收。

官方CBM0.11 src-only基线1285节点/6459边；固定7142c38620150d5f2b7d81963389bdf8b725c316刷新：1333节点/6761边，cache=/tmp/dianzi-cbm-r07-public-signals-20261015，不入Git。schema/architecture/trace原输出和实际argv/秒级时间/exit在cbm_frozen*.json。既有产品链source route→PG job/outbox→worker→_publish_cvss→DimensionRepository/GET详情保留；新enrich_structured_fields和select_public_signal_document在src图入向均0，源码rg只见定义，与“本包未root接线”的事实一致，不能单靠图无边称最终业务缺失或已经接通。

## 5. 固定SHA验证

环境：独立WT/backend/.venv，实际uv sync --offline --frozen --extra semantic exit0/92包；初始同步精确起止历史未记录。所有正式命令工作目录D:/wt/r07-public-signals/backend，argv见对应json，日志/JUnit同名；原60覆盖门未改。原PG10项按原real_pg标记明确deselect，属于独立PG测试范围not_run，无skip替代失败。

| 检查 | 实际开始/结束+08 | exit | 数量/结果 |
|---|---|---:|---|
| `native_frozen` | 2026-10-15T23:21:09+08:00 → 2026-10-15T23:21:11+08:00 | 0 | 1通过/0失败/0skip；原PDF启动例0.77s |
| `focused_frozen` | 2026-10-15T23:21:14+08:00 → 2026-10-15T23:21:16+08:00 | 0 | 101通过/0失败/0skip；0.20s |
| `ruff_frozen` | 2026-10-15T23:21:14+08:00 → 2026-10-15T23:21:14+08:00 | 0 | 4文件通过 |
| `format_frozen` | 2026-10-15T23:21:14+08:00 → 2026-10-15T23:21:14+08:00 | 0 | 4文件通过 |
| `mypy_frozen` | 2026-10-15T23:21:14+08:00 → 2026-10-15T23:21:15+08:00 | 0 | 2产品模块通过 |
| `pure_frozen` | 2026-10-15T23:21:18+08:00 → 2026-10-15T23:23:09+08:00 | 1 | 1944通过/1失败/10 real_pg deselected/0skip；107.11s；coverage75.75%原60 |

focused分类：{'tests.unit.test_r07_public_signals': 51, 'tests.contract.test_r07_public_signal_sources': 50}。正常、缺失、不适用、blocked、failed、conflict、源partial、bool/NaN/范围/未知时间、重复/跨CVE/错误JSON、重复键、Unicode坐标/hash/pointer/source scope、CWE目录/ZIP/实体、payload注入均有可观察断言。T19-C01/C02/C05和T23-C03/C05只取得本包纯候选/来源语义证据；T19-C03/C04/C06完整PG/权限/幂等和T23其他PoC/修复/资产范围由原映射切片共同验收，不越权标为全完成。

## 6. 问题与偏差台账

1. 首轮模块缺失测试：0测试执行/2collection errors，initial_red.log；新增两模块后14→81→97→101针对性测试通过。历史探索命令精确起止未记录，不补写；静态最初28Ruff/9mypy错误保留initial_*.log，最终固定SHA静态exit0。
2. 首轮全pure错误包含原real_pg合同：1747passed/1setup error，DIANZI_TEST_RUN_ID缺失，73.43%原60；pure.log/json/xml保留，错误不是业务断言失败。修正范围沿仓库原测试标记-m 'not real_pg'，不是改失败为skip；PG项目not_run。
3. 未冻结探索回归pure_corrected：1940passed/1failed/10deselected，75.71%；原PDF worker等待首GUARD行超过既有8秒。本包代码在探索过程中仍有改动、旧writer仅结束采hash，此轮只作红证据，不给冻结代码背书。冻结后原PDF例定向1passed/0.77s，不据此推测资源竞争为根因。
4. 固定SHA完整pure_frozen：1944passed/1failed/10deselected，75.75%；原test_guard_hard_exit_after_readiness_terminates_worker_tree[native-cpu] GetProcessTimes kernel4062500+user6250000=1.03125秒，未过原<1秒断言。进程树已结束、无UNSUPERVISED_RESULT/Traceback等先行断言过。根因尚未确认，已交root新诊断者；未改CPU文件、1秒/8秒/覆盖门、金标或skip，不扩大完整重跑。状态未解决，整体回归failed。
5. 外部文档资源控制偏差：三次web工具项数4+4+2=10，预算8，超2；成功正文5/失败5。第一次错误EPSS /epss/api路径404、CISA页403、schema地址失败、ZIP类型unsupported等均保留工具实际记录。错误在按工具批数而未按内部items剩余额度计算，发现后停止所有新增外部IO并告知root，不追认成8。后续每批前按剩余items限额。实际网络单请求时长/响应字节web工具未暴露，写unknown，不能声称每请求已证实<=8MiB/总wall<=60s；没有下载CWE原体。模型/测绘/产品付费API新增0，工具费用unknown。人类报告此前消息误计11项/4正文，已纠正为实际10/5，历史不擦除。
6. 仪器错误：早期猜错parsing.py/network目录/vendor_advisory.py/receipt复数文件名，rg或Get-Content exit1后按rg真实路径修正；不编造不存在路径作为产品缺陷。报告入口/writer改为固定SHA前后hash；原红日志/JUnit保持，不改测试分母。所有问题登记时间本报告真实2026-10-15T23:31:09+08:00，早期首次发现精确秒历史未记录，不伪造。

## 7. 未证明与交回

尚未独立review；全pure继承CPU守护失败待新诊断，不能称全部测试通过。真实CWE目录body/版本/全目录回放尚缺；CVSS可选指标完整语义和分数重算未实现，源报告值及限制保留。四维真实共享网关→原体/选择文档→PG发布→API/UI读取与权限/更新/live/manual均not_run。最终发布必须再次验证source注册/租户/当前revision/原response selection/hash/字段内容支持，候选通过不能当支持事实。

没有取得准确率/召回率/问答延迟/持续采集窗口正式指标，也没有人工金标。没有读DPAPI/.env/KEYS附件、秘密、私有资产或holdout；unknown许可的CISA全文仍在仓外cache，不进Git。前端/SDK/MCP/插件/运维其余卡均不在本包，原T卡合并条件不变。下一步：主控新reviewer固定7142c38620150d5f2b7d81963389bdf8b725c316复跑四维及实际留档，核loader协议→root接线→独立PG/API/UI/live；CPU诊断独立继续。

## 8. 文档修订记录

2026-10-15T23:31:09+08:00，实现Agent首次创建报告；2026-10-15T23:31:09+08:00，按冻结SHA/原红绿日志、101测试、1745条真实录制body复放、CBM和外部次数偏差封存；无accepted或push。

2026-10-15T23:32:46+08:00，更正复放日志文件名、词法秘密检查和精确Git blob封存；首次创建时间不变，产品代码未变。

2026-10-15T23:33:55+08:00，更正复放日志文件名、词法秘密检查和精确Git blob封存；首次创建时间不变，产品代码未变。

2026-10-15T23:36:47+08:00，更正复放日志文件名、词法秘密检查和精确Git blob封存；首次创建时间不变，产品代码未变。
