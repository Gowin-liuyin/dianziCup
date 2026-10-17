# Root · 批次16公开问答、请求边界与前端集成

文档首次创建时间：2026-10-17T09:11:38+08:00
本次写作开始时间：2026-10-17T09:11:38+08:00
阶段：G-C保持in_progress/partial，G-E能力为独立准备
任务状态：awaiting_review（本冻结批次）；整R06/R17/R18仍partial
工作分支：codex/full-delivery-recovery
基线代码SHA：0f8c1f6d047387cfca8a62f8dbc352b8c6415b96
已审代码SHA：源切片版本见导入凭据，Root新默认装配尚待新非作者审查
提交/push：本报告写作时尚未发生；不是阶段通过

## 行为与必要改动

复用现有GroundedQuestionService、PG认证/配额、冻结AskRequest、Assessment条件判断、SDK MCP HTTP，以及现有问答工作台。Root默认App只构建一份问答服务，旧/v1/questions与公开/api/v1/ask共享该对象；公开Ask严格请求体与Idempotency-Key在OpenAPI中按冻结合同展示。原三参数router调用兼容，新增可选provider是默认共享实例接线所必需，没有新增依赖或平行业务事实库。

导入207d严格JSON深度异常收敛、36b9组件选择器及合规PG输入、3873公开ASK、36fb组件条件与凭据边界。bare组件不能借资产配置得出排除结论，AnyOf/AllOf继续原业务规则；MCP HTTP拒绝query与Cookie凭据混入。权限403清除问答私密输入/答案/重试键，CSRF拒绝保留同key重试；前端e2e监听真实/v1与/api/v1路径，并用独占run目录保留分组产物。4fa仪器只批准固定无override调用，标准Playwright输出override的限制保留。

23个代码文件及raw哈希见reports/runs/recovery_reviewed_integration_20261016/root_batch16_code_freeze.json。四份导入凭据分别以reviewed_batch16_{import,public_ask_import,boundaries_import,frontend_import}.json留存；review_copies列六份独立源报告原字节与本批副本，raw与Git规范行尾分别核验，不能声称相等而不检查。

## 实际验证

工作目录D:/dianzi/backend；真实逐命令起止、退出码、原stdout/stderr/XML与NativeJob收据在同run。当前组合离线315不同用例：默认ASK77、组件60、JSON35、请求适配77、SDK HTTP66，全0fail/error/skip。mypy6源与Ruff受影响文件均exit0。公开ASK77在边界导入后另跑，原77不重复相加。

Root前端72不同组件回归（questions/client/App），strict TypeScript与实际frontend ESLint均exit0；这72与独立e2e仪器72是不同范围，报告不混同。当前Root浏览器业务执行/e2e/live/manual not_run，前端build本批not_run；先前作者/独审构建不代签本组合。用户tsconfig.tsbuildinfo始终SHA256 3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d，tsc本批--incremental false，不stage该文件。

普通Win完整峰4–7≤10，所有own子进程残留0；Native512MiB/process、1GiB/job、CPU_RATE833/24核（约2CPU）、每命令60s。无本批付费模型/测绘调用；费用unknown。离线fixture无PG/Redis/source/model，不计live。

独立源测试：207d严格JSON750去重、36b9 selector真实PG7、3873 ASK真实PG18、36fb界限172去重，见各报告。它们不是Root本23文件组合真实PG证明。Root新默认ASK/共享provider/OpenAPI必须由新的非作者冻结后检查并准备实际PG/真实入口。修改前已从0f真实CBM App调用图和源码/rg核到create_application→build_question_router→build_question_service→retriever/models/PG；索引属于0f，待新候选刷新，不能代签当前图。

## 本轮具体问题与处理

- Root ASK首次78条XML条目为67pass/9fail/2error：新增断言错误地从顶层取code、FastAPI嵌套router静态扁平枚举失效、超深参数自动ID触发Windows路径长度。只修新增oracle读取error.code、采用实际HTTP路径与固定短参数ID；原红保留，未改产品合同/金标/阈值。新77实际通过。
- Root SDK首次收集exit2/1error：base解释器没有处理已安装pywin32的.pth，MCP导入找不到pywintypes。新隔离启动显式site.addsitedir处理相同已安装site，未增依赖/改锁/删例；同66随后通过，旧红不覆盖。
- Root boundary先前已证的配置借用与query/Cookie混入由36fb关闭，独审限定结论仍不覆盖完整公开六工具。
- f316 typed绑定修复由新独审通过275+3离线与17真实PG；09:01:08至09:02:08分5有界窗，实际head0031，物理目标2+sampler1、Source OID保持、exact ownDB清理0。真正reader跨lease235.095ms后拒绝。此源码尚未导入Root本批，旧15/1与同txn0/1封存。
- 52caf风险汇总新双来源仍真实40P01：09:03:17.156至27.748，writer持SourceB等publication、reader持publication后扩读SourceB；1真实failure非setup。作者正在独立新WT修bounded cohort前缀锁。原grades4实际1pass/3setup UniqueViolation来源固定name撞名，单列输入修复，不冒充业务通过，原11函数/grade oracle不改。
- Source912仍未ready/6h；新的CORE6b86/OPSf418/helper5e39迁移与诊断限定审查中，当前actual仍37/810/9e。Root08:04:33 fresh17是旧actual关闭证明，不是新tuple安装/启动成功；累计guardian37.6875与ledger42/450不reset。

## 并行与文件所有权

Root独占App/公共合同/schema/迁移/锁/progress/文档/Git与秘密资源。R06作者与新reviewer仅独立控制WT；typed原作者/独审仅绑定与自己证据；risk作者/新独审仅汇总/cohort/直属输入与自己的真实负例；R17原独审定向复核4fa，Root导入限定切片；plugin新独审109f唯一deadline问题已复现，新作者83cd在另WT修，未装配真实quota/tool ports。各固定源码与材料SHA在review/导入凭据；并行源码不相互覆盖，CBM窗口独占、真实PG Root逐窗注入环境，子Agent无push/accepted权限。

## 合同、评分与剩余工作

Root追加CR-R06固定pin迁移最终helper raw/两精确attrs与CR-R18内部Actor异常导入集合澄清；不改原T映射、Gold、门槛、分母、cookie/HTTP到期合同。保存失败、unknown不等于safe、引用存在不等于支持、当前不覆盖历史继续有效。

本批为P3/E1及U06/U13的局部接线/权限证据；多轮多跳、真实9角色职责、全部变化历史、公开tasks/stack/插件host ports、全UI操作、持续来源、正式评测、R24-A→R23→R24-B仍有内部工作，双人gold0/授权资产范围/CNNVD下载等外部项也未完成。G-C不能过门或push为accepted；最后核对远端仍G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。保护原有push台账、Root-batch13-index.md与用户未提交文件，不纳本checkpoint。下一步冻结23文件候选给新默认入口review，Root实际新Source迁移启动、集成f316及真实getter/publisher、复验risk新cohort和浏览器路径。

本次写作结束时间：2026-10-17T09:11:38+08:00
最后更新时间/证据截止时间：2026-10-17T09:11:38+08:00
修订记录：本次首次创建，Root据真实收据记录当前组合、独立源边界与未通过项。实现编写总时长历史未单独记录；测试窗口不称持续采集窗口。


## 前置状态纠偏与原始日志 · 2026-10-17T09:15:00+08:00

本批scripts/verify_plan.py原exit1：STATE_RECOVERY_DEP_INCOMPLETE R02→R01。Git0f基线已是R01 needs_changes/R02 accepted，checker与依赖合同未改。按已有前置回退规则将当前R02转awaiting_review，保留原accepted完整历史、implementation与冻结测试证据；不会把R01改绿或改checker放松规则。R02事实持久化的旧源独立证据仍有效，当前整包前置需复核，历史G-A/G-B已推冻结SHA报告不重写。新默认入口review追加R01当前Engine释放/失败路径与依赖重验。

全staged diffcheck原exit1仅四个pytest原始失败stdout/XML尾部空白。只对明确四文件路径加-text -diff保原raw，其他本批原始收据精确文件-text；业务/文档继续正常diff/style检查。不是全仓禁用，不改变失败数量或原始字节。

前置传播补充 2026-10-17T09:15:32+08:00：[{"id":"R03","unmet":["R02"]},{"id":"R04","unmet":["R03"]},{"id":"R05","unmet":["R04"]}]。只保守回退当前整包accepted到awaiting_review，不更改已证能力切片、实现、原测试、历史阶段SHA或checker；新默认入口独审核R01及传播是否可关闭。原整暂存再次check的CRLF错误真实保留：精确原始文件增加 whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol，将CR作为合法行尾；只有原四份带pytest真实尾空白的失败log/XML -diff。其他代码/文档仍全部正常检查。
