# CR-004 · T06 认证依赖引入（argon2-cffi）

日期：2026-09-30（Goal 第 78 轮）｜性质：新增运行依赖 + 认证实现记录（AGENTS.md §2.5 认证变动走变更单）｜提出：T06 任务卡步骤 1（成熟 Argon2 密码哈希）。

## 变更

| 项 | 内容 |
|---|---|
| 依赖 | `argon2-cffi >=23.1,<26.0`（成熟 Argon2id 密码哈希库，官方推荐参数可配置） |
| 认证设计 | 预创建用户（无公共注册）；密码仅存 Argon2id 哈希；会话为不透明随机 token（secrets.token_urlsafe(32)），服务端存储+过期+注销立即失效；登录限流；CSRF+Origin 校验；production 强制 Secure Cookie；审计事件带 trace_id 且脱敏 |
| 身份来源 | AccessScope 仅由服务端从会话构造；请求体自报 tenant_id/role 一律不采信（T06-C03） |

## 不变项

- 无默认生产账号；无前端硬编码密钥；日志不打印密码/cookie/token/私有正文（T06-C06 实测扫描）。
- 租户隔离优先于功能：不可见对象统一 404，无名称泄露（T06-C02）。

## 验证

由 backend/tests/security/test_t06_authentication_and_scope.py（T06-C01—C06）覆盖，详见 reports/tasks/T06.md（实施后补）。