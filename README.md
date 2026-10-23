# AI 安全知识情报系统（赛题九）

监测、富化与有引用问答的默认产品装配。PostgreSQL 是事实和任务状态的权威；Redis 只传递任务和缓存；OpenSearch 是派生索引，滞后时回查数据库。原文字节在配置的内容存储里，不是另一套业务真相。

本说明只写已经对着代码核对过的事实。它不是评分，也不把历史阶段门写成当前整系统已验收。没有人工金标，就没有准确率或召回率。没有同版本的持续采集窗口，就没有「发现至采集不超过 6 小时」的结论。费用未计量时保持未知。

## 进程

| 进程 | 默认命令 | 作用 |
|---|---|---|
| API | `uvicorn ai_intel.api.app:app` | 认证和业务路由。启动不迁移、不建账号。 |
| worker | `celery -A ai_intel.workers.runtime:celery_app worker` | 只消费队列 `ai_intel`。 |
| investigation-worker | `python -m ai_intel.workers.investigation` | 只消费 `ai_intel_investigations`。Compose profile 是 `investigation`。声明不等于已经跑出轨迹。 |
| scheduler | 同一应用的 `celery beat` | 调度到期任务。进程活着不等于业务任务完成。 |
| frontend | Vite | 工作台。Compose 使用 `FRONTEND_PORT`；本机 `npm run dev` 固定 `127.0.0.1:25173`。 |

调查任务写入队列 `ai_intel_investigations`。默认 worker 不消费它。Compose 用 profile `investigation` 启动 `python -m ai_intel.workers.investigation`；这个进程本轮没有启动。

来源自动轮询默认关闭（`SOURCE_POLLING_ENABLED=false`）。模型富化默认关闭（`ENRICHMENT_GENERATION_ENABLED=false`）。配置不自动读取 `.env`。

## 启动

容器、搜索 TLS 和 profile 以 [infra/compose/README.md](infra/compose/README.md) 为准，这里不复制会过期的步骤。只开 API 不够：`/v1/health/ready` 要在数据库、Redis、已配置的搜索、worker 和 scheduler 都为 `ready` 时才返回 200，否则返回 503。Compose 的 API 健康检查打的就是这个地址，所以前端 profile 要等 worker 和 scheduler 也被观察到。搜索未按该说明初始化时，就绪保持失败，不能改成跳过。

数据库和账号在 `backend/` 下执行，`DATABASE_URL` 先放入环境，不要写进命令行：

```bash
uv run python ../scripts/migrate.py
uv run python ../scripts/admin_user.py <username> --tenant <uuid> --role analyst
```

`system_admin` 必须 `--tenant none`。密码只来自 `ADMIN_USER_PASSWORD` 或无回显提示。没有公共注册。

夹具主路径只在 `DATA_MODE=fixture` 时加载，live 会在打开数据库前拒绝：

```bash
uv run python ../scripts/load_main_path_story.py
```

它写入一条公开事件、一条可定位证据、两个版本不同的资产、一条已发布规则和两个订阅。输出只有标识，没有密码或连接串。重复执行不会再写一套。2026-10-23 在一个用完即删的临时 fixture 库里实际执行过：规则已发布，`1.4.1` 的研判是 `supported_applicability`，`1.4.2` 是 `excluded_with_evidence`，第二次执行返回 `already-present`。那不是 live 库，也不是金标。

本机前端把 `/v1` 和 `/api/v1` 代理到 `API_PROXY_TARGET`，未设置时是 `http://127.0.0.1:28002`。Compose 的 API 端口是 `API_PORT`，两者不一致时要显式设置代理目标。

## 已挂载的路由

下列路由同时挂在 `/v1` 和 `/api/v1`。认证和健康检查另外挂在根路径 `/auth` 与 `/health`。

| 前缀 | 方法与路径 |
|---|---|
| `/auth` | `POST /login`，`GET /me`，`GET /csrf`，`POST /logout` |
| `/health` | `GET /live`，`GET /ready` |
| 事件 | `GET /events`，`GET /events/{event_id}`，`GET /evidence/{evidence_id}`，`GET /events/{event_id}/graph` |
| 资料 | `GET /documents`，`GET /documents/{document_id}`，`GET /documents/{document_id}/revisions` |
| 来源 | `POST /sources/{source_kind}/collect` |
| 富化 | `POST /events/{event_id}/enrichment-jobs`，`GET /enrichment-workflows/{workflow_id}` |
| 任务 | `GET /jobs/{job_id}` |
| 问答 | `POST /questions`，`GET /answers/{answer_id}` |
| 资产 | `GET /assets`，`GET /assets/{asset_id}`，`GET /assets/{asset_id}/snapshots`，`GET /assets/{asset_id}/snapshots/{snapshot_id}`，`GET /assets/{asset_id}/snapshots/{snapshot_id}/sbom`；`POST /asset-snapshots`，`POST /asset-imports` |
| 研判 | `POST /assessments`，`GET /assessments/{assessment_id}` |
| 调查 | `POST /investigations`，`GET /investigations/{job_id}`，`GET .../tool-runs`，`POST .../cancel` |
| 推荐 | `GET /subscriptions`，`POST /subscriptions`，`GET /subscriptions/{subscription_id}`，`PATCH /subscriptions/{subscription_id}`，`POST /subscriptions/{subscription_id}/generate`，`GET /subscriptions/{subscription_id}/recommendations`，`GET /subscriptions/{subscription_id}/reports`，`POST /recommendations/{recommendation_id}/read`，`POST /reports`，`GET /reports/{report_id}`，`GET /reports/{report_id}/export` |

只挂在 `/api/v1` 的公开读取：`GET /vulns`，`GET /vulns/{event_id}`，`GET /sources`，`GET /tasks/{task_id}`，以及 `POST /ask`。

`POST /questions` 在这些情况下返回 422 `question_scope_not_supported`：事件不是恰好一个、带了资产、带了会话、带了 `known_at` 或 `valid_at`、或 `mode` 为 `investigate`。缺证据时不得用模板句充当回答。

## 工作区

导航在 [frontend/src/app/workspace-navigation.ts](frontend/src/app/workspace-navigation.ts)。运行、会话、情报、来源、资料、问答、资产、研判、调查、图谱、变化与推荐、报告会调用上面的接口，不注入演示样本。图谱没有事件标识时只提示先选择事件。

`#tasks` 按输入的任务标识读取已有收据。没有输入时是「尚未查询」，不是零条任务。租户会话看不到不属于自己的来源任务，页面会显示没有权限，而不是把拒绝写成不存在。

九个固定来源覆盖八类：`nvd_ollama` 与 `osv_ollama`（结构化漏洞）、`vllm_vendor`（厂商公告）、`avid_community`（安全社区）、`ollama_releases`（代码仓库）、`trailofbits_blog`（技术博客）、`arxiv_security`（学术论文）、`nist_ai_rmf`（技术标准）、`cac_generative_ai`（政策法规）。采集要由无租户的 `system_admin` 手动提交。后七类写入资料和证据，不据此创建漏洞事件；情报列表和资料库不是同一份结果。

## 主路径还断在哪里

后人要走完的闭环是：登录，打开带来源和原文定位的情报，看到适用富化的已发现、不适用、未知或失败，用两个资产快照得到不同四态研判，多跳问题要么有引用要么拒答，两个订阅得到不同推荐，调查在证据不足时停止并留下工具调用。当前断点：

1. 调查进程已在 Compose profile `investigation` 中声明，默认发布也指向同一队列。本轮没有启动该进程，所以还不能说调查页已经出现停止原因。
2. 默认问答仍拒绝多事件、资产、会话、时间和调查模式。页面会说明这是范围拒绝，并给出调查工作台入口。多跳仍不在 `POST /questions` 上。
3. 事件详情可以提交富化。受理只表示任务已保存；受阻和失败不能显示成已取得。模型维度和暴露面在默认配置下仍会受阻。
4. 夹具命令会发布一条版本区间规则。临时 fixture 库里，`1.4.1` 与 `1.4.2` 已经得到不同研判。换一台库后需要重新执行命令，不能把那次临时结果当成当前库已经有数据。
5. 任务轨迹页会查询已有收据。没有夹具任务标识时，页面保持尚未查询。
6. 自动轮询关闭。没有新的同版本墙钟窗口，时效保持未测。
7. 没有人工双人金标。任何页面或报告都不得在金标数为 0 时显示准确率。
8. 未提供授权资产范围时，不调用 FOFA。资产只来自操作者导入的快照或夹具命令。

这些断点留到下一阶段接，不在本说明里写成已接通。

## 检查

仓库根目录的 `python scripts/dev.py check --scope <scope>` 在对应测试目录存在时才会执行。`unit`、`contract`、`integration`、`security` 分别跑 `backend/tests/<scope>`。`frontend` 跑前端 lint、typecheck 和测试。`e2e` 跑 Playwright。退出码：`0` 实际通过，`1` 失败，`2` 参数错误，`3` 未建设或零测试，`4` 资源阻塞，`124` 超时。跳过的测试不算通过。`contract` 和 `integration` 需要隔离的测试库，不是本说明已经跑过的结果。

不要把组件测试、夹具或计划结构检查当成 live、浏览器业务或正式评测。
