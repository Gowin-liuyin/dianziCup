# CR-R04 · 公开schema与内部合同适配

状态：accepted（用户建设决策已授权，准确落实经独立核对生效）。
首次记录时间：2026-10-14T20:52:23+08:00；最后更新时间：2026-10-14T22:31:09+08:00
提出/记录者：主控 /root。
授权依据：`prompts/12_full_delivery_parallel_push.txt` §§1、7、9；用户当前明确批准CR-R01–CR-R09。
独立审查：/root/r00_independent_review；review_ref=reports/reviews/recovery/G-A-R00-review-1-recheck.md；被审SHA=15d0272bd2a9e25d19397d8147e9c3cbe6016f9b。

## 原合同与问题

docs/plan/05_api_and_tool_contracts.md §2/§3，恢复计划§8公开对象与异步/clean/200限制冲突。

## 新合同与原因

稳定内部ID、revision/evidence/ACL合同优先。公开八对象通过适配层映射；ask以kind=completed/task判别，task不强制answer；check_stack四态，unsupported/no_match仍insufficient_evidence。同步数组最多200；大清单走专用上传，最大10MiB、10000组件、异步解析，超过上限拒绝。

这是已要求效果的最小完整路线，复用现有模块与成熟组件；不建设并行仓库或另一套业务真相。

## 影响范围

T04/T29/T30/T31/T32/T35/T40–T43/T51；R00/R05/R11/R12/R18；F2/F3/A1/E1。不改官方评分、盲测原则、金标或计分分母；费用实际记录，unknown不写0，任务调用/并发/超时仍受控。公共合同由主控集成；相关文档与任务卡以R00生效说明同步。

## 兼容性与已有数据

原未接入业务端点保留兼容别名；/api/v1统一路径。新错误RFC9457 application/problem+json，同时以error/trace_id扩展保留旧客户端识别字段。明确schema版本；前端/SDK生成物一起升级。

## 迁移与验证

冻结public_api_v2.json及正负样例：异步句柄无answer有效、clean无效、201数组无效、上传上限独立；RawEvent是原文，NormalizedIntel是归一化，插件输出受控二者关联。分页/8k token预算不拆断单事实证据关系；R18实际协议兼容测试。

尚未执行产品迁移/验证，结果须由对应任务报告和真实命令给出；本单不是能力通过证明。

## 回滚与失败恢复

保留旧API适配与版本路由，停用新版本入口，读取内部完整记录。不能回滚为clean/安全或让异步伪装回答；上传已收任务按冻结schema完成/明确失败。

## 批准记录

建设决策：用户已授权。准确落实核验：accepted（独立意见见下方生效记录）。生效依据将在独立审查报告冻结后追加，记录其被审SHA与报告路径，主控不自签。


2026-10-14T22:19:34+08:00：依据独立reviewer /root/r00_independent_review 的 [reports/reviews/recovery/G-A-R00-review-1-recheck.md](../../reports/reviews/recovery/G-A-R00-review-1-recheck.md)，冻结代码15d0272bd2a9e25d19397d8147e9c3cbe6016f9b上的准确落实核验通过并生效。主控仅登记该意见；本单产品实现结果仍按各R卡独立验收，原整T与G-A不自动通过。
