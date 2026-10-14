# T00 验收检查表（实际执行记录）

执行时间：2026-09-30 18:41—18:56（本地时区）｜执行环境：Windows 11 10.0.26200，pwsh｜执行任务：T00

主检查按任务卡 §6 逐条核验实际文件、日志或人工记录；未创建空测试冒充通过。`python scripts/verify_plan.py` 为 T01 后补跑项，本次 not_run。

## 最低验收案例（任务卡 §5）

| ID | 输入/场景 | 必须检查的结果 | 实际输入与观察 | 判定 | 证据 |
|---|---|---|---|---|---|
| T00-C01 | 已存在仓库与未提交文件 | 报告准确保留其路径和状态，没有修改源码 | `D:\dianzi` 有 4 个既有文件（AGENTS.md、赛题 PDF、两份提示词/包文件），逐一记录于报告；全部未改动；`git status` 不可用因非 Git 仓库（退出码 128），如实记录而非伪造状态 | 通过 | `reports/tasks/T00.md` §现状审计；`docs/decisions/repository_mapping.md` §1 |
| T00-C02 | 空目录 | 标为 greenfield，给出默认落地目录而不伪称有代码 | 仓库无源码/依赖/测试/README，标 greenfield；落地目录按 `docs/plan/02_architecture.md` §3 映射登记（backend/frontend/config/... 计划任务），未预建空目录、未伪称有代码 | 通过 | `docs/decisions/repository_mapping.md` §3 |
| T00-C03 | 已有测试命令 | 只在允许且环境具备时试运行，记录原始退出码 | 仓库无任何测试命令与测试文件 → 无可试运行对象，记 not_run；`python scripts/verify_plan.py` 尚不存在（T01 产物），not_run | 通过（如实 not_run） | `reports/tasks/T00.md` §实际测试表 |
| T00-C04 | 没有模型或 FOFA 凭据 | 列为 blocked_live，不索取明文密钥到报告 | 环境无任何秘密类变量、仓库无 .env/密钥文件（仅查存在性）；模型/embedding/rerank/FOFA 均记 blocked_live（BLK-002）；报告无任何密钥值 | 通过 | `progress/blockers.md` BLK-002；`reports/tasks/T00.md` §资源状态 |
| T00-C05 | 旧 AGENTS 与本包冲突 | 提交具体冲突与映射，不覆盖 | 仓库 AGENTS.md 与包 AGENTS.md 逐行比对一致（仅差拼接分隔符）：无冲突，无需变更单；未覆盖任何文件 | 通过 | `reports/tasks/T00.md` §AGENTS.md 比对 |
| T00-C06 | 无容器权限或网络授权 | 标受影响任务与可以继续的本地任务 | `docker info` 退出码 1（守护进程未运行）→ 受影响：T03/T05/T16 等容器集成验证（BLK-001）；可继续：纯文档、domain 纯函数、合同/Schema 类任务。网络：git 到 GitHub 可达（ls-remote 退出码 0），web_fetch 工具层被拒（工具限制非主机网络事实）；未访问任何真实外部资产 | 通过 | `progress/blockers.md` BLK-001/005；`reports/tasks/T00.md` §实际测试表 |

## 边界与不变量自检

- 未读取、未输出任何秘密值；仅记录变量名模式的存在性检查结果（0 命中）。
- 未运行 `git reset`、`git clean`、force push、删除用户文件、部署或发布。
- 未安装依赖、未调用付费 API、未访问 FOFA 或第三方真实资产。
- 未修改任何既有文件；新增文件仅限 `progress/`、`docs/decisions/`、`reports/tasks/` 与本检查表 `reports/acceptance/`。
- 未运行的检查一律写 not_run；未把未知资源写成已有资源。

## 结论

6/6 案例有实际输入与可观察证据；T00 自检通过，状态置 awaiting_review，等待独立评审（不自置 accepted）。
