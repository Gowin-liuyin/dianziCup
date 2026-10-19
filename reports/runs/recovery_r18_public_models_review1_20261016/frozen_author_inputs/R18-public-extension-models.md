# R18 · 公开扩展 SDK typed models

文档首次创建时间：2026-10-16T21:18:13+08:00
本次写作开始时间：2026-10-16T21:18:13+08:00
本次写作结束时间：2026-10-16T21:18:13+08:00
最后更新时间：2026-10-16T21:23:02+08:00
任务实际执行开始/源码冻结时间：2026-10-16T21:05:57+08:00 / 2026-10-16T21:13:50+08:00
证据截止时间：2026-10-16T21:18:13+08:00
实现 Agent：/root/r18_public_extension_typed_models_implementation
独立审查：待主控派发新非作者 reviewer；本报告是作者自检，不是独审放行。
任务状态：awaiting_review；本切片实现状态：complete；整 R18：partial。
工作分支：codex/r18-public-models；工作目录：D:/wt/r18-public-models
基线 SHA：1315194a8ee421b7f1131a901221f31f4cacb536
已测源码 SHA：2bb2e122644bd2e2084056ca0251bcd85583c664
已审源码 SHA：尚未独立审查
提交：只提交三个明确授权的源码/测试路径；未 push。

## 1. 用户行为与范围

R18/T04/T32/T35/T51 的公开类型切片，支持 SDK 读取已冻结的 sources、vulns、tasks 封装，以及新风险摘要。
唯一业务文件所有权为 `sdk/python/ai_intel_client/models.py`、`__init__.py`、直属新增 `tests/test_public_extension_models.py`。
client/MCP 六工具由另一个 Agent 实施；后端共享服务、REST 入口、包装、锁文件、公共 schema、权限、状态由主控/相应唯一作者负责，本切片未修改它们。

输入为显式合成的 public JSON，输出为 frozen、extra=forbid、strict=True 的 Pydantic typed record。
公开扩展版本为 `urn:dianzi:public-api:extensions:v1`。没有读取密钥、附件秘密、holdout 答案，未调用产品 PG、来源、模型或付费 API。

## 2. 改动与复用

新增十个模型：RiskFinding、RiskSummary、StackCheckEnvelope、VulnerabilityPage、VulnerabilityDetailPage、SourceDescriptor、SourcePage、TaskDescriptor、PublicProblem、TaskResultEnvelope。
同名十类加入根公开导出；原七个 `__all__` 名称全部保留。八个原公开业务 DTO 类及原 models.py 全部旧正文保持原样，`dependency_inventory.json` 对 Git 原文前缀做了精确断言。
十四个旧 schema 定义逐个结构相等、八原模型和原 fixture 均保持。新增代码复用已有 PublicRecord/Citation/ComponentAssessment、UUID/RFC3339/绝对 URI 校验；没有添加依赖、通用服务层或另一套业务状态。

必要新增为冻结十个 DTO 的字段、分页上限和跨字段不变量，不能由旧 StackCheckResult/TaskHandle 表达：真实九种任务状态、明确错误、风险证据和四态未知。
Source enabled 不推断 healthy，healthy 必须带成功观测；never_polled 不接受已存在的观测。
SourcePage.source_id、VulnerabilityPage.event_id 重复拒绝；游标1..2048、分页最多100。
任务 poll_uri 必须固定为自己的 `/api/v1/tasks/{task_id}`，不能跟随响应中的任意 URL。
TaskResult 区分 ask/stack_check；非终态不含答案/error、succeeded 有正确类型结果且无 pending/failed/error，failed/cancelled/blocked 必须明确 problem；partial 保留部分结果、错误、未完成项。
CVSS 使用 CR 已批准的五个分带和版本；拒绝布尔当数值、非法 UUID/日期、缺引用、分带错误、重复 finding、同一 assessment/claim 的 payload 归属矛盾。
风险阈值 finding 与 confirmation 一致，unknown/stale 不写 complete；finding 必须对应同 index、同 ID、当前、有引用的 supported_applicability 研判。

## 3. 实际接口链与并行边界

原消费者经源码/rg 交叉定位：client 的 ask/check_stack 解析模型；CLI 使用旧 StackCheckResult；MCP 使用原两工具与 wire_json；mcp_stdio 进入 MCP server；根 __init__ 公开 SDK 类型。
第一次独立索引仅 `sdk/python/ai_intel_client`，名称 r18-public-models-1315194，157 nodes/595 edges/7 Python files，无跳过/部分解析。
源码冻结后新索引名称 r18-public-models-2bb2e122；实际 get_architecture、get_graph_schema、trace_path、get_file_outline 原始返回保存在本 run。
初次短函数名/缺 module 的 qn trace 得到0边，不能据此认定无运行调用；随后按 outline 的精确 qn 重查，另外 rg 与原349真实协议测试核实调用。
缓存为工作区外 `/tmp/dianzi-cbm-r18-public-models-20261016`，未提交工具缓存。索引未包含秘密、评测答案或无关用户资料。

完整 dependency inventory 共52个输入，49个非本切片文件 Git blob 对基线不变、三个源码/测试有各自 Git blob+raw SHA256。包含完整 SDK 源码、旧测试、旧 fixture、新测试、合同与配置。
源码已向 /root/r18_six_read_tools_sdk_implementation 交付 exact SHA；并行合并后的 client/MCP 需再审综合候选，不用本报告给未测新调用方背书。

## 4. 实际验证

所有表中工作目录均为 D:/wt/r18-public-models，数据模式 synthetic_fixture；日志保留真实开始/结束、超时上限与退出码。pytest 使用 --no-cov 仅隔离 SDK/JSON 合同验收，不声称全仓覆盖门通过，未改60%门槛。

| 检查 | 实际命令 | 开始/结束（Asia/Shanghai） | 退出码 | passed/failed/skip | 原始日志 |
|---|---|---|---|---|---|
| new_models | `D:\dianzi\backend\.venv\Scripts\python.exe -m pytest sdk/python/tests/test_public_extension_models.py -q --no-cov --junitxml=D:\wt\r18-public-models\reports\runs\recovery_r18_public_extension_models_20261016\new_models.xml` | 2026-10-16T21:11:05.080638+08:00 / 2026-10-16T21:11:08.256294+08:00 | 0 | 122/0/0 | [new_models.log](../runs/recovery_r18_public_extension_models_20261016/new_models.log) |
| new_models_final | `D:\dianzi\backend\.venv\Scripts\python.exe -m pytest sdk/python/tests/test_public_extension_models.py -q --no-cov --junitxml=D:\wt\r18-public-models\reports\runs\recovery_r18_public_extension_models_20261016\new_models_final.xml` | 2026-10-16T21:12:53.453327+08:00 / 2026-10-16T21:12:56.438850+08:00 | 0 | 123/0/0 | [new_models_final.log](../runs/recovery_r18_public_extension_models_20261016/new_models_final.log) |
| sdk_regression | `D:\dianzi\backend\.venv\Scripts\python.exe -m pytest sdk/python/tests -q --no-cov --ignore=sdk/python/tests/test_public_extension_models.py --junitxml=D:\wt\r18-public-models\reports\runs\recovery_r18_public_extension_models_20261016\sdk_regression.xml` | 2026-10-16T21:11:15.776813+08:00 / 2026-10-16T21:12:25.197493+08:00 | 0 | 349/0/0 | [sdk_regression.log](../runs/recovery_r18_public_extension_models_20261016/sdk_regression.log) |
| sdk_regression_final | `D:\dianzi\backend\.venv\Scripts\python.exe -m pytest sdk/python/tests -q --no-cov --ignore=sdk/python/tests/test_public_extension_models.py --junitxml=D:\wt\r18-public-models\reports\runs\recovery_r18_public_extension_models_20261016\sdk_regression_final.xml` | 2026-10-16T21:14:39.064389+08:00 / 2026-10-16T21:15:32.225849+08:00 | 0 | 349/0/0 | [sdk_regression_final.log](../runs/recovery_r18_public_extension_models_20261016/sdk_regression_final.log) |
| schema_regression | `D:\dianzi\backend\.venv\Scripts\python.exe -m pytest backend/tests/contract/test_r18_public_extensions.py -q --no-cov --junitxml=D:\wt\r18-public-models\reports\runs\recovery_r18_public_extension_models_20261016\schema_regression.xml` | 2026-10-16T21:11:31.045034+08:00 / 2026-10-16T21:11:35.280757+08:00 | 0 | 23/0/0 | [schema_regression.log](../runs/recovery_r18_public_extension_models_20261016/schema_regression.log) |
| style_final | `D:\dianzi\backend\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml sdk/python/ai_intel_client/models.py sdk/python/ai_intel_client/__init__.py sdk/python/tests/test_public_extension_models.py` | 2026-10-16T21:13:09.531957+08:00 / 2026-10-16T21:13:09.751877+08:00 | 0 | 非测试检查 | [style_final.log](../runs/recovery_r18_public_extension_models_20261016/style_final.log) |
| format_final | `D:\dianzi\backend\.venv\Scripts\python.exe -m ruff format --check --config backend/pyproject.toml sdk/python/ai_intel_client/models.py sdk/python/ai_intel_client/__init__.py sdk/python/tests/test_public_extension_models.py` | 2026-10-16T21:13:09.763906+08:00 / 2026-10-16T21:13:09.989555+08:00 | 0 | 非测试检查 | [format_final.log](../runs/recovery_r18_public_extension_models_20261016/format_final.log) |
| typing_final | `D:\dianzi\backend\.venv\Scripts\python.exe -m mypy --strict --follow-imports=normal sdk/python/ai_intel_client/models.py` | 2026-10-16T21:13:09.632830+08:00 / 2026-10-16T21:13:10.381891+08:00 | 0 | 非测试检查 | [typing_final.log](../runs/recovery_r18_public_extension_models_20261016/typing_final.log) |

唯一测试数为 123 新模型 + 349 旧 SDK + 23 旧扩展 schema = **495**；初次122是最终123的前一版本，不再相加；两次349同一套件也不相加。
最终349保存原始 native/stdio/loopback观察到独立 `sdk_regression_final_native_evidence/`。第一次349原 pytest log/XML保留，但当时未显式设置 SDK_TEST_EVIDENCE_DIR，默认临时观察目录未逐一归属，不假装已归档；因此有一次受控追加复跑。最终349没有失败/错误/skip，5条原 record_property 与 xunit2 不兼容警告保留。
原 guard 报告本 fixture 子段24次 loopback request、上限100、墙钟36.307979秒、外部/产品/付费请求0；不能把该24当全套所有合成 TCP 请求数。
stdio 资源观察有五请求/峰值4/queued dispatch0/shutdown all EOF=true；官方子进程 fault 场景真实 returncode3、固定错误且没有异常栈泄露、stdout JSONRPC无 marker，属原协议 fixture 回归，不是产品 live。

分层状态：unit=passed（本切片）；contract=passed；integration=not_run（产品 PG/后端 producer 未运行）；security=passed（DTO 输入/固定 URI/隐藏字段边界子集，非整权限/注入验收）；frontend=not_run；e2e=not_run；live=not_run；manual=not_run。
Mypy --strict --follow-imports=normal 检查 models.py 正文通过，不声称全后端/全 SDK 所有路径类型通过。

## 5. 问题、修复与未证明事项

- 21:05–21:08 的首次定位命令误用了 PowerShell rg 通配路径、不存在的 sdk/python/pyproject.toml，并有一次在主控 cwd 读取本 WT 日志，返回路径错误；随后使用 rg --files/准确路径。它们是定位错误，不是业务测试失败，未改变代码或 fixture，原工具输出仍在会话；初次读命令未保存文件 raw，不伪造补录。
- 第一次349缺显式原始观察目录：pytest log/XML已存在，单个临时目录所有权未确认，不抓取其他 Agent 或用户临时文件。改唯一新 run helper 设置 SDK_TEST_EVIDENCE_DIR，第二次完整349归档，不改变旧测试。
- 代码样式首次 formatting 的工具输出为2files reformatted、check0，未提前写文件 raw；最终 style/format 逐条可追溯 raw/receipt 均0。
- 根共享 public schema 不包含实际请求总数/claim 归属信息；SDK 不能通过 UUID 存在证明数据库事实、引文内容支持、当前 ACL/epoch、claim 与 event 的真实关系，须 producer 在 PG 最终事务核验。本片只检 payload 自洽。
- 主控补充确认 evaluated_components 是实际发生研判的请求组件数，unknown 被评估仍计数。本 DTO 只证 evaluated_components<=len(results)、index范围、complete无empty/unknown/conflict/stale；client check_stack(request) 还须按原请求数量/索引校验，producer complete 必须每请求 index 恰好覆盖，不能缩分母。partial 不擅自强制相等。
- Source 时间字段的真实性仍依赖 PG 实际观测，不能通过传入一条时间声明真实在线。无后端真实 producer、认证撤销、分页 ACL/epoch 或公开入口接线证明。
- 原旧 Windows writer.wait_closed 清理风险没有在本次两轮349复现；保留此前独审非阻断债务，未改测试为skip，不能因本次通过宣称该宿主风险永久消除。
- 代码编写、阅读、索引时间没有逐段时钟记录，历史未记录；上面的执行起点/源码冻结和各测试墙钟不混称持续采集或实际编码时长。

## 6. 合同与计划差异

依据 CR-R04、CR-R09、CR-R18_public_envelopes_and_output_budget；公开schema未修改、未新增字段/分带/数据源阈值、金标/分母/评分/盲测未改。
跨数组关系与 unknown/empty 保护是 CR 原风险语义及本次主控冻结的 count解释，不宣称 JSON schema 单独能验证 PG业务支持。
只新增局部 run `.gitattributes` 保留原始日志/XML/native观察 bytes，不对源码或全仓关闭风格/测试；审查必须核对该局部范围。

## 7. 评分与场景证据

E1/R2 的 SDK 合同兼容证据：source_freeze.json、dependency_inventory.json、三个 JUnit 文件与 SDK原协议输出。
F2/F3 的 unknown/四态不变量证据：新 test_public_extension_models 的分带、未知覆盖、空范围、task/type/error 与范围负例；它们仅为合同级，不计真实系统准确率或召回率。
U场景的可操作前后端链路、本卡 MCP六工具、CLI SDK打包、三类插件、actual Codex/Claude客户端均未由本片证明，仍属 R18 与后续集成范围。

## 8. 结论与下一步

本片 awaiting_review；主控需创建非作者 fresh reviewer，对固定 source SHA+raw inputs 复跑关键负例及495合同回归。
review 通过后再合并与另client/MCP实现、后端 producer；新增 producer 必须实际核 claim/event/ACL和完整真实请求分母，不用 fixture算live。
没有 push、accepted 或 R18/G-E 阶段门声明。安装包原五文件、SDK client/MCP协议与主控App不在此源码commit。

## 9. 文档修订

2026-10-16T21:18:13+08:00：首次真实写作与证据落盘，作者 /root/r18_public_extension_typed_models_implementation。

2026-10-16T21:20:21+08:00：材料首次 git diff --cached --check 真实退出2，自写JSON使用CRLF且已设-text，Git把CR当行尾空白；未commit，原工具输出未完整保存，21:19:55+08:00定向重现exit2保存 material_diff_red_recheck.log。只把作者自生成metadata JSON改LF（不改时间/命令/结果数据），原始CBM JSON、日志/XML与native观察raw bytes保留；CBM返回追加局部-diff属性，其余自写metadata仍参与diff检查。源码SHA未变。


## 10. SourcePage 模式一致性追加 · 2026-10-16T21:23:02+08:00

追加写作开始/结束时间：2026-10-16T21:23:02+08:00 / 2026-10-16T21:23:02+08:00（实际系统时钟）
新增最终源码 SHA：be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958
原源码2bb2e122/495与原材料a45ae4d9历史保留，前文其所属验证时间与SHA不替换。
新增两业务路径：models.py 的 SourcePage.require_unique_sources 增两行；新增test增加三个必要case；__init__ Git blob80a4c46b7374c10ba5d6eea10afc462360712e74不变。

client并行作者发现 page.data_mode=live/items[*].data_mode=fixture 被原2bb2接受，反向也接受。
预期是用户要求的真实/演示隔离标记一致；实际该页可在总模式上误导调用方。根因是原模型只分别校验枚举，没有跨页/项校验。
主控批准按原 CR 和用户 fixture/live 分离不变量修复，不改冻结 schema、不发明 mixed、不动金标/分母。
只拒绝混合模式；零item仍保留明确page mode，不能把空页或enabled当已验证的live来源能力。

先加双向负例：2026-10-16T21:20:56.863111+08:00–21:20:59.400625+08:00，真实exit1、124passed/2failed/0skip；new_models_mode_red.log/XML保留。
两行修复后：2026-10-16T21:21:19.489778+08:00–21:21:21.699774+08:00，exit0、126passed/0failed/0skip；new_models_mode_fix.log/XML保留。
style/format/mypy strict：21:21:24+08:00–21:21:25+08:00，各exit0、原始 *_mode_fix.json/log 记录精确时秒。
最终唯一 case126+原349+旧schema23=498；不是把122/123/126或两次349相加。
旧349/23已在原源码运行，后两行仅新SourcePage，九其它新DTO和全部旧models正文不变，旧SDK调用方无SourcePage读取；没有无必要第三次跑349。并行client把新SourcePage接入后必须重新运行其相关回归并独审。
52 final inputs 及49 unchanged依赖见 dependency_inventory_mode_fix.json；独立刷新索引名称r18-public-models-be4b9114，缓存仍工作区外，cbm_mode_fix_index.json保留真实返回。
本片仍awaiting_review，实际后端producer按同mode出页、PG观察真实性、live/人工仍未证明。
