# R01 · 独立TLS审查的CI环境装配修复

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T12:34:55+08:00，作者root，awaiting_review/partial。

新独立reviewer固定f2实测TLS7项/native密码/端口/缺密码/真实session失败隐私均通过，但发现CI调用prepare之后未获得fault-test必需的DIANZI_DOCKER_COMMAND_JSON；prepare可默认docker运行，test直接读env触发KeyError，原Must2不能视作关闭。最小修复复用prepare里已校验docker_command()的实际prefix，作为非秘密JSON随其余12个环境值统一写private connection和GitHub ENV。无需新增依赖或第二套prefix规则，不改测试断言；自有真实create/fault/cleanup由独立reviewer用新候选复核，云GitHubCI保持not_run。

同批f2 pureunit248/59.98%不足60而插件舍入返回0的问题仍准确保留；当前root真正dev.py unit入口268passed/61.42%、exit0有原始实际结果，不能以旧版本255含T09冒充其pureunit。工具raw覆盖率严格门计划在R20检查，门槛不降。
