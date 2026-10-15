# R10 · 证据支持、读返回有效性与 fixture 迁移

记录时间：2026-10-16T04:12:00+08:00。状态：`awaiting_review`；实施依据是主控本轮明确授权的修复设计和 10 个旧正例 fixture 输入迁移，独立复核尚未完成。本文件不修改 public_api_v2、公共权限/认证、数据库 schema、锁配置、原 T 验收或评分分母。

## 已复现问题与依据

冻结 `b0b7a5b856cc38862f64c01565309564d67c34c0` 的作者 PG 35 项通过，但部分正例只用 `explicit source` 作为引用。PG supported/validated 标记和引文哈希不能证明版本、ATLAS、论文、处置或事件绑定的内容支持。新独立 reviewer 的最初 20 项为 8 passed/12 failed；扩展到 32 项后为 20 passed/12 failed。原报告/脚本/日志在主控 `reports/runs/recovery_r10_pg_evidence_graph_review1_20261016/`，本作者不修改其字节或期待。

另两个 P1 是首次 RR event SELECT 后另一事务已撤销父 ACL、撤回事实/增加 epoch/事件版本，或将 analyst 降为 viewer，而路由仍交付旧快照。P2 是相同论文目标在 2000 支持行、max_nodes=1/max_edges=1 时重复做目标 ACL 查询。

## 最小行为修正

- 投影按 claim 聚合完整有效引用，验证证据坐标/哈希后复用 `validate_field_candidate`。CVE/GHSA 使用原文机制/版本/分析句中的外部 ID 或同修订精确 owner JSON 字段（`/id`、`/ghsa_id`、`/cve/id`、`/cveMetadata/cveId`）绑定，ID 比较沿用不区分大小写的已归一语义；不要求原文含系统 UUID。非 CVE 使用同主来源的已验证 affected_product/source_excerpt 与具体安全描述，缺绑定保持 unknown。
- 版本需要组件、生态、肯定 affected 范围、原边界及限定条件；修复/缓解需具体来源句；ATLAS 需当前、可见、固定 commit 的体系文档/技术 ID、事件机制和前提；论文需 URI/title/关系正文、正确目标身份、覆盖及当前父 ACL。只共享主题或缺依据不发布强边。
- 为复用模型专用校验器，只在临时校验候选里中和 comparison_support、模型不允许选择的 target IDs、static_status 等权限限制；随后核对由 PG 选定的目标身份。不写回、不提升模型候选，也不修改已有合法规则事实或静态 PoC 状态。规则事实的 supported comparison 和已记录 static_reviewed 保持原值。
- 首次 RR 仅构建候选与输入摘要；关闭它后在新 READ COMMITTED 短事务使用现有 `lock_authenticated_scope`，比较完整 scope/role/permissions。锁顺序为认证 → source → document → revision → event → claim/evidence/block/断言关联 → epoch。当前投影和有界输入摘要全部重读，再锁/比较 epoch。直接撤权不递增 epoch 时也会失效；变化返回 409，撤权返回 401/403/404。所有读取完成后在持锁事务内构建响应字节。0 重试，不在 epoch 锁内倒序获取父锁，等待继承既有配置并以 503 有界失败。
- 论文目标和文档只在一次 event_graph 调用的认证范围内缓存；下一调用重新检查当前父 ACL。没有全局权限缓存。输入支持行上限 2000、节点 200、边 400 保持；超过返回围栏容量明确 409。`content_sha256` 仍仅描述选中图，不能给截断全图/Neo4j 投影签一致；内部输入摘要只用于本次读围栏。
- 投影规则版本由 `r10-graph-1.0.0` 升到 `r10-graph-1.1.0`，公开合同未改变。

## 原 35 项迁移范围与保留

原始文件完整保存在 `reports/runs/recovery_r10_graph_validity_20261016/original_author_cases.py`。raw SHA-256=`dca8f657fc384c6af9363b020c7ce49ce9bd1d2b08f913fa73625ff2d13d3bf9`，原 Git blob=`2ccfb158d3d231af1a442cdda0e20d41023d515e`。只读原副本在新语义下实际为 24 passed/11 failed，exit 1；`original_author_red.log/xml/json` 保留。10 个失败正例缺内容支持，另 1 是旧 REST rule_version 的硬编码期待。没有把原红改绿或删样本。

| 原 case / 参数范围 | 原缺口 | 新输入；全部行为/权限/current/数量断言保留 |
|---|---|---|
| `test_six_relations_are_derived_from_published_pg_claims_and_preserve_reverse_support`（1） | 假 quote 不含六类字段和事件依据 | 合成自然 GHSA 公告、PyPI affected 边界、Fixed/Mitigation 句、体系 commit/技术 ID/机制/前提、论文标题/URI/分析原文与目标版本 |
| `test_same_names_in_distinct_ecosystems_and_ranges_remain_separate`（1） | 引用无组件、生态和范围 | 三个明确的 PyPI/npm 与 1.x/2.x 来源句；仍断言 3 身份、不合并 |
| `test_unknown_version_and_absent_action_preserve_gaps`（1） | 无来源绑定的 same_event | 真 GHSA/组件范围来源；comparison unknown 和空 action 原期待保留 |
| `test_current_version_changed_withdrawal_and_truncation_do_not_resurrect_edges`（1） | 初始 5 边无原文依据 | 合法的 affected/fix/mitigation 来源；原 5 边、截断、撤回、旧 RR 快照与新版本断言均保留 |
| `test_private_graph_and_nested_sources_do_not_cross_tenants_or_promote_scope`（1） | 私有输入无语义绑定 | 同样自然原文的私有 scope；被测试的公开关联显式带相同外部标识，仍拒绝 other/viewer、私边不提升 |
| `test_every_parent_acl_is_rechecked_and_private_support_stays_private`（5） | 来源事实本身是空泛 quote | 真实字段句；source/document/revision/evidence/claim 全 5 参数与其拒绝/私有范围断言不改 |

同一 helper 生成的其余 25 项输入得到上述自然原文以保持正负例同一基线，原 case IDs、参数和期待未删除。合成原文按固定坐标存入内容寻址对象，PG 文档/修订 hash 与实际字节一致；只是未发布 fixture 的初始化，不改变产品历史或原文保存逻辑。新增检查直接读取原文字节核验所有 quote 坐标。仍不是 live/官方版本真实性实测。

unit 的一个固定 rule_or_model_version 输入和 REST 的 rule_version 期待改为 1.1.0，分别有原 unit/PG 副本和旧红记录；这是版本变更，不改变状态门或强关系门。

## 原 reviewer 20/32 的保留与 known loss

作者复制的 32 项脚本 raw SHA-256=`cfbbb95d227f4e884d2765bde6da5dbd1121c5ffd9c159ac99a1e9eadf0bfe16`，原脚本字节不改。新语义首轮复跑 22 passed/10 failed：原 12 个 P1 反例均通过；10 个旧期待仍保留失败。

- `test_exact_fixture_fields_produce_each_supported_relation` 的 6 参数：仅将 typed JSON 和内部 UUID 拼入字符串，并未给出原文外部 ID/精确源字段、完整版本/体系/论文依据，不能作为强关系正例。
- `test_selected_graph_is_bounded_deterministic_and_canonical` 的 3 个小上限参数：仍以无支持的旧 quote 输入，期待原来虚构的 5 边导致 truncated=true；新语义无有效边，原截断期待不成立。第四个大上限 case 仍通过。
- `test_poc_reference_does_not_become_remediation_or_verification`（1）：旧无绑定 quote 不能确认 same_event；“不成为处置/验证”的安全要求继续由新增真实来源例验证。

这些 known loss 不被标记 skip、不替换原 probe 或改计分口径。新增自然原文正负例另列；独立 reviewer 决定语义修复与本次 fixture 迁移是否可接受。

## 验证与剩余范围

需在新的冻结 SHA 完整运行迁移后原 35、原 pure 10、新语义/HTTP/锁等待/性能用例、相关既有回归，并保留原 35 与 reviewer 20/32 的红项和所有分母。控制负载仅报 SELECT 次数与实际耗时，不作为 P1/P3 比赛指标。无 source/provider/model/network 调用，无资产扫描、认证共用改动、新 schema 或业务写入。Neo4j、产品注册、UI、live/manual 仍未交付，原 R10/原 T 整卡不能自动接受。
