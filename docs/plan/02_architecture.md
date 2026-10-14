
# 02 · 架构、目录和技术分界

> R00恢复合同补充（2026-10-14T21:05:58+08:00）：用户已批准CR-R01–CR-R09建设决策与完整有界批次；准确落实awaiting_review。独立核对生效后以[变更记录](../decisions/CR-R07.md)和manifest.recovery执行。原T卡最终范围/原前置/六项验收完整保留；执行依赖按能力切片。新review/push规则见用户执行提示词，未完成live/人工不算通过。


本文是空仓库默认设计，不是对用户现有环境的事实判断。T00先调查已有仓库；已有实现冲突时提出映射或变更，不自动重写。逻辑上沿用此前方案的FastAPI、PostgreSQL、OpenSearch、Celery/Redis、LangGraph、React/TypeScript；将目录收敛为模块化单体，避免弱能力Agent处理不必要的微服务集成。

## 1. 固定职责

| 组件 | 本项目职责 | 不负责什么 |
|---|---|---|
| FastAPI | 认证、请求校验、HTTP接口、任务查询 | 不在请求线程执行长时间全网调查 |
| PostgreSQL | 原文元数据、事实、资产、结论、任务、依赖、outbox | 不用搜索索引替代它 |
| 内容存储 | 按哈希保存原始字节与不可变解析产物 | 不接收用户任意路径 |
| OpenSearch | BM25候选检索与受限过滤 | 不存第二套语义向量、不决定事实有效性 |
| pgvector | 真实embedding向量、模型空间与版本隔离 | 不替代PG事实/ACL |
| Neo4j | PG已核验关系的可重建图投影 | 不另建事实真相 |
| MinIO | 内容寻址原文字节和报告对象 | 不接受用户任意路径 |
| Langfuse | 脱敏模型/工具追踪投影 | 不代替PG任务状态 |
| Celery + Redis | 定时采集、队列、任务执行与受控重试 | 不代替业务状态机或幂等 |
| LangGraph | 一次调查内的角色协作、状态和检查点 | 不重复实现队列、不授予工具权限 |
| React + TypeScript | 业务工作台和证据展示 | 不持有模型/FOFA密钥、不生成业务真值 |
| Prometheus/Grafana/告警通道 | 运行指标、可视化与告警 | 不伪造已观测到的运行时间 |

FastAPI的同步路由、SQLAlchemy会话边界、Celery幂等、LangGraph持久化和OpenSearch混合检索参考各自官方资料，见参考索引[S01—S06]。这些框架能力不是团队原创。

## 2. 版本与IO约定

空仓库建议Python 3.12、Node.js 24 LTS、TypeScript strict；实际补丁版本在T00/T02验证并锁定，不写 `latest` 镜像、不混用不同机器生成的锁文件。Node状态核查依据官方发布页[S07]。现有仓库已有兼容且受维护版本时先沿用。

Python采用 `uv` 管理环境与锁文件；前端用npm并提交 `package-lock.json`。CI使用锁定安装：`uv sync --locked`、`npm ci`；初次无锁文件时由T02正常生成，不手写伪锁文件。[S08]

首版统一同步IO：FastAPI业务路由用 `def`，SQLAlchemy Session与psycopg同步驱动，HTTPX同步客户端，Celery工作进程内同步执行图。每个请求/任务独立会话，不跨线程或进程共享Session，不在模块import时建立网络连接。异步优化必须先有性能证据和ADR，不能一半async一半阻塞。

模型提供者未确定：定义结构化生成、embedding、reranker三个独立接口；真实实现必须依据用户授权提供者的文档。离线fixture实现只用于测试。不要默认要求某家付费账号。

## 3. 目标仓库

```text
AGENTS.md
README.md
backend/
  pyproject.toml
  uv.lock
  alembic.ini
  migrations/
  src/ai_intel/
    api/                 # 路由、认证依赖、错误序列化
    domain/              # 枚举、数据合同、纯业务类型
    ingestion/           # 来源、游标、连接器、解析
    knowledge/           # 实体、事实、证据、版本
    enrichment/          # 抽取与多维关联
    assets/              # 清单、外部观察、适配器
    assessment/          # 版本、条件、证据包
    retrieval/           # 索引、检索、重排
    investigation/       # Agent、工具和预算
    revalidation/        # 依赖、关注范围、更新
    answering/           # 会话、答案与校验
    recommendations/     # 订阅与推荐
    infrastructure/      # DB、网络、存储、时钟、模型客户端
    workers/             # Celery入口与任务适配
  tests/{unit,contract,integration,security}/
frontend/
  src/{app,features,components,api}/
  tests/
  e2e/
config/{sources,models,rules,products}/
fixtures/{synthetic,recorded}/
benchmarks/{dev,manifests}/
experiments/{configs,runs}/
infra/{compose,monitoring,backup}/
scripts/
docs/{plan,tasks,references,decisions,runbooks,report}/
progress/
reports/{tasks,reviews,acceptance}/
```

上面的树为职责说明，不要求一次建立所有空目录，也不要求在源码里写这些行尾说明。按当前任务创建实际需要的文件。

一个模块通常从 `schemas.py / service.py / repository.py / router.py`中实际需要的文件开始。没有数据库访问不建repository；一个函数解决的事不建Service类。跨模块只调用公开服务或合同，不直接改别的模块的数据库表。

## 4. 依赖方向

`api/workers → application services → domain + narrow infrastructure ports`。

domain不能import FastAPI、Celery、LangGraph或数据库会话。版本比较与条件判断是纯函数；它们只接收已校验输入，不在判断过程中联网。

数据库模型留在对应repository或集中persistence包，接口DTO不得直接泄露ORM对象。明确写出的SQLAlchemy查询优于动态拼接通用CRUD框架。

## 5. 一条完整业务链

定时发现 → 安全抓取 → 原始内容留存 → 标准化/证据定位 → 相关性与事件归并 → 富化与事实校验 → 条件/资产研判 → 索引 → 问答/推荐。

每个跨任务步骤写入事务outbox。worker拿到ID后到数据库读取当前状态，不把完整私有文档和密钥放进队列。消息重复投递由任务幂等键和唯一约束处理。

LangGraph只用于需要选择调查路线的任务；来源轮询、版本比较和重试不必调用LLM。CR-R01九职责可使用同一基础模型，确定性节点不调用LLM；各角色职责/工具/输出不同。固定四角色仍为B2对照。

## 6. 状态与失败分工

PostgreSQL保存 `JobRun` 与业务任务状态。Celery状态只用于队列观测。LangGraph保存调查检查点，不以聊天历史覆盖事实库。

重试由唯一层管理：HTTP层单次有限请求；可重试的外部错误交给任务执行层按预算重新调度；图节点不再无限重试同一个请求。429读取合法Retry-After，401/403归权限配置错误，不反复攻击账号。

任务允许部分成功。例如论文关联成功、FOFA无权限：保留成功信息，资产维度标blocked，不把整条任务写complete。正文解析失败：留原文，进入待处理，不推进“已可问答”。

## 7. 环境与功能模式

`APP_ENV=development/test/staging/production` 控制部署；`DATA_MODE=fixture/live` 控制数据来源，两者不可混淆。production拒绝fixture模型和fixture来源。demo只能显式展示数据模式与快照时间。

开发API默认仅监听本地或私有Docker网络。数据库、Redis、OpenSearch不直接公开。生产认证、TLS、备份、秘密配置缺项则启动或发布检查失败，不能靠默认账号上线。

## 8. 初始内部预算

初始工具预算建议：任务外部查询最多8次、模型调用最多6次、图循环最多8轮；配置项而非硬编码。具体任务可以申请更高但必须记录。时间和费用预算由T00/T18依据实际提供者配置，未知费用上限不允许批量付费运行。

向量维度由已选择embedding模型的能力探测得出并写入索引版本。模型变化需要新索引和离线重建，不混合不同维度或模型空间。

## 9. 不增加的基础设施

不增加Kafka、Kubernetes、Agent自动安装平台、全能插件商店或自研认证协议。CR-R02明确批准pgvector/Neo4j/MinIO/脱敏追踪，依赖版本与容量在R01真实核实后锁定。不训练基础模型、不重做所有第三方产品能力。新增基础设施必须有明确瓶颈与维护成本说明。
