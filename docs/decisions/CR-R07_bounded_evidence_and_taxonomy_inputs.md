# CR-R07 · 有界模型证据选择与固定版本 taxonomy 输入

状态：awaiting_review；实现切片，整 R07 和默认 App 接线未验收。记录：2026-10-16，Asia/Shanghai。授权：主控 /root 的当前独立输入切片授权、最多四个固定 GET 后追加两个新官方组织固定 GET；依赖由主控 48b56033 单独冻结。

问题：595e42a9 的完整 NVD 输入有 67 blocks，四个独立模型子任务均 field_input_budget_exhausted、0 wire。Context 没有 valid_cwe_ids/valid_atlas_ids 字段；默认事件 loader 不加载官方 taxonomy。现 field_sources ATLAS 仅信任 `/mitre/atlas-data/{full_commit}/dist/ATLAS.yaml`，该路径本次真实 404；实际新官方组织是 mitre-atlas。不得扩大预算、伪造旧路径可用或完整覆盖。

变更：model_fields.PROMPT_VERSION 从 r07-model-fields-1 到 r07-model-fields-2；输出 schema r07-model-field-extraction-1 不变。内部选择规则 evidence_selection.SELECTION_VERSION=r07-field-selection-1。原输入 50条、每条16384字符、总65536 bytes，以及单维默认1024 output tokens/20s/一次 wire、不修复格式均不变。使用固定字段线索作确定的词法排名，保留完整可容纳 block；超大 block 只保留完整行，不切断一行生成失实引用。全量维度选择在首个 wire 前完成；无法选择的 oversized/no-hit 输入仍失败/未知，不表示安全。

选择保留 source/document/revision、原内容与 block hash、block 与原始 Unicode offsets；返回 selected、omitted blocks/ranges、所有来源版本依赖和 incomplete。模型输入包含覆盖摘要，候选引用必须落在实际送入模型的范围内，并继续用未改的 field_sources 对原文全集校验。遗漏的条件不能借选段绕过校验；存活候选继续 model_hypothesis/pending，部分选择附限制。输入原文、PG roster、content_coverage、blocks_complete 不重写。ModelFieldResult 新内部 input_selections 字段默认空；现调用方可以继续读取原两个字段。

Taxonomy：新窄 parser 只负责官方固定版本 XML/ZIP 与 legacy ATLAS YAML 的受支持 ID、名称、原始来源定位和 provenance。CWE 要版本化官方 URI、XML 内版本和 raw hash 一致；ZIP 保留 raw hash 与解压 XML hash。ATLAS 要两个明确官方组织之一、固定40位 commit、legacy `/dist/ATLAS.yaml` 路径、raw hash 和合法唯一 technique/subtechnique IDs；增加新组织只影响新 parser，不改共享 field_sources。成熟 PyYAML SafeLoader 解析，拒绝 aliases、重复键、非受支持 tags，并限制原字节、深度和节点。v6 输入明确 unsupported，不冒充支持或 latest。

正式窄 loader 仅读取已有 PG current revision 和已校验 CAS bytes；必须 READ_PUBLIC，逐次 source/document/revision ACL 复查，读时对父行 FOR SHARE。返回来源身份、hash 与版本，不读取环境密钥，不提供 URL fetch、不自动注册 source、不自动添加事件关联/context、不发布事实。事务结束后来源可能修订，正式发布仍需完整 PG current/ACL 复查。

兼容/迁移：没有公共 schema、认证、任务、迁移、评分、金标、分母变更。主控须将新 PROMPT_VERSION 与 SELECTION_VERSION 纳入 server policy/幂等 fingerprint，旧持久任务和原失败日志保留历史，新策略不复用旧键。主控另外实现现有 step/result 中覆盖摘要的持久审计与受控 taxonomy 来源采集；本切片返回值不等于该接线已完成。

真实观察：CWE 4.19，969 IDs；ATLAS deprecated legacy5.6.0@3259f388d19cbcca11bacf12a0ef97f4198f711b，170 IDs 和 170 原始 identifier 行定位。固定新组织数据与同 commit 旧 dist/schemas 官方 schema 的额外全 schema 校验有126 anyOf errors，保留 exit1，不削弱 schema，不称全 schema 通过。窄 parser 的成员性验证与官方全 schema 检查分开报告；新组织 URI 仍不被现共享 field_sources 接受。因此 taxonomy parser/loader 的代码检查和受控抓取不等于默认模型 ATLAS 输入已经接通。

费用：仅六个已批准公开固定 GET 和有界 DoH，无模型/测绘/付费 API。带模型 codec 的自动测试使用明确 synthetic offline transport，AttemptMetadata fee=unknown，不写0费用。未授权新付费批处理。

回滚：在未接线时连同两个新增模块和 model_fields 修改回退到旧 prompt；保留 raw CAS、历史失败与任务报告。接线后主控同时回退 policy 指纹和入口，旧任务不得被新算法重解释。原文与金标不删、不覆盖。

验收：长67块正例/否定/未知、过大无命中、完整 Unicode 引用、未见真实 span、遗漏 qualifier、提示词注入、预算/egress拒绝、taxonomy ID/版本/源/hash/重复键/别名/不支持格式，以及实际 PG ACL、current、对象损坏、重放和并发读锁。原模型143与字段集102回归期待不改。新非作者 reviewer 复跑冻结 SHA；frontend/e2e/live模型/manual、默认 App 与自动 collector 留待主控明确接线，不计通过。

依据：官方 [CWE 归档](https://cwe.mitre.org/data/archive/) 与固定 [CWE 4.19](https://cwe.mitre.org/data/xml/cwec_v4.19.xml.zip)；官方 [ATLAS README](https://github.com/mitre-atlas/atlas-data/blob/main/README.md)、固定 [legacy data](https://raw.githubusercontent.com/mitre-atlas/atlas-data/3259f388d19cbcca11bacf12a0ef97f4198f711b/dist/ATLAS.yaml)。真实命令、HTTP status、hash、CAS 路径与未通过项见 reports/runs/recovery_r07_input_capabilities_20261016。

Fix1补充（主控2026-10-16明确指令）：保留7dae1d82及其历史材料。先由原validator确认原文quote合法和字段内容不伪造，再检查模型已见范围。合法但未见span使用field_evidence_outside_selection/BLOCKED；version_expression_context_missing、atlas_prerequisite_context_missing、literature_relation_context_missing仅在对应原文必要qualifier确与omitted_ranges重叠时BLOCKED。仅selection.incomplete不够：模型已经见到的必要条件、伪造ID/内容/格式仍FAILED，empty仍PENDING；混合坏输出不能全部归罪selection。公共validator不改，原full-input143期待保留。新算法此前未集成或发布，不引入数据迁移；主控runtime首次接线以最终source SHA和上述prompt/selection版本为准。

Fix2补充（主控2026-10-16T06:22:44+08:00正式CR授权）：独立评审发现原validator先抛必要context缺失，导致另一伪造boundary未被核验；该共根因不能由owned模型层复制validator解决。本版本依CR-R07_context_validation_seam.md修改唯一共享field_sources入口：先完成quote/value/boundary/target/limitations校验，再从完整原文计算typed FieldContextGap；错误默认空gap，安全code/str不变。owned模型层删除复制qualifier正则，仅当全部gap都与omitted ranges相交且selection.incomplete时BLOCKED。错误值、可见但被丢弃的必要条件、混合坏候选仍FAILED；未改变支持规则、source URI信任、公共schema、阈值或预算。源码rg与CBM确认仅model_fields._generate_field和EvidenceGraphReadService._validated_support直接调用；publication不直接调用，不存在field_candidates.py。此前关于publication重验证覆盖limitation的推断已撤回，不能记真实缺陷。

Parser边界Fix2：URI分解与端口错误归一为taxonomy_source_uri_invalid，不回显原URI；YAML使用成熟SafeLoader构造标量key后判等，拒绝语义重复key、非scalar/customtag/alias与非有限float key。解析阶段先保留TaxonomyInputError，成熟scalar构造的ValueError/KeyError等再归一为taxonomy_yaml_invalid；不吞任意业务异常。原评审URI/YAML/false-boundary/scalar探针保持输入不变，969/170真实固定版本成员性与170原文行定位重跑；官方全schema126错误、旧组织404及旧595预算红项继续保留。回滚将shared seam与owned状态判断作为同一行为单元；首次正式接线仍由root采用最终source SHA与上述冻结prompt/selection版本，旧任务不重解释。
