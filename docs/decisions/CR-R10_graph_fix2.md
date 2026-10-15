# R10 · 关系极性和原可见候选锁集合

状态：`awaiting_review`。实施依据为主控 2026-10-16 本轮唯一修复作者指令及共享调用方/读围栏计划认可；独立复核未完成。修复基线为 `29e1ebddca5cbadffc8c6533bdeeb08b8d63e469`，此前代码冻结 `3516b9109b9b7f2c5691d78ad0439aea4a659f4f`。本次工作树 `D:/wt/r10-graph-fix2`，分支 `codex/r10-graph-fix2`；不修改旧审查工作树或主 checkout。

## 实际问题与原材料

独立定向 probe 原文件 `test_review2_pg.py` raw SHA-256 为 `1b12f82583d8c067cc52d604c54aa53bddeb593c1cf8c2bfcccdc32d6d810c47`。原 9 项在本工作树未改源码时实际为 5 passed/4 failed：论文 `does not analyze` / `analysis ... unconfirmed; mechanism unknown` 仍产生 related_paper，ATLAS `do not enter` 仍产生 mapped_atlas，另租户未关联 claim 仅 subject=公共事件就被围栏取锁并阻塞 5 秒、返回 503。根因是共享 validator 只看 analysis 标记或精确引用存在，以及锁候选以所有 subject claims/整个修订 evidence 替代有效可见读输入。

原 probe、旧作者 35 和前次审查材料的 case IDs、期待和分母保留。旧 32 的脚本 SHA=`cfbbb95d227f4e884d2765bde6da5dbd1121c5ffd9c159ac99a1e9eadf0bfe16`；20 是该 32 的明确子集；审查的 33 实际命令是该 32 加独立 `test_graph_load_pg.py` 的 1 项，不是另一份改成 33 case 的脚本。各副本原字节及执行入口/fixture 版本在新 run 的 preservation 清单登记，不改 canonical 原文件。

## 变更边界与规则版本

投影算法显式从 `r10-graph-1.1.0` 升到 `r10-graph-1.2.0`。内部 schema_version=1、GraphSnapshot/GraphEdge 字段、状态和 gap 的 `no_current_supported_relation` / `truncated` 两种理由保持。原 unit 的规则版本输入及原 PG REST 版本断言仅升级字符串；无其他旧 fixture 迁移。此前 raw/blob/红记录保留，正式前端 rule union 同步由主控完成。

修改范围是 graph 两文件、共享 `enrichment/field_sources.py` 的关系支持校验、专属 R10 tests/本 CR/报告/run。公共 schema、auth、model_fields、预算、持久化、业务状态、迁移、锁配置、app/UI/Neo4j/progress 不改。

修改前实际 CBM 自有 `r10_graph_fix2_backend` fast index、architecture、qualified trace 与 rg 确认 `validate_field_candidate` 直接调用方仅 `model_fields._generate_field` 和 `EvidenceGraphReadService._validated_support`，上层为 `generate_model_field_attempts` 和 `event_graph`。共享函数的原 R07 model_fields/root_causes/security/contract 122 项必须回归；这些调用仍按原四维预算运行，合法候选仍是 pending/MODEL_HYPOTHESIS，图仍只读 PG supported/current/source_verified 门。没有将模型候选或反例主动改成支持/撤回事实。

## 最小修复行为

- ATLAS 对机制原句、论文对 relation 对应的完整引用句检查否定、不确定和冲突，不以标题相似度或裸关键词证明关系。论文 analysis/defense/experimental 对应谓词被否定或未确认时保持 gap；ATLAS 攻击路径被否定或未确认时不映射。
- 判断限定在关系断言及连接的限定句。`not sanitized`、`fails to filter` 是缺安全控制，不是攻击路径不存在；`not only` / `不仅` 的肯定并列、与分析无关的“不执行 PoC/不扫描”安全说明、中文“不受信任/不同角色”和时间 May 均有正例。不是对全文出现 not/不 一律拒绝。
- 原文关系的 inline/换行条件不可从 typed 值丢弃。共享完整段落限定逻辑保持版本字段原范围；关系字段从实际引用位置和条件句核对，不把前一版本字段的 inline qualifier 当作 ATLAS 机制限定。英/中文换行限定有完整与丢弃对照。覆盖不完整的论文分析继续用既有 fulltext 门拒绝。
- 文本规则是固定、可测试的保守断言检查，不是通用语言理解、任意 NLP/模型调用或准确率承诺。陌生语法和缺足够明确支持仍需独立评审；保留来源原文和 PG claim 状态，不以规则修改事实。
- 首次 RR 记录本次可见读取实际涉及的 source/document/revision/claim/validated evidence/block/assertion/支持关联 identity，作为请求内临时 `GraphReadInputs`。新 RC 重新锁认证并比较完整 scope，再按 source → document → revision → event → claim/evidence/block/关联 → epoch 取锁。仅 subject 相同、不可见或未关联的 claim/evidence 及父链不入锁集合，不让私有无关 writer 影响公共图等待或可见数量。
- 临时 identity 只用于锁原读输入；锁后仍执行完整当前 `event_graph` 查询、输入 hash、event business_version 和 scope epoch 比较，不按旧 ID 限制 fresh 查询。首次集合不存在的新可见 claim/evidence/关联，在真实提交窗口及不 bump epoch 对照中必须返回 409；直接父 ACL/claim 撤回、角色降权、writer→epoch 并发和继承锁超时仍回归。0 无限重试、0 权限缓存，序列化仍在锁内。
- 每次事件读取论文目标 memo 仍只属于本次已认证 scope；原 2000 支持行下 7 SELECT、1 目标 ACL 的测试保持。输入/输出容量、截断选集摘要、Neo4j 未接/无 consumer 的事实不变。

## 复跑与交接

最终冻结 SHA、+08 时间、argv、exitcounts、原字节和规范 Git blob 见 `reports/tasks/R10-pg-evidence-graph.md` 的 fix2 记录及 `reports/runs/recovery_r10_graph_fix2_20261016/`。所有开发红输出保留，包括首次共享限定范围过宽的 11/122 红、新测试 fixture 构造缺 kind/规范 JSON 默认字段/证据 helper 形状问题；不删旧难例或以 skip 改分母。只有冻结后实际执行的组记 passed。

本切片交付只能 awaiting_review，待原独立 reviewer 定向复核。产品注册、正式公共图合同、前端 rule union、Neo4j 和 live/manual 由后续授权任务处理；没有自行 Ship/accepted/push。
