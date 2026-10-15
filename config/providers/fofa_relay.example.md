# FOFA relay 进程配置变量

本配置只适用于专用第三方 relay 适配器。官方直连使用独立凭据和合同；不能将 relay 密钥复用于官方或其他来源。账户验证只说明 relay 账户状态，不证明资产授权或官方 API 观察能力。

| 变量名 | 用途 |
|---|---|
| `DIANZI_FOFA_PROVIDER` | 显式选择专用 relay 身份；其他 provider 会拒绝 |
| `DIANZI_FOFA_RELAY_BASE_URL` | 服务端可信固定来源配置；仅接受已核对的精确 HTTPS origin |
| `DIANZI_FOFA_RELAY_API_KEY` | 从秘密管理器向子进程临时注入；不写入配置文件、参数、日志或前端 |

当前候选支持固定路径的单次账户只读验证，不接受任意 URL、自由查询或资产搜索。fixture 网关须同时显式开启 fixture 模式，结果携带合成标记。

缺失 key 为 `not_configured`；无效身份/来源/key 格式为 `invalid_configuration`；鉴权失败、支付要求、限流、超时、非 JSON、供应商错误分别返回固定错误代码。成功但额度未给完整数字时为 `unknown`，已知零额度为 `budget_exhausted`；不从错误文本推测余额。

本候选未接入公共 settings、运行时、PG、API 或 UI。公共配置由主控在独立评审后接入。后续资产观察须先取得授权范围、费用上限、搜索响应字段合同，并使用服务端认证上下文构建范围限制，独立保存快照和历史。
