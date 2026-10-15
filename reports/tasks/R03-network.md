# R03 · 真实网络网关与独立初审修复

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T12:26:03+08:00；作者root集成原网络实现71e27，状态awaiting_review/partial。

复用标准库HTTP/TLS/socket和成熟dnspython，不增加备用HTTP栈。原f0独立审查251自动通过仍实际复现5项安全/正确性缺口，见reports/reviews/recovery/G-A-R03-network-review-1.md；root按该可复现输入修复，具体旧行为/根因/新行为已写CR-R04-R03。原报告及negative_probes保留。完整链路为固定sourcepolicy→网关→核验DNS全集→固定numericIP连接→peer+CA+SNI/Host→响应关闭与有界读取；API/worker来源handler当前尚未装配，不能声称全系统外联已切换。

327passed/0failure/skip，cov66原60门、Ruff0、mypy64files0，命令/时刻/exit在reports/runs/recovery_r03_network_root_fixes_20261015逐条receipt。最初ruff --fix前长行是格式自检，格式化后收据0。修复后真实NVD显式DoH一次GET200/3106bytes/3.609s，证据体及hash已保存；非持续监测、DB闭环、模型或官方性能。系统DNS保留拒绝保留地址，不自动fallback。

原接口保持fetch兼容，新增可选父deadline；只支持固定来源GET，R05的受控模型POST还需后续明确合同，不走绕过网关的客户端。无fixture/live混用、无秘密用户数据或holdout。新的独立定向复核待排，不能整R03/G-A过门。
