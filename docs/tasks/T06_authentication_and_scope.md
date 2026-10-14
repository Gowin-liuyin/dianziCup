
# T06 · 用户认证、租户权限与审计基础

阶段：G1｜前置：T05｜评分/要求：E1、F3、X1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/05_api_and_tool_contracts.md`
- `docs/plan/09_operations_delivery.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/api/`；`backend/src/ai_intel/infrastructure/`；`backend/src/ai_intel/domain/`；`backend/tests/security/`；`scripts/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/api/authentication.py`；`backend/src/ai_intel/domain/access.py`；`reports/tasks/T06.md`。

测试/检查位置：`backend/tests/security/test_t06_authentication_and_scope.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现预创建用户、成熟Argon2密码hash、不透明随机session、注销和过期，不开放公共注册。

2. 实现CSRF、Origin/CORS和Cookie策略，production必须Secure，登录有有限速率控制。

3. 在服务端构造AccessScope与权限表，区分tenant_admin和system_admin；请求体不接受自报权限。

4. 建立范围化repository查询范式和不可见对象统一404规则，公共证据和私有资产分别处理。

5. 增加审计事件与trace_id；记录安全事件不打印密码、cookie、token和私有正文。

6. 提供管理CLI安全创建测试用户；无默认生产账号、无前端硬编码密钥。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T06-C01 | 正确账号登录/注销 | session生成后有效，注销立即失效 |
| T06-C02 | tenant B请求tenant A资产/证据 | 一律不可见，无名称泄露 |
| T06-C03 | 伪造请求体tenant_id或role | 不获得权限 |
| T06-C04 | 无CSRF/错误Origin写请求 | 拒绝 |
| T06-C05 | 过期/错误session或暴力登录 | 正确拒绝与限流，不泄露账户细节 |
| T06-C06 | 日志与前端构建扫描 | 无真实密钥、密码或会话值 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/security/test_t06_authentication_and_scope.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T06.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R01:T06、R02:T06、R20:T06。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
