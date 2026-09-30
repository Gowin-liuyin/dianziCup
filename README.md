# AI 安全知识情报系统（赛题九）

面向 AI 安全知识情报的监测、富化与问答系统，当前处于**开发骨架阶段**。

## 当前状态（诚实声明）

- 现有内容仅为项目骨架：后端最小 FastAPI 入口（`/health/live`、`/health/ready`）、前端空工作台外壳、依赖锁定（`backend/uv.lock`、`frontend/package-lock.json`）与质量命令体系。
- **后端业务 API 未接入**：无监测、富化、问答、Agent 任何业务路由；`/health/ready` 在外部依赖（数据库/缓存/搜索）未接入前如实返回 503 `not_ready`，不谎报 ready。
- **无任何业务能力与指标**：本仓库不提供也不声称任何准确率、时延、覆盖率或得分数字。
- CI 工作流 `.github/workflows/ci.yml` 已配置但**尚未实际运行**（not_run）。

## 环境要求

| 组件 | 版本 | 依据 |
|---|---|---|
| Python | 3.12（`requires-python = ">=3.12,<3.13"`） | `backend/pyproject.toml` |
| uv | 按锁安装（`uv sync --locked`） | `backend/uv.lock` |
| Node | 24 | 实测 v24.13.1（`reports/runs/t02_frontend_checks.log`） |
| npm | 随 Node | 实测 11.8.0（同上日志） |

## 已可运行命令

### 后端（工作目录 `backend/`）

| 命令 | 作用 |
|---|---|
| `uv sync --locked` | 按 `uv.lock` 干净安装依赖 |
| `uv run pytest tests/unit` | 单元测试（含覆盖率门槛 60%，实测 9 passed / 覆盖率 100%） |
| `uv run ruff check .` | Lint |
| `uv run ruff format --check .` | 格式检查 |
| `uv run mypy src` | 静态类型检查 |

### 前端（工作目录 `frontend/`）

| 命令 | 作用 |
|---|---|
| `npm install` | 安装依赖并生成 `package-lock.json` |
| `npm run lint` | ESLint 检查 |
| `npm run typecheck` | TypeScript strict 类型检查（`tsc --noEmit`） |
| `npm run test` | Vitest 单元测试（实测 1 test） |
| `npm run build` | `tsc -b && vite build` 构建 |

### 项目检查入口（工作目录仓库根）

| 命令 | 作用 |
|---|---|
| `python scripts/dev.py check --scope unit` | 执行后端单元测试（实测 9 passed，退出码 0） |

`scripts/dev.py` 退出码合同：`0` 检查已执行且通过；`1` 已执行但未通过；`2` 参数错误（未知 scope）；`3` 该 scope 尚未建设（输出 `not_implemented`，绝不打印 PASS）。

## 待后续任务实现的命令（当前 not_implemented）

以下命令入口已声明但对应检查尚未建设，执行会以退出码 `3` 返回 `not_implemented`，**不代表通过**：

| 命令 | 状态 | 归属 |
|---|---|---|
| `python scripts/dev.py check --scope contract` | not_implemented | 合同测试（后续任务） |
| `python scripts/dev.py check --scope integration` | not_implemented | 集成测试（需 Docker/本地集成环境，BLK-001） |
| `python scripts/dev.py check --scope security` | not_implemented | 安全检查（后续任务） |
| `python scripts/dev.py check --scope frontend` | not_implemented | 前端检查统合入口（当前请直接用 `npm run …`） |
| `python scripts/dev.py check --scope e2e` | not_implemented | 端到端测试（后续任务） |
| `python scripts/dev.py check --scope all` | not_implemented | 全量检查统合入口 |

此外以下能力整体 not_implemented：容器化与容器集成测试、真实 API/live 验证、性能与指标测量、业务功能。

## 目录速览

- `backend/` —— FastAPI 后端（`src/ai_intel/`、`tests/unit/`、`pyproject.toml`、`uv.lock`）
- `frontend/` —— React + Vite 工作台外壳（`package.json`、`package-lock.json`）
- `scripts/dev.py` —— 质量检查入口
- `.github/workflows/ci.yml` —— CI（仅编排上述已可运行检查）
- `docs/`、`contracts/`、`reports/`、`progress/` —— 计划、合同、报告与进度
