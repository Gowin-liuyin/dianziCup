# CR-R09 · 共享认证、MCP与插件边界

状态：accepted（用户建设决策已授权，准确落实经独立核对生效）。
首次记录时间：2026-10-14T20:52:23+08:00；最后更新时间：2026-10-14T22:31:09+08:00
提出/记录者：主控 /root。
授权依据：`prompts/12_full_delivery_parallel_push.txt` §§1、7、9；用户当前明确批准CR-R01–CR-R09。
独立审查：/root/r00_independent_review；review_ref=reports/reviews/recovery/G-A-R00-review-1-recheck.md；被审SHA=15d0272bd2a9e25d19397d8147e9c3cbe6016f9b。

## 原合同与问题

docs/plan/05_api_and_tool_contracts.md仅预置团队cookie，恢复计划§8新增API Key/OAuth/插件。

## 新合同与原因

cookie会话与MCP/API Key共享PG用户/租户/权限；Key随机≥32字节，仅存hash、可轮换/撤销/限流。MCP stdio stdout只协议、Streamable HTTP必须认证；OAuth仅在选定客户端要求时按官方协议实施并实测。六只读工具与可配置本人订阅第七工具。

这是已要求效果的最小完整路线，复用现有模块与成熟组件；不建设并行仓库或另一套业务真相。

## 影响范围

T06/T32/T35/T45/T51；R02/R14/R18/R20；A1/E1/X1。不改官方评分、盲测原则、金标或计分分母；费用实际记录，unknown不写0，任务调用/并发/超时仍受控。公共合同由主控集成；相关文档与任务卡以R00生效说明同步。

## 兼容性与已有数据

不开放注册，不降低浏览器CSRF/Origin；Key不替代cookie的写权限检查。SourceConnector/Enricher/Tool三扩展受限上下文、无默认网络/文件/秘密权限；不直连主库，不安装任意依赖。

## 迁移与验证

版本化manifest/SDK/协议输入输出；非root只读容器、受限syscall/出口网关隔离，subprocess不算完整沙箱。实际Codex/Claude Code调用分项实测，未实测客户端不声称兼容；R18/R20权限/撤销/stdio污染/恶意插件/秘密边界测试；Apache-2.0候选先核查第三方许可。

尚未执行产品迁移/验证，结果须由对应任务报告和真实命令给出；本单不是能力通过证明。

## 回滚与失败恢复

撤销相关Key/禁用插件/停止远程MCP，保留合规审计；恢复批准manifest版本。不得关闭隔离来让插件通过。只制作安装/发布候选，不公开部署/发包/代提交；本次只授权既有origin工作分支push。

## 批准记录

建设决策：用户已授权。准确落实核验：accepted（独立意见见下方生效记录）。生效依据将在独立审查报告冻结后追加，记录其被审SHA与报告路径，主控不自签。


2026-10-14T22:19:34+08:00：依据独立reviewer /root/r00_independent_review 的 [reports/reviews/recovery/G-A-R00-review-1-recheck.md](../../reports/reviews/recovery/G-A-R00-review-1-recheck.md)，冻结代码15d0272bd2a9e25d19397d8147e9c3cbe6016f9b上的准确落实核验通过并生效。主控仅登记该意见；本单产品实现结果仍按各R卡独立验收，原整T与G-A不自动通过。
