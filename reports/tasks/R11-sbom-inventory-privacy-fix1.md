# R11/T24 · SBOM URI展示边界修复

状态：awaiting_review；原非作者reviewer待复核。本次只修已报privacy Must与实际复现的同根因展示路径，整个R11/T24/T28仍partial。无push/progress/accepted、DDL/依赖/auth/已审parser修改。最终代码冻结 `6942c65efd5df013c077275cbb6d8cfec3585080`，在74285153、b4e26971的安全投影与显式None来源校验上补严格有界解码和重复引用逐次校验，切片parent `c0369e6b7cb71c19f7594da8737e6bb3717893f3`，WT `D:/wt/r11-sbom-inventory`。报告实际装订时间在本run收据；首次工具探索未完整逐项计时，不补写。

独立审查转来的18个PG自有探针15pass/3fail是一根因：externalDocumentRefs.spdxDocument的数据库连接URI、file URI或HTTPS userinfo URI经POST201之后被sidecarGET原样返回，违反原CR内部路径/连接串不返回约定。作者最小unit首红同3输入，6:38:28–6:38:30，exit1/3failed，原日志/XML保留。不能因原411通过而消除该缺陷。

## 源码与合同变动

修改 `assets/sbom_inventory.py`、`sbom_inventory_contracts.py`、`inventory.py`；新unit/真实PG privacy测试；在owned CR-R11_sbom_inventory_proposal补兼容、迁移、回滚和测试影响。原 `sbom_parser.py`、`manifest_parser.py`、inventory/sidecar模型、shared JSON、API app/auth、迁移、锁、公共schema、所有原测试、reviewer文件与progress均不改。

安全展示共享投影仅离线使用标准库urllib/ipaddress及已锁PackageURL，不做DNS/HTTP。HTTP(S)须完整credential-free authority、无query/fragment、无authority百分号/反斜杠/控制；显式local/internal host与非global IP拒绝，authority尾点归一再检。必要UUID/CDX规范ref与安全opaque ID可保留；其他URI/path变为显示限制。该语法判断不证明域名公网解析、文档可达或checksum声明真实。

sidecar统一公开schema2，document_uri可为None；typed redactions保存精确安全source_field_locator、固定unsafe_uri_or_path原因、引用替代alias或None。原document ID/checksum保留，raw/fullJSON/combined/projection摘要不变，未知和composition声明不变。危险CDX source_ref、edge两端、composition三组引用同值使用同opaque alias，保拓扑；客户端原值恰为生成前缀也当原值hash，不与真实危险ref合并。再次schema2投影要求完整typed形状、scope/hash绑定、确切locator/reason/replacement_ref，额外/重复/伪标记或未处理危险值503；不是只凭startswith或PG metadata存在信任。

历史schema1先校验PG绑定再相同投影返回schema2，不重解析raw、不改不可变历史。新payload显示层冻结schema2，私有原文仍完整，source adapter/spec/来源hash保持。旧安全URL仍返回。schema1缺redactions按空兼容；故意伪metadata不被当为历史安全证据。

追踪发现另两个实际同根因：PURL编码version可载credential URI且原profile合法接受（只打印accepted/purl_retained布尔，未将URI值当接口凭据）；URI作为未知JSON字段键会进入unmapped JSONPointer。经主控批准，仅SBOM公共snapshot隐藏不可展示purl为已有nullable None，覆盖POST、重放、get/current/list/history，私有canonical/组件identity/hash不改，JSON/CSV保持原行为。sidecar从冻结snapshot payload标对应purl位置，不读raw解析。URI/path样式未知键使用稳定安全locator占位；普通name/display或自由文本不做万能secret黑名单。PURL qualifiers/subpath仍由原pure profile明确拒绝，不偷放宽。

同批独立复核在742又发现3个真实失败：未知字段URI键5/8层percent编码绕过四轮解码；两条edge共享同一定位时，首条正确alias使用marker后，第二条改安全外观的不同ref仍GET200。b4的None来源校验保留。新最小unit于7:17:43–7:17:45真实3红；新9个PG于7:18:22–7:18:26为7failed/2passed（5/8层及非法UTF-8的新2/历史1、重复错值），原日志/XML完整保留。补丁仍最多四轮，严格escape语法/UTF-8，非法或残余percent编码一律固定占位；不无限解码或只再加轮数。占位hash原JSONPointer反转义字段字节，避免不同编码的相同URI合并定位。所有相同定位的ref逐次一致且必须匹配typed reason/alias，错值在安全URI判断前拒绝503，合法重复同值200/拓扑不变。没有新的DTO字段、parser/原文/摘要/DDL变动。

## 真实验证与保留红例

所有Python命令cwd为本WT/backend，解释器为本WT/backend/.venv/Scripts/python.exe，完整argv/上海秒级起止/退出码/log在新run commands.jsonl。pytest均--no-cov；本轮不声称全suite覆盖率、正式评分、性能SLA或live。

| 范围 | 实际结果 |
|---|---|
| 原pure337的完整argv原样复用，只改JUnit输出目录 | 7:19:28–7:21:34，exit0/337passed，0fail/error/skip |
| 原真实SBOM PG/HTTP28 | 7:20:37–7:20:49，exit0/28passed，0fail/error/skip |
| 原JSON/CSV真实PG46 | 7:21:27–7:21:35，exit0/46passed，0fail/error/skip |
| 既有privacy unit33输入/断言不变 | 7:19:13–7:19:14，exit0/33passed，0fail/error/skip |
| 既有privacy真实PG22输入/断言不变 | 7:19:40–7:19:50，exit0/22passed，0fail/error/skip；DEBUG产品日志否定 |
| 新followup unit26 | 7:18:47–7:18:48，exit0/26passed；冻结后7:23:05–7:23:06联合原33为59pass，均0fail/error/skip |
| 新followup真实PG9 | 7:18:52–7:18:56，exit0/9passed，0fail/error/skip |
| 原独立reviewer探针18复制原bytes作者复现 | 7:22:56–7:23:03，exit0/18passed，0fail/error/skip；作者复现，非独立签字 |
| 同批独立reviewer新增13冻结探针原bytes作者复现 | 7:22:05–7:22:10，exit0/13passed，0fail/error/skip；原11加None来源2，作者复现 |
| Ruff/format新增/改动7代码测试文件 | 7:22:28，followup_code_ruff/followup_code_format均exit0 |
| 全src mypy | 7:22:28–7:22:29，exit0/125source files无问题 |

原411分母完整保留并全复跑；第一轮新增55、followup35与reviewer18/13另列，不以重复运行累加通过数。新PG真实检查schema1历史/新2、raw byte/hash/canonical、幂等重放与current复用、analyst GET、引用碰撞/混合拓扑、PURL全路由、URI键、伪metadata503；原28/46保留跨tenant、corrupt binding、immutable、回滚、history及并发。原10k完整容量仍复跑通过。新矩阵含编码1/4/5/8/12/64层、非法/截断percent、非法UTF-8/编码代理码/NUL、正常Unicode、不同编码键占位不碰撞和重复同值/错值。显式None URI必须有对应redaction来源，原33/22文件与DTO从b4到6942逐blob核不变；所有c036原测试文件也逐blob核不变。表中411与PG在最后仅等语义Ruff换行前执行，冻结后59联合unit和原18再次执行；业务逻辑无后续变动。

最后guard不改变合法URI显示。b4复跑原337时harness固定复用了original_pure337_final输出名，前一次绿色原输出被覆盖，只保留原命令收据，不能把旧开始时间冒充新log的时间；当前该log/XML对应7:11:46–7:14:00，原失败日志未覆盖，原411的上轮冻结完整材料仍在c036/原run。followup改harness允许明确独立输出标签，新337为original_pure337_after_followup，不覆盖上述文件。

新PG第二轮为21pass/1fail（6:51:02–6:52:51，107.52s）：失败在fixture auth/login返回503，SBOM尚未上传；未定位该503根因，也未改auth/时间预算/阈值。相同suite6:53:58–6:54:07真实复跑22pass；最新DEBUG复验22pass。此前19case首轮6.54s全绿不叠加。不能称登录故障已被URI补丁修复，红日志保留。

外部probe首次14pass/4errors是共享register_sensitive_failure_value fixture没有被自动发现，4个API探针未执行。仅harness加`-p tests.conftest`装入原共享脱敏/资源fixture后18通过；probe与resource副本未修改，原reviewer路径不写。首mypy5错误是循环变量复用类型冲突，改语义变量名，无Any/cast/ignore；新Ruff2长行只拆等值字符串/URL构造，原输入不变。首次apply_patch上下文不匹配、个别工具路径/PowerShell参数探索错误保留事实，不计业务失败，不补造未存工具日志。原3泄漏红、初类型/风格/fixture错误均在run保存，未skip或修改原断言。

同批reviewer冻结13副本SHA256 `1b6862cd8b1b35572513ff698788768d826d8bfc885146021c66f510bd87a8d5`，helper副本SHA256 `ac9bae2de1b3f48c0d52f2c39f54f66ac2466418275d80991c1915937c5bc44b`；两者逐字节复制，不修改原独审工作树。PURL case最初version与encoded PURL version矛盾由原reviewer自行纠夹具，非本业务修复，不把该夹具红改记为已修漏洞。独占author测试库加原shared hook与写前敏感值脱敏。独审初红/自纠记录仍保留在其独审材料，作者新run保留同输入最小3红和新PG7红。新format初红仅2源码换行、后1个seal脚本格式，机械formatter后检查绿，没有修改测试输入/断言。

实际PG16.14只用loopback25432独占test数据库；SBOM/privacy/review前向0019，legacy前向0018，再仅测试创建sidecar单表（test_table_create_not_production_0022）。连接配置只进内存，无DSN/口令到argv/报告；数据库不删除，不downgrade，不碰生产。全部URI/资产为explicit synthetic fixtures。caplog DEBUG否定产品日志包含被保护URI/marker；原未改probe的case名称含synthetic URI，本run测试材料保留标明的合成输入，不能误称所有证据文件没有这些fixture字面量。

## 追溯、限制与下一步

写业务前assets独立CBM index/schema/architecture/freeze trace与源码rg定位；外部src源码未改，复用原source图，最终再独立source/assets索引和safe-sidecar trace。6942冻结后7:23:37–7:24:10新独立followup source/assets index/schema/architecture/trace，均exit0（src1509/7879、assets261/1171；src嵌套assets排除由独立assets图补）；结合源码rg核GET/POST/history四路径，不以缺失嵌套lambda图边推没有caller。source/Git-LF与所有run原字节在manifest及frozen_source_proof核；原reviewer副本hash与原输入一致。新run仅本目录attributes保raw并承认CRLF；无全局attributes改变，报告另gzip精确原bytes。

无新外部调用/下载/费用，未读取chat/model/provider秘密/金标；新代码不运行URI、PoC或任意shell/SQL。生产0022/API app、SBOM frontend/browser_e2e、产品live/manual仍not_run；本fix不以synthetic PG验收真实资产范围或完整R11。

F2/F3：仅来源声明安全展示、范围未知保留、私有历史与证据hash不改。E1/D1：独立缺陷的实际首红与对应复测、工程类型/风格与raw材料可追溯。P2：未产生正式准确率/召回率或降低评分门槛。

下一步：原非作者reviewer对新冻结source/material定向复核Must及自有向量；主控再决定装配/迁移和前端切片。回滚须保留安全view或停用SBOM/sidecar显示，不可重新透传旧URI，也不能删不可变原文/sidecar。

未检查：生产迁移/正式app、SBOM前端/browser/live/manual与真实URI可达性；普通自由业务文字不属于此定向URI隐私扫描范围。

实际最终装订时间：2026-10-16T07:25:55+08:00。
