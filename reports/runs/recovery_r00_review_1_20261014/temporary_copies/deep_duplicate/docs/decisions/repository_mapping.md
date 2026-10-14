# 仓库与开发包路径映射（T00 产出）

状态：awaiting_review｜建立时间：2026-09-30｜建立任务：T00（docs/tasks/T00_repository_audit.md，内嵌于开发包）

## 1. 已核实的路径事实

| 项 | 实际路径/状态 | 核实方式 |
|---|---|---|
| 会话工作目录 | `D:\dianzi` | `Get-Location` |
| 代码仓库（本地） | `D:\dianzi`，用户确认“使用这个仓库” | 用户指令 |
| 代码仓库（远程） | `https://github.com/Gowin-liuyin/dianziCup`（用户提供的 settings 链接对应仓库） | `git ls-remote` 退出码 0、ref_count=0，即远程仓库存在但当前无任何提交（空仓库） |
| 本地 Git 状态 | `D:\dianzi` 不是 Git 仓库（`git rev-parse` 退出码 128），无分支、无未提交修改可查 | 命令实测 |
| 开发包形态 | 单文件拼接包：`D:\dianzi\赛题九_Agent工程开发计划与执行提示词_完整版.md`（390144 字节，99 个 `# 文件：` 分节） | 文件清单与分节扫描 |
| 开发包 AGENTS.md | 拼接包内 `AGENTS.md` 分节，与独立文件 `D:\dianzi\AGENTS.md` 内容一致（非空行逐行比对，仅差拼接分隔符），无冲突、未覆盖 | 比对脚本，退出码 0 |
| 首次执行提示词 | `D:\dianzi\赛题九_编码Agent首次执行提示词.txt` | 文件清单 |
| 官方赛题 PDF | `D:\dianzi\9 赛题九：网信产业应用赛道-智能体驱动的AI安全知识情报系统设计与实现（奇安信科技集团股份有限公司）.pdf`（260044 字节），用户已提供 | 文件清单 |

## 2. 路径映射决定

1. 仓库根目录为 `D:\dianzi`。本轮新建文件全部落在该根目录下，与包内目录合同一致：
   - `reports/tasks/T00.md`、`reports/acceptance/t00_checklist.md`
   - `progress/context_handoff.md`、`progress/blockers.md`、`progress/task_state.json`
   - `docs/decisions/repository_mapping.md`（本文件）
2. 既有 4 个文件（AGENTS.md、官方赛题 PDF、两个提示词/包文件）不移动、不改名、不覆盖、不删除。
3. 开发包目前是单一拼接 Markdown，其内部路径（`docs/plan/*`、`docs/tasks/*`、`prompts/*`、`templates/*`、`docs/runtime_prompts/*`、`docs/references/verified_sources.md`、`PACKAGE_VALIDATION.md`）尚不存在为独立文件。是否将其物化为仓库文件、何时物化，属 T00 修改边界之外，登记为待人工确认事项 DEC-002，不在本轮执行。
4. 包内引用 `docs/references/competition_brief.pdf`（4 页官方赛题）。实际文件在仓库根目录且文件名不同，映射关系：包内引用路径 ← 根目录同名中文长文件名 PDF。物化时按包内路径归位或建立引用说明，不重复拷贝。
5. 包内引用 `docs/references/previous_research_plan.md`（依据 [A02]）在开发包 99 个分节中不存在，属“被引用但未提供”的输入缺口，登记为 DEC-003，不猜测其内容。
6. `contracts/task_manifest.json` 与 `contracts/requirements.json` 在 START_HERE 中列出但当前不存在；按 T01 任务卡其为目标产物（T01 交付），非本包遗漏的运行入口。

## 3. 与默认目录树（docs/plan/02_architecture.md §3）的对应现状

| 默认目录 | 当前状态 | 计划建立任务 |
|---|---|---|
| `AGENTS.md` | 已存在（与包一致） | — |
| `README.md` | 不存在 | 后续文档任务（T55 之前按需） |
| `backend/`、`frontend/`、`config/`、`fixtures/`、`benchmarks/`、`experiments/`、`infra/`、`scripts/` | 均不存在 | T02 起按任务卡逐步创建，不预建空目录 |
| `docs/{plan,tasks,references,decisions}` | 仅 `docs/decisions/`（本轮建立） | T00 建立 `docs/decisions/`；其余随开发包物化决定（DEC-002） |
| `progress/` | 本轮建立 | T00 |
| `reports/{tasks,reviews,acceptance}` | `tasks/`、`acceptance/` 本轮建立；`reviews/` 暂无内容不预建 | 按需 |

## 4. 未决事项（需人工决定）

- DEC-001：是否授权在 `D:\dianzi` 执行 `git init`、关联远程 `https://github.com/Gowin-liuyin/dianziCup.git`，以及本地提交与 push 的授权范围。未获授权前不执行任何 Git 写操作。
- DEC-002：开发包 99 个分节是否物化为独立仓库文件及落点确认（建议物化到包内原路径，根目录保留原始拼接包作来源存档）。
- DEC-003：`docs/references/previous_research_plan.md` 是否另行提供；不提供则在来源清单标注缺失。

## 5. 2026-09-30 更新（T01 轮，保留 T00 时点历史，不改写上文）

| 变化 | 结果 | 记录 |
|---|---|---|
| DEC-001 执行 | 本地 Git 已建立：`git init -b main`（退出码 0），`origin → https://github.com/Gowin-liuyin/dianziCup.git` 已配置；未 add/commit/push/fetch | `docs/decisions/dec001_local_git_setup.md` |
| DEC-002 执行 | 开发包 99 分节物化为独立文件（98 创建、`AGENTS.md` 仅换行差异跳过、0 冲突）；原 ZIP 未在项目目录出现，按允许路径从完整阅读版拆分 | `docs/decisions/dec002_devkit_materialization.md`、`reports/acceptance/devkit_materialization.md` |
| 官方 PDF 路径 | 新增副本 `docs/references/competition_brief.pdf`（与根目录原件 SHA-256 一致）；原件保留 | 同上 |
| T00 时点说明修正 | “未改动/六项执行/blocked_live”表述澄清与证据补强 | `docs/decisions/t00_correction_appendix.md` |
| 新增目录 | `contracts/`、`fixtures/synthetic/`、`scripts/`、`tests/plan/`、`reports/runs/`、`.bootstrap/`（临时，不得入库） | `reports/tasks/T01.md` |

原 DEC-001/002/003 编号保留；DEC-001/002 已落实本轮授权部分，剩余（提交/push 授权、ZIP 补入比对）仍开放。
