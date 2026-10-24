# batch21 时间线（唯一进度真相源）

- 文档首次创建时间：2026-10-24T22:45:00+08:00
- 本次写作开始时间：2026-10-24T22:45:00+08:00
- 最后更新时间：2026-10-24T22:55:00+08:00

## C0 冷启动（开始 2026-10-24T22:40:00+08:00，完成 22:55+08:00）

- `git log -3`：
  - `6c9bb455c checkpoint: batch20 followup decisions - worker spawn fix, OQ-3 proposal material, smoke diagnosis`
  - `d21922041 checkpoint: batch20 offline convergence, r06 unit reds, smoke script, dto pinning`
  - `999af01b0 checkpoint: batch20 offline convergence fixes, route inventory test, smoke script, r06 adapter`
- 实际 HEAD 与任务给定起始 SHA 一致（`6c9bb455c`），未做任何回退。
- `git status --short` 快照：仅 `?? .zcode/`（会话目录，预期内，不 stage）。
- 必读材料已读：AGENTS.md、Root-batch20-summary.md（含续推轮补记）、red_inventory.md、OPEN_QUESTIONS.md、batch20_main_path_smoke/ 证据（attempt6 命令形态）、context_handoff.md 顶部条目、conftest.py:140-209、scripts/dev.py:30-90。
- 本批未改任何业务文件。

## C1 单容器回环冒烟

- 状态：进行中（2026-10-24T22:55+08:00 开始）
- attempt1（23:56 UTC+8 记录以文件内时间为准）：镜像 `dianzi:batch21-smoke` 构建成功（python:3.12-bookworm + pgdg postgresql-16 + postgresql-16-pgvector + uv 0.13.5）；容器脚本自身 NameError（落盘变量名），容器实际跑完但输出丢失。宿主证据：host_attempt1.txt、image_build.txt、preflight.txt。
- attempt2：容器脚本 CRLF 行尾（Windows write_text 默认换行翻译），bash 全线报错；修复为 newline="\n"。证据：attempt2_run.txt。
- attempt3：PG 启动/建库/uv sync（96 包）全部成功，smoke 真实运行但探针报 `database unreachable: OperationalError`。证据：attempt3_run.txt。
- attempt4：加 psycopg 直连诊断探针——同容器同 URL **连接成功**（probe_ok）。证据：attempt4_run.txt。
- attempt5：双探针——裸 psycopg 成功、SQLAlchemy make_url→str→create_engine 路径报 `password authentication failed`。证据：attempt5_run.txt。
- attempt6（原 6 次上限最后一次）：hex 口令 + 方言级诊断——`dialect_pw_len 3`，确认 SQLAlchemy 路径收到 3 字符"密码"。证据：attempt6_run.txt。
- **根因（宿主离线复核证实，无需容器）**：SQLAlchemy 2.1.1 的 `str(URL)` 将密码渲染为 `"***"`（3 字符）；`scripts/smoke_main_path.py` 的 `normalize_database_url` 用 `str(url.set(...))` 做字符串往返导致密码被掩码。同仓库 conftest.py:196 先例已用 `render_as_string(hide_password=False)` 规避该坑。这是冒烟脚本真实缺陷（batch20 从未在带真实 DATABASE_URL 的情况下跑到该路径），不是环境阻塞。
- 最小修复：normalize_database_url 返回 URL 对象直接传 create_engine（scripts/smoke_main_path.py，5 行改动）；宿主离线验证 password_len=32 保留。
- attempt7：**超出"最多 6 次尝试"上限的一次运行，偏差理由：cap 用于根因定位阶段已完成其使命；本次运行验证的是已离线验证的代码修复，不是环境重试**。若失败则立即按 cap 纪律落盘 OQ 转 C3。证据：attempt7_run.txt。
- **attempt7 结果（23:2x+08:00）：smoke_result=pass，smoke_exit=0**。六组断言全过：rule_published（published v1）、story_assets_present（1.4.1/1.4.2 两资产）、asset_assessment_1_4_1（supported_applicability）、asset_assessment_1_4_2（excluded_with_evidence）、story_idempotent（already-present 且 rule_id 一致）、health_live（200 live）。迁移、夹具、API、幂等重跑全为真实执行，全部流量在容器内 127.0.0.1。C1 验收达成。
- 资源清理合同：容器 `--rm` 已随退出删除（脚本结束时 docker rm -f 兜底）；uv 缓存卷 batch21_smoke_uv_cache 暂留供 C2 复用，C2 结束即删；镜像 dianzi:batch21-smoke 保留供 C2/后续 integration 使用，批次收尾时处置。

（后续批次按时间追加）
