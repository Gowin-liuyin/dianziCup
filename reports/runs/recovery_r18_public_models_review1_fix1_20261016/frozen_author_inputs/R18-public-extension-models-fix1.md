# R18 · 风险完整性资格修复 fix1

文档首次创建时间：2026-10-16T21:42:41+08:00
本次写作开始/结束时间：2026-10-16T21:42:41+08:00 / 2026-10-16T21:42:47+08:00
最后更新时间/证据截止：2026-10-16T21:44:22+08:00 / 2026-10-16T21:44:22+08:00
实际执行开始/源码冻结：2026-10-16T21:30:41+08:00 / 2026-10-16T21:39:57+08:00
实现 Agent：/root/r18_public_extension_typed_models_implementation
独立审查：原非作者 reviewer 待固定源码定向复核；作者不自签。
任务状态：awaiting_review；本修复实现状态：complete；整 R18：partial。
分支：codex/r18-public-models-fix1；目录：D:/wt/r18-public-models-fix1
基线材料：08fb9623f4cdda0facd1314ab8174376a6504798；原 models 源码：be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958
已测候选源码：011ea225d18b7511a19d7d6056288f799bb83f20；已审候选源码：待独审。
提交/push：源码只两明确授权路径本地提交；未push、未accepted。

## 1. 原问题与冻结范围

原 be4 的风险 DTO 已有日期/UUID、分带、finding绑定、未知范围基础约束，但没有完整资格核验。
独审给出同根因九条稳定 DID NOT RAISE：complete confirmation=unknown/conflict 直接Envelope与succeeded TaskResult联合共四条；complete supported无grade、excluded无citation、excluded无assessment_id三条；partial未知/缺grade仍none_confirmed两条。
这使客户端可能把不充分结果展示为本范围无确认高风险，违背 CR-R18 “缺grade/证据/未知不可complete/none_confirmed”。

只改 models.py 的 RiskSummary/StackCheckEnvelope，新增直属 test_public_extension_models_fix1.py。
原报告/test/schema/oracle、be4/08fb历史、client/MCP/CLI/包装/锁文件/主控状态一字未改。
原独审两probe原字节复制：test_independent_models.py SHA36f92cdaf3faab7a500befd29b878cee3aba320242ded236d421f19364c40384；test_complete_support.py SHA74bb7251e00f652b055815d336321b4948a578f95488703e35366b149fb75de8。
它们原hardcoded ROOT只读取冻结schema；D:/wt/r18pm-r1 schema和本WT逐字节相等，未修改probe常量、期望或threshold。

## 2. 最小修复与复用

RiskSummary.complete 拒绝 unknown/conflict confirmation；none_confirmed 必须 complete，原 current/unknown-index 保护继续有效。
Envelope.complete 的每行必须 current、具有 assessment_id+引用；supported_applicability 还须保留该index的有效 RiskFinding。excluded_with_evidence 依然不强加CVSSgrade，要求自身排除证据可追溯。
分级低于 minimum仍保留finding/引用，只不计confirmed；severity none/score0也保留明确grade。没有调低minimum或新增分带、没有新grade字段。
partial明确unknown保留未评估结果、较小evaluated_components；不擅要求 partial等号，不把grade集合映成全部unknown_indices。原status insufficient/conflict、stale/unknown freshness必要索引规则保持。
复用原Pydantic after validators、分带和现有字段；源码diff13行新增/2行替换，无新依赖/通用服务。

## 3. 问题闭环与真实失败

作者先补26例，第一次14passed/12failed，覆盖原九类并补summary-only incomplete、部分结果正例、完整低grade/排除、TaskResult与legacy CLI。
初修43独审probe中42pass/1fail：把partial未实际分级的supported旧结果也强制列入unknown_indices，误拒原合法smaller-count正例。原红保留；作者未冻结过严test原byte保存在 author_initial_overconstraint_test.py（SHAa7412802b5b85dd984106b4b8510f6c9fca95fbcb89579e11221c2fc5f55ba49）。
主控明确依原已冻结partial语义纠正，不改reviewer原43/oracle。自身未冻结例改成验证明确global uncertainty仍保留完整部分结果，并说明契约原因，未涉及人工金标/正式分母。
资格约束仅complete/none_confirmed，partial已明确unknown可保留部分未评估结果；最终原43全部通过。

最终SDK套件501实际500pass/1fail，原 TcpEvidence fixture.writer.wait_closed WinError10053→fixture tasks未discard，raw栈在sdk_all_final.log。
失败函数是 test_real_drip_total_deadline_and_peer_eof[body]，业务deadline/peer EOF记录已生成：total0.1409999999741558秒、deadline0.12、原io_timeout0.5、actual_peer_eof=['drip-body']。
这对应此前包独审已复现的原Windows fixture cleanup Should；models改变不被该旧SDK调用，没有修改旧helper/oracle/超时、没有skip。
仅一次同原body定向复验1pass，full501红仍保留，不能把定向绿改写成全套501绿；不重复全套直到碰巧绿。是否非本slice阻断交原独审决定，作者不判accepted。

## 4. 实际验证

下表每条cwd均D:/wt/r18-public-models-fix1；日志/receipt保留精确+08:00时钟；原始UTC若有仅为库日志。
数据全部显式synthetic fixture；stdio/loopback真实原协议IO不等于产品PG/live。--no-cov只用于SDK/JSON子集，不改全仓60%门槛或宣称全仓coverage。

| 检查 | 实际命令 | 开始/结束 | exit | passed/failed/skip | raw |
|---|---|---|---|---|---|
| eligibility_red | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest sdk/python/tests/test_public_extension_models_fix1.py --no-cov -q --junitxml=D:\wt\r18-public-models-fix1\reports\runs\recovery_r18_public_extension_models_fix1_20261016\eligibility_red.xml` | 2026-10-16T21:33:39.509654+08:00 / 2026-10-16T21:33:41.954079+08:00 | 1 | 14/12/0 | [eligibility_red.log](../runs/recovery_r18_public_extension_models_fix1_20261016/eligibility_red.log) |
| eligibility_green | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest sdk/python/tests/test_public_extension_models_fix1.py --no-cov -q --junitxml=D:\wt\r18-public-models-fix1\reports\runs\recovery_r18_public_extension_models_fix1_20261016\eligibility_green.xml` | 2026-10-16T21:33:59.226644+08:00 / 2026-10-16T21:34:01.578745+08:00 | 0 | 26/0/0 | [eligibility_green.log](../runs/recovery_r18_public_extension_models_fix1_20261016/eligibility_green.log) |
| reviewer_probes | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest D:\wt\r18-public-models-fix1\reports\runs\recovery_r18_public_extension_models_fix1_20261016\inputs\test_independent_models.py D:\wt\r18-public-models-fix1\reports\runs\recovery_r18_public_extension_models_fix1_20261016\inputs\test_complete_support.py --no-cov -q --junitxml=D:\wt\r18-public-models-fix1\reports\runs\recovery_r18_public_extension_models_fix1_20261016\reviewer_probes.xml` | 2026-10-16T21:35:29.915072+08:00 / 2026-10-16T21:35:32.724288+08:00 | 1 | 42/1/0 | [reviewer_probes.log](../runs/recovery_r18_public_extension_models_fix1_20261016/reviewer_probes.log) |
| reviewer_probes_final | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest D:\wt\r18-public-models-fix1\reports\runs\recovery_r18_public_extension_models_fix1_20261016\inputs\test_independent_models.py D:\wt\r18-public-models-fix1\reports\runs\recovery_r18_public_extension_models_fix1_20261016\inputs\test_complete_support.py --no-cov -q --junitxml=D:\wt\r18-public-models-fix1\reports\runs\recovery_r18_public_extension_models_fix1_20261016\reviewer_probes_final.xml` | 2026-10-16T21:36:45.934757+08:00 / 2026-10-16T21:36:48.133201+08:00 | 0 | 43/0/0 | [reviewer_probes_final.log](../runs/recovery_r18_public_extension_models_fix1_20261016/reviewer_probes_final.log) |
| sdk_all | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest sdk/python/tests --no-cov -q --junitxml=D:\wt\r18-public-models-fix1\reports\runs\recovery_r18_public_extension_models_fix1_20261016\sdk_all.xml` | 2026-10-16T21:34:42.724891+08:00 / 2026-10-16T21:35:29.699006+08:00 | 0 | 501/0/0 | [sdk_all.log](../runs/recovery_r18_public_extension_models_fix1_20261016/sdk_all.log) |
| sdk_all_final | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest sdk/python/tests --no-cov -q --junitxml=D:\wt\r18-public-models-fix1\reports\runs\recovery_r18_public_extension_models_fix1_20261016\sdk_all_final.xml` | 2026-10-16T21:37:18.232470+08:00 / 2026-10-16T21:38:07.559158+08:00 | 1 | 500/1/0 | [sdk_all_final.log](../runs/recovery_r18_public_extension_models_fix1_20261016/sdk_all_final.log) |
| legacy_cleanup_recheck | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest sdk/python/tests/test_independent_native.py::test_real_drip_total_deadline_and_peer_eof[body] --no-cov -q --junitxml=D:\wt\r18-public-models-fix1\reports\runs\recovery_r18_public_extension_models_fix1_20261016\legacy_cleanup_recheck.xml` | 2026-10-16T21:39:20.578105+08:00 / 2026-10-16T21:39:22.539536+08:00 | 0 | 1/0/0 | [legacy_cleanup_recheck.log](../runs/recovery_r18_public_extension_models_fix1_20261016/legacy_cleanup_recheck.log) |
| schema | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest backend/tests/contract/test_r18_public_extensions.py --no-cov -q --junitxml=D:\wt\r18-public-models-fix1\reports\runs\recovery_r18_public_extension_models_fix1_20261016\schema.xml` | 2026-10-16T21:35:36.336587+08:00 / 2026-10-16T21:35:39.574785+08:00 | 0 | 23/0/0 | [schema.log](../runs/recovery_r18_public_extension_models_fix1_20261016/schema.log) |
| style_final | `D:/dianzi/backend/.venv/Scripts/python.exe -m ruff check --config backend/pyproject.toml sdk/python/ai_intel_client/models.py sdk/python/tests/test_public_extension_models_fix1.py` | 2026-10-16T21:37:29.477770+08:00 / 2026-10-16T21:37:29.695660+08:00 | 0 | 非测试 | [style_final.log](../runs/recovery_r18_public_extension_models_fix1_20261016/style_final.log) |
| format_final | `D:/dianzi/backend/.venv/Scripts/python.exe -m ruff format --check --config backend/pyproject.toml sdk/python/ai_intel_client/models.py sdk/python/tests/test_public_extension_models_fix1.py` | 2026-10-16T21:37:29.470769+08:00 / 2026-10-16T21:37:29.697308+08:00 | 0 | 非测试 | [format_final.log](../runs/recovery_r18_public_extension_models_fix1_20261016/format_final.log) |
| typing_final | `D:/dianzi/backend/.venv/Scripts/python.exe -m mypy --strict --follow-imports=normal sdk/python/ai_intel_client/models.py` | 2026-10-16T21:37:29.420621+08:00 / 2026-10-16T21:37:30.121898+08:00 | 0 | 非测试 | [typing_final.log](../runs/recovery_r18_public_extension_models_fix1_20261016/typing_final.log) |

最终不同node总数：SDK501（旧349+原126+新增26）+原schema23+原独审43=567。
最终完整运行结果为566passed/1旧fixturefailed；定向重试重复原1例不新增分母；前次SDK501绿不是最终共享规则版本的全套绿。
原43通过含最初九条红与合法partial count控制例。新26含任务联合的资格阻断和有效partial正例、legacy CLI保持2（不凭新摘要之外旧协议给0/1）。
dtype/string/bool/date/id与原126保持；strict mypy读取models正文、lint/format均0。
两个完整SDK run各有唯一 native_evidence子目录；最终guard所覆盖fixture子段24loopback请求、32.952883秒、外部/产品/付费0，不冒称此24是所有native请求总数。

验证层：unit=passed（风险资格/新旧DTO子集）；contract=passed；完整SDK原协议回归=failed（上述一条旧fixture）；产品integration/security整体/frontend/e2e/live/manual=not_run。
模型/PG/来源/API付费调用0；未读取秘密/holdout答案，未知费用不计作产品模型0cost证明。

## 5. 调用方与索引

源码/rg核实RiskSummary被Envelope和TaskResult联合动态Pydantic路径使用；原client/CLI/MCP只消费旧StackCheckResult，新六工具接线由另一作者独立完成，必须合并后复验。
新26对TaskResult succeeded/partial两路径与legacy CLI未知退出码增加直接回归；原501覆盖真正stdio/TCP/取消/输出边界，没有只跑九负例。
独立CBM索引：r18-public-models-fix1-08fb9623→冻结后r18-public-models-fix1-011ea225，范围仅SDK source；get_architecture/schema/trace原始返回在run。
静态图没有Pydantic动态回调边不能证明没有调用；源码decorator和真实model_validate_json负例交叉核实。
缓存在/tmp/dianzi-cbm-r18-public-models-fix1-20261016，未提交缓存；排除秘密、holdout、用户资料。
dependency_inventory.json共54仓库输入，非owned Gitblob全部保持；另两固定reviewer probe SHA验证，原Schema字节相等。

## 6. 合同、限制与后续

原CR-R18资格语义落实，没有公共JSONschema字段、分带、threshold、评分、金标、正式分母、预算/超时、权限变更。
producer仍须PG核实际引用支持/claim-event归属/ACL、完整真实请求index与总数；SDK不能用DTO存在替代它们，live未接线不能计通过。
历史 be4/08fb/原498材料保持，不以旧绿给新代码背书；新增候选011ea225待原非作者定向复核。主控据独审结论调度六工具作者拉准确models blob32b48ca953f867d4d7819de94c352d7173312489，init仍80a4c46b7374c10ba5d6eea10afc462360712e74。
本片R18/T04/T32/T35/T51合同证据指向raw/JUnit/输入清单；不声称整R18、G-E、P2/P3或用户业务场景已完成。
代码阅读/编写未逐段计时，历史未记录；执行/测试/文档时段分别记录，不混称持续运行。
局部 .gitattributes 仅ownrun原始log/XML/native/CBM与两固定输入bytes，业务源码/自写metadata仍参与正常diff检查；不全局忽略规则。

## 7. 文档修订记录

2026-10-16T21:42:47+08:00：真实首次写作与完整失败/成功证据落盘；作者 /root/r18_public_extension_typed_models_implementation。

2026-10-16T21:44:22+08:00：第一次材料seal把own inputs中的两个pytest __pycache__列入显式清单，git add按原ignore拒绝exit1，未继续commit；原完整raw仅工具输出，随后同根因最小重现exit1/raw保存ignored_cache_stage_red.json/log。只在材料枚举排除生成__pycache__/.pyc，没有force-add、删除文件或新增全局ignore，源码/测试未变。
