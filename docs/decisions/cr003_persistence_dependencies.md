# CR-003 · T05 持久化依赖引入（SQLAlchemy / Alembic / psycopg）

日期：2026-09-30（Goal 第 77 轮）｜性质：新增运行依赖记录（AGENTS.md §2.5 口径）｜提出：T05 任务卡要求（数据库迁移、原文存储、不可变版本）。

## 变更

| 依赖 | 版本范围 | 用途 |
|---|---|---|
| sqlalchemy | >=2.0.36,<3.0 | ORM/核心：Session/事务边界、表映射（PostgreSQL 为事实权威，02_architecture §1） |
| alembic | >=1.14,<2.0 | 数据库迁移（T05 步骤 1/6：空库升级、已有数据升级、回滚失败处理） |
| psycopg[binary] | >=3.2,<4.0 | PostgreSQL 同步驱动（02_architecture §2 同步 IO 合同） |

均为运行依赖主版本锁界（<下一主版本），由 uv 真实锁定（uv.lock 随后刷新）；前端无变化。

## 理由

T05 必须实现真实迁移与持久化（验收 C01—C06 需真实 PostgreSQL 读写与重启持久化验证），SQLite/内存替身被任务卡明确禁止。三者为 Python 生态标准组件（02_architecture §9 不新增基础设施，ORM/迁移属常规依赖）。

## 影响

- backend/uv.lock 刷新（工具生成）；不改冻结 contracts/fixtures；verify_plan 双模式持续 PLAN_OK 为证。
- 生产配置校验（T03-C04）不变；连接串经 Settings 环境注入，不在库内含真实秘密。

## 验证

由 T05 主检查（tests/integration/test_t05_persistence_and_raw_store.py）与全套回归覆盖；详见 reports/tasks/T05.md（实施后补）。
