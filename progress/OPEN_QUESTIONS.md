# OPEN_QUESTIONS

记录被跳过/等待用户输入的事项。每条含：已经验证的事实、具体缺口、影响任务、可以继续的独立部分、最小所需输入。本文件由批次20（2026-10-24）建立。

## OQ-1 Docker Desktop daemon 不可达（批次20 主路径冒烟真实执行被阻塞）

**状态更新（2026-10-24T11:1x+08:00）：daemon 已由用户恢复，但 WSL2/Docker Desktop 虚拟交换机数据面故障，真实冒烟经 6 次尝试仍被环境阻塞。**

- 已验证事实（全部落盘 `reports/runs/batch20_main_path_smoke/`）：
  1. daemon 恢复后 core profile 容器可启动且健康（pg_isready 容器内 unix socket 正常）；
  2. 端口发布对任意端口（25499/29500）静默失败：HostConfig.PortBindings 有请求、NetworkSettings.Ports 运行时为空、宿主 netstat 无监听；
  3. 宿主→容器 TCP 握手成功但数据包黑洞（对 172.19.0.2:5432 发送 PG SSLRequest 无响应）；
  4. compose 网内容器→postgres 同样失败（smoke 在网内临时容器、uv 锁定安装成功后仍 `database unreachable`）；
  5. 网桥容器→互联网数据正常（uv sync 成功装完锁定依赖）。
  - 结论：仅虚拟交换机跨端数据面损坏（宿主↔容器、容器↔容器），容器内 loopback 与 VM 出网正常。10-23 同一路径正常，判断为 10-24 会话期间宿主环境变化（安全/代理软件或 WSL 网络状态）。
- 具体缺口：需要用户修复宿主虚拟网络（建议顺序：重启 Docker Desktop → `wsl --shutdown` 后重启 → 排查当日新启用的代理/安全软件）。本批按约定未执行任何修复操作。
- 影响任务：smoke_main_path.py 真实执行；任何宿主侧容器验证。
- 可以继续的独立部分：脚本本身已验证（退出码合同 0/1/2，env-guard=2 实测，锁定依赖安装成功并真实运行到连接阶段）；主路径流程以 10-23 证据为参照。
- 最小所需输入：宿主网络恢复后执行一条命令即可（恢复 `--profile core` 并以 `DATABASE_URL=postgresql://story_smoke:<随机口令>@postgres:5432/story_smoke_20261024` 在网内容器或宿主运行冒烟，见证据文件 attempt6 记录的完整命令形态）。

## OQ-2 content_read_worker 子进程在 uv 管理的 venv 下必然导入失败（16 个 r07 链红的根因）

- 发现时间：2026-10-24T02:2x+08:00（批次20基线甄别）
- 已验证事实（含最小复现）：`backend/src/ai_intel/infrastructure/content_store.py` 在 Windows 下以 `base_prefix/python.exe` + `PYTHONPATH=<venv>/Lib/site-packages` 启动 `ai_intel.infrastructure._content_read_worker` 子进程；该 venv 由 `uv run`/`uv sync` 管理时项目始终以 editable 安装（`_editable_impl_ai_intel_backend.pth` 内容即 `D:\dianzi\backend\src`）。PYTHONPATH 目录不做 .pth 处理，且 `uv run` 每次都会把 `uv sync --no-editable --reinstall-package ai-intel-backend` 的实体安装翻转回 editable（已实测翻转），因此子进程内 `import ai_intel` 恒为 ModuleNotFoundError → `OSError: content_read_worker_unavailable`（content_store.py:233）→ `tests/unit/test_r07_source_io_deadline.py` 等 16 个测试失败。产品代码在不可编辑安装（如容器镜像）下无此问题。
- 具体缺口：需要评审决定修复方向：(a) 约定本机测试一律 `UV_NO_SYNC=1` 且 venv 保持非 editable 安装（工作流约定）；(b) spawn 环境构造中追加源码布局路径（触碰安全敏感的子进程环境边界，需按变更单走）。
- 影响任务：批次20基线中 16 个 r07 source-io/report/enricher 链测试的分类（环境回归，非代码缺陷）；任何依赖 content_read_worker 的离线验证。
- 可以继续的独立部分：其余全部离线测试、DTO、R06 单测、冒烟脚本编写。
- 最小所需输入：评审在 (a)/(b) 间做出决定（或给出第三方案）。

## OQ-3 t06 秘密扫描遗留未分类 finding（54 处，含 10-23 证据脚本）

**状态更新（2026-10-24T11:3x+08:00）：决议经历一次修正。** 用户授权自决后先执行了逐条分类（54 条记录，全部验证为合成值并带证据链，t06 一度 15 passed 转绿）；随后发现分类表受 R20 冻结登记控制（`tests/security/test_r20_secret_provenance.py` 冻结 total_records=136 = 原 54 + 已审增补 82，且扩展需完整的提案证据束程序），单方面追加登记等于绕过该变更单级控制。已回退分类表至 136 条（R20 复测全绿 158 passed），**54 条已建好的分类记录连同证据链保存于 `reports/runs/batch20_secret_classification_20261024/classification_records_54_ready_to_land.json` 作为待落地提案材料**。

- 落地路径：按 R20 提案程序为 54 条记录建立 fixture bundle + fixture_bindings + 更新 total_records（54→190），走变更单；完成后 t06 转绿。
- 影响：t06 维持唯一历史红（16 codec + 2 迁移 head + 1 t06 = 19 failed 最终余量）；不影响其他批次。
- 最小所需输入：评审/下一批次按 R20 程序落地上述提案材料。
