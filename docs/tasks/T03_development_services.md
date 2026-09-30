
# T03 · 开发依赖容器与配置分层

阶段：G1｜前置：T02｜评分/要求：E1、P1、R2

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/02_architecture.md`
- `docs/plan/09_operations_delivery.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

需要本地Docker或明确授权的等价容器环境。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`infra/compose/`；`config/`；`backend/src/ai_intel/infrastructure/`；`backend/tests/integration/`；`scripts/dev.py`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`infra/compose/compose.yaml`；`backend/src/ai_intel/infrastructure/settings.py`；`reports/tasks/T03.md`。

测试/检查位置：`backend/tests/integration/test_t03_development_services.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 创建core与search/observability可区分的Compose服务，锁定经验证的PostgreSQL、Redis、OpenSearch镜像。

2. 配置私网、持久卷、健康检查、资源限制和本地端口；不把数据库/搜索直接暴露公网。

3. 实现Settings：APP_ENV与DATA_MODE分开，秘密引用与非秘密配置分开；缺必需项给出明确错误。

4. 提供本地开发启动/关闭与依赖检查，关闭不删除数据卷；销毁数据需要显式确认。

5. 在真实容器上建立连接、写入/读取最小数据并重启确认持久性；不能只mock数据库。

6. 更新CI集成服务配置及README，记录实际内存/磁盘需求与未验证的平台。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T03-C01 | 首次启动依赖 | 健康检查可用且从应用访问成功 |
| T03-C02 | 重启容器 | 已写持久数据保留 |
| T03-C03 | 搜索profile未启动 | 可识别降级，不谎报全依赖ready |
| T03-C04 | production配fixture或默认秘密 | 配置验证拒绝 |
| T03-C05 | 无容器权限 | integration标blocked，不用SQLite冒充 |
| T03-C06 | 关闭开发服务 | 不删除卷和用户文件 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t03_development_services.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T03.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
