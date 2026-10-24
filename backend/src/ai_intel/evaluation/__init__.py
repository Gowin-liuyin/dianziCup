"""T47/R21 评测骨架: 统一记录、基线注册、指标三元组与 fixture-scale 强制收据。

本包是批次21 C5.4 的骨架层: 只做配置/记录/注册/指标/落盘/复跑比较,
不改 retrieval/investigation/revalidation 生产语义, 不产出正式指标。
B2/B2b/B3 的 stub runner 通过既有 build_investigation_graph 驱动记录结构;
B1/B4_ref 以 not_implemented/not_reproduced 如实登记; 一切输出显式标注 fixture-scale。
"""
