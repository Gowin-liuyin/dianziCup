# OPEN_QUESTIONS

记录被跳过/等待用户输入的事项。每条含：已经验证的事实、具体缺口、影响任务、可以继续的独立部分、最小所需输入。本文件由批次20（2026-10-24）建立。

## OQ-1 Docker Desktop daemon 不可达（批次20 主路径冒烟真实执行被阻塞）

- 发现时间：2026-10-24T01:34:18+08:00
- 已验证事实：`docker info --format "{{.ServerVersion}}"` 报 `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine … The system cannot find the file specified`；进程列表中无任何 Docker 进程（Desktop 未运行）。现场落盘 `reports/runs/batch20_main_path_smoke/docker_preflight_20261024.txt`。10-23 的同类故障与恢复过程见 `reports/runs/story_fixture_20261023/`（当时曾崩溃循环，后成功恢复并在临时库上跑通主路径）。
- 具体缺口：需要用户启动 Docker Desktop 并确认 Linux engine 正常（本批按约定不执行任何修复性操作，不重置、不删数据）。
- 影响任务：批次20 B4 的 `scripts/smoke_main_path.py` 真实执行（脚本本身已编写）；任何需要 PostgreSQL/Redis/OpenSearch 容器的验证。
- 可以继续的独立部分：脚本编写与入库、全部离线单元/合同测试、DTO 纠偏、R06 单元红。
- 最小所需输入：用户启动 Docker Desktop 后回复即可，冒烟脚本随时可真实执行一轮并落盘证据。

## OQ-2 content_read_worker 子进程在 uv 管理的 venv 下必然导入失败（16 个 r07 链红的根因）

- 发现时间：2026-10-24T02:2x+08:00（批次20基线甄别）
- 已验证事实（含最小复现）：`backend/src/ai_intel/infrastructure/content_store.py` 在 Windows 下以 `base_prefix/python.exe` + `PYTHONPATH=<venv>/Lib/site-packages` 启动 `ai_intel.infrastructure._content_read_worker` 子进程；该 venv 由 `uv run`/`uv sync` 管理时项目始终以 editable 安装（`_editable_impl_ai_intel_backend.pth` 内容即 `D:\dianzi\backend\src`）。PYTHONPATH 目录不做 .pth 处理，且 `uv run` 每次都会把 `uv sync --no-editable --reinstall-package ai-intel-backend` 的实体安装翻转回 editable（已实测翻转），因此子进程内 `import ai_intel` 恒为 ModuleNotFoundError → `OSError: content_read_worker_unavailable`（content_store.py:233）→ `tests/unit/test_r07_source_io_deadline.py` 等 16 个测试失败。产品代码在不可编辑安装（如容器镜像）下无此问题。
- 具体缺口：需要评审决定修复方向：(a) 约定本机测试一律 `UV_NO_SYNC=1` 且 venv 保持非 editable 安装（工作流约定）；(b) spawn 环境构造中追加源码布局路径（触碰安全敏感的子进程环境边界，需按变更单走）。
- 影响任务：批次20基线中 16 个 r07 source-io/report/enricher 链测试的分类（环境回归，非代码缺陷）；任何依赖 content_read_worker 的离线验证。
- 可以继续的独立部分：其余全部离线测试、DTO、R06 单测、冒烟脚本编写。
- 最小所需输入：评审在 (a)/(b) 间做出决定（或给出第三方案）。

## OQ-3 t06 秘密扫描遗留未分类 finding（54 处，含 10-23 证据脚本）

- 发现时间：2026-10-24T02:3x+08:00
- 已验证事实：`tests/security/test_t06_authentication_and_scope.py::test_audit_and_sources_carry_no_secret_values_t06_c06` 自 2026-10-16 晚（分类表 `reports/security/recovery_fixture_false_positives.json` 最后更新 19:27，晚于其的前端测试文件 21:27/23:57 提交）起即为红。当前未分类 finding 共 54 处：前端测试文件（assessments/investigations/recommendations 等合成凭证形状）、`reports/runs/` 下 2026-10-14~16 评审产物、以及批次19入档的 `reports/runs/story_fixture_20261023/verify_story.py`（2 处，10-23 真实运行证据脚本，不宜改动）。批次19/20 新增文件（`backend/src/ai_intel/fixtures/main_path_story.py`、`scripts/smoke_main_path.py`）的命中已通过等值改写（f-string/局部变量，运行时值不变）清零。
- 具体缺口：需要评审按白名单机制为遗留 finding 逐条建立带证据链的分类记录（尤其 verify_story.py 的 2 处）；批量自我分类不属于本轮权限。
- 影响任务：t06 安全扫描测试保持历史红；不影响其他批次。
- 可以继续的独立部分：全部离线测试与质量门。
- 最小所需输入：评审对 54 处逐条分类或授权批量分类标准。
