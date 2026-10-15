# CR-R04 · 公开Schema格式校验环境补充

状态：awaiting_review；落实已有RFC3339/公开v2 Schema合同，未改Schema、样本、负例、评分或盲测。
首次创建/本次写作开始/结束/证据截止：2026-10-15T18:43:56+08:00
作者/root；独立核对/root/g_b_checkpoint_review待新锁定环境复跑。

独立阶段审查在冻结semantic环境执行原tests/plan得到55pass/1fail：不带时区created_at被FormatChecker接受。根因是jsonschema基础包的date-time格式检查器需要其官方可选依赖，环境未安装；不是负例错误，也不能把格式声明当已执行校验。

backend dev依赖从jsonschema>=4.23,<5改为官方jsonschema[format-nongpl]>=4.23,<5并更新uv.lock，补RFC3339、URI等既有格式的成熟校验实现；没有自写日期正则。运行时依赖/公开API没有变化，不把dev检查变成付费模型或网络调用。uv add命令退出0，但首次独立开始/结束时间未记录，不按mtime补写；之后真实frozen命令2026-10-15T18:31:40+08:00至2026-10-15T18:32:07+08:00，原56计划检查全部通过，26.05s。日志gb_schema_plan_formats.*；该合同/计划检查不计产品coverage分母，原产品60%门另行保持。

兼容/迁移：开发/CI/复现环境必须uv sync --frozen安装锁定dev依赖，production no-dev不引入测试工具。原合法带时区例不变，原非法无时区负例恢复拒绝。回滚保留该已验证锁/校验工具；若上游依赖不可用，标环境阻塞并前向修复，不删负例或关闭FormatChecker。新增的可选格式依赖是执行已有格式合同所需；未新增通用框架。
