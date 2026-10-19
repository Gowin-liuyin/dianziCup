# CR-R18 · 集成风险切片的源码保全比较基线

文档首次创建时间：2026-10-17T11:34:08.241+08:00
本次写作开始时间：2026-10-17T11:34:08.241+08:00
状态：approved_for_implementation；Root 修改的测试与集成源须新非作者审查。

Root 从已独审 8125ca3 导入风险 producer 与9直属测试，回归140项实际139pass/1fail：test_existing_production_blobs_are_unchanged 对6个生产文件统一比较旧9aa源码，Root 已先集成的 structured_fact_proofs.py 与旧9aa有已审支持闭包/内容读取变化。此失败是集成保全比较基线不符；不能回退已有修复或修改事实/权限/评分来改绿。原红/XML/导入 manifest 与8125原测试 Git 原文保留。

最小更正仅该保全测试：新导入 public_risk_summary.py 继续与9aa精确比较；其余5个既有生产文件与此次导入前 Root0291d197精确比较。PG 原 expired case 的 AST 比较仍使用9aa，issued-2/expiry-1 与原 SessionExpired/Grade/权限断言不改。新的比较仍要求源码逐字相等，不能允许任意函数变化。

无生产行为、数据库、依赖、公开合同、金标、阈值或分母变化。回滚可恢复原测试并保留其已知不匹配；新 Root 整合版本仍须相关实际 PG 与新审查，旧9aa/8125有限通过不自动签 Root。必要验收：更正后原140完整重跑、6文件保全来源核验、相关 Root 回归；未跑的真实 default route/integration/live 明确 not_run。

本次写作结束时间：2026-10-17T11:34:08.242+08:00
