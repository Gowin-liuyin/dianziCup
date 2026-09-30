# 阻塞登记（progress/blockers.md）

建立：2026-09-30（T00）｜规则：保留历史，不删除旧条目；解除时标注日期与证据，不覆盖原文。

| ID | 阻塞事实（已验证） | 类型 | 影响任务 | 可继续的独立部分 | 最小所需输入 | 状态 |
|---|---|---|---|---|---|---|
| BLK-001 | Docker 守护进程未运行：`docker info` 退出码 1（npipe 连接失败）；CLI 29.2.0 与 Compose v5.0.2 已安装 | 环境资源 | T03、T05 及一切需容器的集成/live 验证（T16、T50 等） | 纯文档、domain 纯函数、JSON Schema/合同、不依赖容器的单测 | 人工启动 Docker Desktop 或授予启动权限 | open |
| BLK-002 | 无模型/embedding/rerank/FOFA 凭据：环境中无秘密类变量，仓库无 .env；仅查存在性未取值 | 外部凭据 | T18 真实模型接入、T25 FOFA 观察及依赖 live 的验收项 | 接口定义、测试替身、离线 fixture（显式标记）开发 | 用户指定提供者与密钥注入方式（环境变量名即可），及费用上限授权 | open（blocked_live） |
| BLK-003 | `D:\dianzi` 非 Git 仓库（`git rev-parse` 退出码 128）；远程 `Gowin-liuyin/dianziCup` 为空仓库（ls-remote 退出码 0、0 ref） | 工程流程 | 一切需要提交/diff/复现基线的验收（E1/D1 证据链、T51、T57） | 不依赖版本历史的本地开发与文档 | DEC-001：git init、远程关联、commit/push 授权 | open |
| BLK-004 | 资源事实未确认：队伍人数、截止日期、部署位置、授权资产、人工标注可用性（10_provenance §3 明示不得假设） | 人工输入 | T24（资产范围）、T46（金标）、T51/T59（部署发布）、T54（持续运行）、排期 | T01、T02 等不依赖上述资源的任务 | 用户逐项确认（10_provenance §3 清单） | open |
| BLK-005 | web_fetch 访问 github.com 被工具策略拒绝（主机名解析为非公开 IP）；`git ls-remote` 同一远程可达 | 工具限制 | 仅影响以网页抓取方式核对 GitHub 页面的任务 | git 协议操作、本地审计 | 无需输入；如需网页核对请人工提供页面内容 | open（低影响） |
| DEC-001 | git 工作流授权（init/remote/commit/push 范围）未决 | 待决定 | 同 BLK-003 | 同 BLK-003 | 用户授权 | open |
| DEC-002 | 开发包 99 个分节是否物化为独立仓库文件及落点未决（包当前为单文件拼接） | 待决定 | T01 起各任务的文档引用路径稳定性 | 以拼接包行号引用可继续 T01 | 用户确认物化方式与落点 | open |
| DEC-003 | `docs/references/previous_research_plan.md`（依据 [A02]）被引用但包内不存在 | 输入缺口 | 依赖 [A02] 内容的对照设计（影响有限） | 不依赖该文档的任务 | 用户提供或确认以现有包内文档为准 | open |

说明：外部不可达与凭据缺失不记为软件缺陷；live 阻塞在最终验收中不得视为通过（AGENTS.md §3）。

## 2026-09-30 更新（T01 轮，保留上表历史，不覆盖原文）

| ID | 更新 | 状态 |
|---|---|---|
| BLK-001 | 不变：Docker 未运行；本轮未启动、未改配置（T03 资源缺口，非 T01 阻断） | open |
| BLK-002 | 不变：无模型/FOFA 凭据；T01 的 live=not_run，不受阻 | open（blocked_live） |
| BLK-003 | 部分缓解：DEC-001 已执行本地 `git init -b main` + `origin` 配置（`reports/runs/t01_git_init.log`）；**提交/push 仍无授权** | open（部分缓解） |
| BLK-004 | 不变：人数、截止、部署、授权资产、标注、费用/网络范围仍 unknown/to_confirm | open |
| BLK-005 | 不变（低影响） | open |
| BLK-006 | **新增**：原开发包 ZIP（`赛题九_Agent工程开发包_20260930.zip`）未在项目目录出现；`contracts/*.json` 为按任务卡生成，字段结构可能与 ZIP 原始结构不同。影响：T02+ 沿用字段时的兼容性。最小所需输入：ZIP 补入项目目录后先做结构比对再合并（不得覆盖本轮真实进度）。不影响 T01 验收 | open |
| DEC-001 | 本轮已落实 init/remote 部分；剩余：commit/push 授权、`.bootstrap/` 排除规则 | open（部分落实） |
| DEC-002 | 本轮已落实（98 创建/1 跳过/0 冲突，见 `reports/acceptance/devkit_materialization.md`）；剩余：ZIP 补入后比对 | open（部分落实） |
| DEC-003 | 不变：`docs/references/previous_research_plan.md` 未提供 | open |

## 2026-09-30 更新（Goal 第 5 轮，保留上表历史，不覆盖原文）

| ID | 重新核实结果（实测） | 状态 |
|---|---|---|
| BLK-001 | 再次实测 `docker info` 退出码 1（npipe 管道不存在）：守护进程仍未运行。影响范围不变（T03/T05 及需容器的集成与 live 验证）；最小用户操作不变：启动 Docker Desktop。T02 不受影响 | open（今日两次实测确认） |
| BLK-002 | 不变：无模型/embedding/rerank/FOFA 凭据；本轮未读取任何密钥值。只阻断真实接口验证，不阻断离线开发 | open（blocked_live） |
| BLK-003 | 不变：git 已 init（main、origin）、**仍无任何提交**（R-T00 21:07 复核 `git log` 退出码 128）；本 Goal 未获 add/commit/push 授权，版本标识继续用文件哈希与日志 | open（部分缓解） |
| BLK-003 | **2026-09-30 Goal 轮 77 更新：用户指示「每轮一个 commit」→ 本地提交授权已获得**。累积基线提交 `1ec7efd`（306 文件/35537 行，含 .gitignore）已建立；此后每轮一提交；**push/fetch 仍无授权** | closed（本地提交）/ push 仍 open |
| BLK-004 | 不变：人数、截止、部署位置、授权资产、人工标注、费用/网络范围仍 unknown；合并最小用户输入清单见下 | open |
| BLK-005 | 不变（低影响）；本轮未复现（R-T00 记 not_run） | open（低影响） |
| BLK-006 | 不变：原 ZIP 仍未补入。依据官方 PDF + 任务卡 + 计划文档审查重建内容（R-T01 已独立复现官方依据链：PDF 哈希一致、pdftotext 165 行逐字节一致）；格式差异不判失败 | open（不阻断离线路径） |
| 环境新事实 | uv 管理的 cpython-3.12.13 于 2026-09-30 21:11 安装成功（退出码 0）：T02 合同要求的 Python 3.12 前置已满足，无需 ADR 偏离；系统默认 Python 3.13.11 未改动 | 已解决（原“无 3.12”差异关闭） |
| 缺陷记录 | FIND-001（T06↔F1 映射偏离任务表）、FIND-002（compare_baseline 不比对 source_hashes）：R-T01 审查发现 + 主控独立核实，FIX-T001 修复中，走变更单 cr001 | 修复中（非环境阻塞） |
| BLK-001 补充（Goal 第 25 轮实测） | Docker Desktop 已安装（`C:\Program Files\Docker\Docker\Docker Desktop.exe` 在位）；当前无任何 docker 进程运行，`docker context ls` 显示 desktop-linux 上下文存在。最小用户操作精确化为：启动 Docker Desktop（或由授权的本机开发服务启动动作代为启动）。Goal 已授权本机隔离开发服务启动，T03 时可直接启动，无需另行申请 | open（细化） |
| 缺陷关闭 | FIND-001/FIND-002 已由 FIX-T01 修复 + RV-FIX 独立复查通过（reports/reviews/RV-FIX.md，转录落盘见其声明）；cr001 变更单归档 | closed（2026-09-30） |
| BLK-001 关闭 | Goal 第 35 轮：主控启动 Docker Desktop（仅启动已安装应用，未改任何系统设置），引擎就绪——`docker info` 退出码 0，ServerVersion 29.2.0，desktop-linux 上下文正常。T03/T05 的容器集成验证前置已满足 | **closed（2026-09-30，新证据：docker info exit 0）** |

### 合并的最小用户输入清单（不重复追问已决定事项）

1. 本地 git commit/push 授权范围（含 `.bootstrap/` 排除规则）——DEC-001 剩余部分。
2. 原开发包 ZIP 是否补入项目目录（BLK-006；补入后先语义比对再合并，不覆盖现有进度）。
3. 模型/embedding/rerank/FOFA 提供者、注入方式（环境变量名即可）与费用上限授权（BLK-002；T18/T25 真实验证前置）。
4. 队伍人数、截止日期、部署位置、授权资产范围、人工标注可用性（BLK-004；影响 T24/T46/T51/T54/T59）。
5. Docker Desktop 启动（BLK-001；影响 T03/T05 集成验证，纯离线开发不受阻）。

