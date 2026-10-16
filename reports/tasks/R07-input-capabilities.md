# R07 · 长文模型输入与固定版本 taxonomy 能力切片

状态：awaiting_review；本切片实现 complete，整 R07/default App 为 partial。未签 accepted，未 push。代码冻结 `7dae1d82363d8459f3546fee4b92137559dcb5aa`，工作树 `D:/wt/r07-input-capabilities` / `codex/r07-input-capabilities`。基线 e310f773；先合限定 Ship R10 ff5aa737（无冲突），再合主控依赖 checkpoint48b56033（本 WT cherry 为475dea5）。R10当前读保证范围仍受主控 canonical CR-R10_graph_fix2_review_scope.md 限定，不扩大旧保证。

改动文件：新增 enrichment/evidence_selection.py 与 taxonomy_inputs.py；修改 model_fields.py 输入构造及模型已见范围检查；新增直属 unit、contract、security、integration 四个测试；新增 CR-R07_bounded_evidence_and_taxonomy_inputs.md。共8 code/contract files，1374 additions /37 deletions。没有改 inputs、field_sources、公共 context/schema、source catalog、HTTP网关、API、worker、settings、迁移、锁文件、progress。依赖变化来自主控独立提交，本切片没有编辑其 manifest/lock。

输入与输出：`select_field_evidence(documents, dimension)` 返回 FieldEvidenceSelection，包括 source/document/revision/hash/version/URI 全依赖、原 block-relative Unicode selected/omitted ranges、遗漏 block IDs、完整性、匹配线索及有界模型文本。词法排名按不同匹配线索数量，平分按原 loaded document/block/range 顺序；不是语义检索或字段真实性确认。保留完整可容纳 block；超大 block 只选完整且可引用的行。固定50条/16384字符/65536 bytes不扩大；一条报告计入50条，至多49个证据记录。原源文档和 roster 完全保留，不伪改 blocks_complete/content_coverage。没有命中的过大输入仍明确失败/未知。

`model_fields` 首wire前完成所请求各维选择，防止一个后续维的输入失败已经消耗 earlier wire；单维1024 tokens/20s/一次wire/no repair保持。模型引用除了原 validator 的全文验证，还必须落在已送范围；完整真实却遗漏的 span 无法借真实身份混入。遗漏的前提仍从原文本检查，不能通过截短输入绕过。结果仍 model_hypothesis/pending；选择不完整给 candidate limitations 和新的内部 ModelFieldResult.input_selections，空回答仍 field_evidence_missing，不产生 not_found 或安全结论。prompt r07-model-fields-2、selection r07-field-selection-1、schema原r07-model-field-extraction-1。

Taxonomy 窄接口：`parse_cwe_catalogue(raw, CatalogueProvenance)` / `parse_atlas_catalogue(...)` 返回 TaxonomyCatalogue（版本、源/文档/修订、raw 与解压内容hash、来源locator、真实supported_ids）。ATLAS additionally 提供从同一 AST matrix/technique 项取得的170条完整 identifier 原文行和 Unicode 坐标；CWE XML用不可歧义 XPath。ID成员性不等于事件映射。正式 `load_taxonomy_catalogue(session, store, authenticated scope, visibility scope, revision_id, kind)` 仅从现有PG current来源加载；READ_PUBLIC、source/doc/rev三层ACL在IO前和锁后复查，父行FOR SHARE，CAS read_verified与长度重验，缺失/损坏/不可达区分。没有任意URL、模型、shell、PoC执行或环境密钥读取。

实证缺口：当前 EnrichmentContext 字段仅event/version/revision_ids/CVE/rule_version；不存在 valid_cwe_ids/valid_atlas_ids，也没有 default官方taxonomy loader。实际新组织 ATLAS URI 不被现 field_sources 的旧组织URI规则接受。事件最多20来源，与taxonomy依赖如何合并、taxon完整成员性和 full_text/blocks_complete 的区别需要主控正式合同接线；不能把catalogue投影偷偷标全文。现有 public context未扩展。源/文档/revACL loader已在真实PG测过，但collector注册、默认事件加载、App、持久step覆盖metadata、policy指纹还未接通。

真实固定公开GET：先经主控批准最多4，再追加2，actual HTTP6次：GitHub commit API200/10116 bytes，旧组织YAML404/0 bytes，旧组织schema404/0 bytes，CWE4.19 ZIP200/1883899 bytes，新组织YAML200/452399 bytes，新组织schema200。全部redirect0、各22s、原4请求总90s/追加总45s、每次DoH2s固定Cloudflare，无凭据、付费/模型/测绘调用0。原字节CAS在仓外 `D:/dianzi-private/r07-taxonomy-cas`，不删除、不替换。CWE4.19实得969 IDs，ZIP hash f7a7705971796ac26aed238f62594e24ff028549586b37150da32d9bbd58c554，XML hash952e31ada53436bbfc6dab873adeb00d08870eec88d00075b38defd1142b8ddb。ATLAS明示deprecated legacy5.6.0，full commit3259f388d19cbcca11bacf12a0ef97f4198f711b，170 IDs，raw hashc9c23971d0db07e2782423d795a20e78d5c2c9bcdc78fc67e24530657daaec41。费用unknown，不冒称最新taxonomy。

实际命令及最终自动结果，均helper保存完整命令、cwd、Asia/Shanghai起止、exit、JUnit和计数：

| 层 | 命令 | 结果 | 材料 |
|---|---|---|---|
| unit | `backend/.venv/Scripts/python.exe reports/runs/recovery_r07_input_capabilities_20261016/check_inputs.py unit` | exit0，18 passed/0skip | unit_060704 |
| contract | 同 helper `contract` | exit0，6 passed/0skip | contract_060852 |
| security | 同 helper `security` | exit0，7 passed/0skip | security_060704 |
| realPG integration | 同 helper `integration` | exit0，12 passed/0skip | integration_060853 |
| 原模型回归 | 同 helper `regression` | exit0，143 passed/0skip | regression_060853 |
| 字段相关回归 | 同 helper `fieldset` | exit0，102 passed/0skip | fieldset_060148 |
| static | 同 helper `static` | ruff/check、format、mypy三source、diff-check全exit0 | static_commands_060853.json |

原模型143的实际构成为 model_fields56 /single_model_dimension41 /model_field_root_causes46；不按旧摘要的122伪写计数。自动测试合计288 passed，但这不是正式评分、live或全卡通过。PG helper只访问明确test用户、独立新test_dianzi_r07_inputs_*数据库；原有 conftest核对隔离身份，凭据从指定WSL私有connection.json仅进程内读取。真实来源67-block NVD由既有fixtures/recorded/nvd_api_20261015_public.json重新经原source worker保存入PG，原文和全部block/hash不改；本次仅离线真实codec的版本维1 wire、1024 tokens、empty→unknown，不声称真实模型输出正确。另67块synthetic正/否/未知、条件遗漏、恶意提示/egress、未见span用例有直接断言。

失败/未通过全部保留：first_pure 从项目root运行导致3 collection errors；最外PowerShell最终tail返回0，pytest没有业务通过，JUnit明示collection错。second_pure 为2 failed/28 passed（synthetic正例标点不满足原版本边界、SafeLoader接受无关set tag）；修fixture为明确分号边界、拒绝非目录tag。contract_060039为wire键误读（evidence_texts而实际untrusted_evidence）；改测试核实际codec。integration_060106为1 passed/10 failed，fixture sources.name唯一冲突；每次新唯一fixture name后12通过。regression_060148为142 passed/1 failed：legacy four维在后维输入fail前先调用ATLAS；统一首wire前完成preflight，原测试不改期待，143两次复跑通过。起初一次静态命令错工作目录、一次mypy无stub及未format，均工具/类型环境问题，未冒充业务测试失败；其完整起止未记录，不补造。

额外 full official schema 探针仍红：同固定commit的 dist/schemas/atlas_output_schema.json（hash17349bf6127b69a2b366aa6c18a8a9d0034545c88186e8120269f94b51f263f1）对原legacy bytes检出126 anyOf错误，replay_catalogues.py exit1。首失败的subtechnique要求subtechnique-of/tactics，原字节使用specializes；schema/原文未修改。保留 first断言失败和结构叶观察；这不否定已逐条验证的170 member IDs/identifier coordinates，但不能称官方全schema验证通过。旧组织404和595e42a9旧NVD field_input_budget_exhausted/0wire红例均保留；不改阈值/gold/冻结probe。

CBM：第一次业务编辑前自己WT backend/src独立r07_inputs_backend index/schema/architecture/extract_model_dimension调用链+rg；冻结后刷新index/trace。initial CLI起止没有写盘，记not_recorded，不依mtime补造；exit0/output保留，frozen source trace明确新selector→original field_sources→real GenerationClient链。原权威PG和对象服务复用，没有第二套业务真相。

材料检查补充：首次材料eb6daced新增原始pytest失败log的trailing whitespace、CBM输出末尾空行；材料diff-check失败，源代码冻结diff-check仍exit0。最外PowerShell继续commit并返回0不代表内层检查通过。专用check_material_diff.py保存真实独立命令、退出码和原输出。没有删改raw日志，已报告主控决定是否为此run的*.log按现有规范做局部attributes；本实现不擅改公共attrs。

评分证据：R07/F2/P2提供有界真词法检索、可回溯引用、严格hypothesis/unknown和taxonomy真实成员性基础；E1提供输入范围/权限/CAS/并发读锁/注入边界。没有准确率、性能、多跳或稳定时长评分结果。frontend/e2e/live模型/manual、全默认App/worker、taxonomy自动collector为not_run或blocked_live；官方全schema探针failed。

主控后续建议：复核本冻结SHA；把PROMPT_VERSION/SELECTION_VERSION纳入credential-free policy/幂等fingerprint，旧任务不自动重算；持久保存input_selections的无全文覆盖摘要和原依赖。受控登记两个官方固定来源、保存原bytes/版本/ACL后接catalogue loader；现代URI、完整taxonomy成员性投影、context容量和正式field support规则先走单独CR。无法安全支持时明确unknown/blocked。禁止伪造旧官方URI、full-text coverage或付费live成功。此处不继续下一任务。
