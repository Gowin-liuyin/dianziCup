# CR-R18 · API Key 与共享认证事务接口

首次创建时间：历史未记录（文件创建后首次读取时钟）。
首次登记时间：2026-10-16T08:42:32+08:00
状态：approved_for_implementation；实现与独立审查尚未完成。
授权依据：本批用户批准 CR-R09、R18 API Key 与租户隔离建设；不是新增收费服务或扩大资产访问。

当前 cookie 路由通过 `api.auth_state.lock_authenticated_scope` 在业务事务内重新锁会话与用户。API Key 不得转换为会话 token 或临时管理员 cookie。源码和当前索引 `dianzi-root-r18-d31-20261016` 核对了 answering、assessment、inventory 与 API 调用；图中的间接关联须以源码交叉验证。基线 `d31f37ff04f845d310393fd652e4e7a2647b8755`。

## 输入、输出与权限

新增 `api.credentials` 的不可变 `SessionCredential(token: SecretStr)`、`ApiKeyCredential(token: SecretStr)` 与联合 `AuthenticatedCredential`；不允许 repr 显示凭据。`lock_authenticated_principal(connection, credential, now) -> AccessScope` 在调用者事务中验证当前状态。会话分支复用既有函数，保持 cookie、Origin 与 CSRF 行为。

Key 由标准库 `secrets` 生成至少 32 随机字节，仅签发时返回一次。数据库只存 SHA256、key_id、owner user_id、固定 resource `urn:dianzi:api:v1`、scopes、issued_at、expires_at、revoked_at、version；不得存 token、密钥提示或秘密日志。第一版允许 scopes 仅 `read:public` 与 `read:asset`，必须非空且不超出签发者当前角色权限，不赋予源管理、规则发布、用户管理或审计读取权限。派生 ask/check 的幂等任务与费用另受共享任务预算约束，不能因为只读 annotation 免于鉴权。

读取与提交均锁 key 和当前 users 行，权限是 key scopes 与当前角色的交集，保留当前 tenant；过期、撤销、错 resource、无权限、owner 不存在均拒绝。撤销与角色变更的提交顺序由真实 PG 锁保证。用户只管理本人 key，system_admin 也不得借此代取他人明文；撤销保持历史记录。默认有效期 30 天、最大 90 天是明确工程配置；调用者必须使用服务端 aware now，错误输入不得变成永久有效。

固定 Bearer 仅从 Authorization header 读取；拒绝 query 凭据、重复/畸形 header、同时 cookie 与 Bearer。请求体的 user_id、tenant、role、scopes 不参与调用者身份。HTTP MCP 必须逐请求/逐工具取得认证上下文；禁止用全局一个产品 key 为所有 HTTP 用户代取数据。

## 数据与限额

指定实现者只新增 `api/credentials.py`、`api/credential_models.py` 及自有测试；既有 auth_state/access/service/router 由主控接线。迁移编号 **0026** 由主控唯一负责。表定义不得伪称生产迁移已完成；实现者提供精确 DDL、约束和 metadata 对照，由主控加入前向链。

`api_keys` 与必要的 `api_key_rate_buckets` 为 PG 权威。限流候选单 key 60 读/分钟、10 ask/分钟，bucket 使用服务端时间和事务原子锁；只能更新本人 key 的 bucket，未授权请求不能消费其他 key 限额。两个并行派生任务的预算/预约复用 job authority，未接通时明确未实现，不另建内存计数冒充分布式限制。Redis 只可加速，失效不能绕过 PG。

## 兼容性、迁移和回滚

原 `/v1` cookie 合同、会话哈希与原表不变。旧 shared service 的 `session_token` 接口不能偷偷解释为 key；主控显式增加 credential 输入并保留旧调用兼容，再跑全部最终事务/撤销/租户路径。公开 `/api/v1` 与 MCP 新入口接入本 seam，没接通时返回明确 not_configured/拒绝，不能创建假成功。

只执行新增表的前向迁移。回滚先关闭公开 key/MCP 新入口，保留 key 撤销历史、任务和审计，不降级/drop 数据。安装 SDK 不接触数据库凭据，产品 API Key 不等于编程 Agent 账号。

## 任务和验证影响

R02/R12/R14/R18/R20、T06/T32/T35/T45/T51；原最终范围与评分/金标/盲测不变。必须单元/合同覆盖严格解析、scope/expiry/resource/秘密 repr；真实隔离 PG 覆盖两租户、角色降级、撤销提交竞态、两进程限流、失败回滚/幂等与重启；安全覆盖 cookie 混淆、日志/错误回显和请求体伪造。API、MCP、真实客户端和 live 为主控接线后的独立验收，不能由纯模块测试替代。

实现者只进入 awaiting_review；全新非作者审查此切片及其 PG 行为后主控才登记有限结论。此记录本身不是任务或阶段通过。
