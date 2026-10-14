# CR-R07 · 切片依赖、并行审查与阶段交付

状态：awaiting_review（用户建设决策已授权，待独立核对准确落实后生效）。
首次记录/更新时间：2026-10-14T20:52:23+08:00
提出/记录者：主控 /root。
授权依据：`prompts/12_full_delivery_parallel_push.txt` §§1、7、9；用户当前明确批准CR-R01–CR-R09。
独立审查：尚未发生；review_ref=null。

## 原合同与问题

docs/plan/00_execution_map.md 原G0–G6全卡顺序，恢复11/12默认串行与R19起点不一致。

## 新合同与原因

R00–R24为原T00–T59的恢复切片，原最终验收完整保留。执行依据recovery.requires_slices，不机械要求含后段的整个T卡先accepted；T最终验收须全部映射切片、原前置和原C01–C06共同完成并独立review。七阶段G-A–G-G，R24-A→R23→R24-B。

这是已要求效果的最小完整路线，复用现有模块与成熟组件；不建设并行仓库或另一套业务真相。

## 影响范围

全部T/R；E1/D1/D2/X1/R2。不改官方评分、盲测原则、金标或计分分母；费用实际记录，unknown不写0，任务调用/并发/超时仍受控。公共合同由主控集成；相关文档与任务卡以R00生效说明同步。

## 兼容性与已有数据

原manifest任务/阶段/依赖/order和历史不删除；增量recovery DAG与合并验收规则。state单一真相增加recovery_tasks、8层verification及切片review；旧原文含重复键以.json.txt存档，不继续解析成当前合同。

## 迁移与验证

新批次新非作者review冻结SHA/worktree；阶段另新reviewer，主控据证据登记accepted。R19工具/候选在R04真实链通过后，正式冻结依赖完整覆盖+双人核验；R20基础从R01、R22观测首真实链、R24骨架R00。每阶段显式add/安全扫描/授权origin分支push/远端SHA核对。旧评分阈值、不变量、case IDs不改；新baseline仅刷新批准合同hash并保留旧baseline。

尚未执行产品迁移/验证，结果须由对应任务报告和真实命令给出；本单不是能力通过证明。

## 回滚与失败恢复

DAG配置出错停止受影响调度，保留全部完成代码/证据并前向修正映射；旧accepted只在history留存不恢复伪通过。远端不匹配停止push而继续本地；禁止force/main push/自动合并。

## 批准记录

建设决策：用户已授权。准确落实核验：awaiting_review。生效依据将在独立审查报告冻结后追加，记录其被审SHA与报告路径，主控不自签。
