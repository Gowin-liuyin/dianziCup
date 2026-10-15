# G-B / R04 pipeline Must 2 定向复核

审查人：`/root/r04_pipeline_independent_review`，未参与本次修复。固定候选 `8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce`，tree `1b9a94ac49b58ddd12debb40f173749dbd3110a7`。使用新版 ponytail-review 5.2.0，中文报告。首次创建/最后实际保存时间见本轮 `review_document_times.json`；测试时段不代替编码工时。

**What this change does:** 厂商来源改用实际响应 Link 中的 after 游标，在 PG 保存 `cursor_version=2/after`，下一请求仍重建固定命名仓库 URL。无 next 才完成；历史整数 page>1 明确 blocked，重复 Link 头在共享 HTTP 层转为字典前拒绝。

**Verdict: Ship（仅本次分页 Must 2 修复及关联边界切片）。** 原两个失败用例在同一公共原样本、同一期望下均通过，Must 2 在本固定版本关闭；Must 1 空 package 维持 7184 已关闭。本轮未发现额外可复现 Must。不是完整 R04、实际来源持续采集、模型/UI 或 G-B 阶段验收，不改 progress/accepted。原 95/7184 的失败、错误 Ship 草稿和撤回记录完整保留于[初审报告](G-B-R04-pipeline-review-1.md)及其原始目录。

## 冻结范围与依据

- 独立新工作树 `C:/Users/yinha/.codex/worktrees/recovery-r04-cursor-recheck/dianzi`，分支 `codex/review-r04-cursor-recheck-20261015`，由固定 SHA 创建。未审主控活目录、未改业务、迁移、锁、合同、状态或盲测，未提交/push。
- 复核 `5ca5664 → e6ce5ae` 的 `source_jobs.py`、`source_documents.py`、直接 unit/PG 测试，以及共享 `http_transport.py` 的 Link guarded header 与三参数安全回归；核对现行来源任务 CR（`c3d5129`）。读取 AGENTS、执行地图、11 恢复计划、R03/R04/R05 边界及当前状态索引；前轮已经读取的原 T09/T10/T12/T17/T40/T41 和冻结数据/工作流/证据合同继续适用。
- 相对 7184 的模型 generation/client/json_output 与 UI 后续变更不作本次代码审查。完整 unit 及共享 POST/timeout 检查是回归证据，不能转为这些子系统的独立验收。未将作者 575 unit/44 PG 或主控旧 114 HTTP 结果替代本轮运行；旧共享 HTTP 命令未单独记录的起止不补写。
- 作者 `R04-vendor-cursor.md` 及实际源码/测试仅作输入。当前 CR 已明确撤销旧 page 合同，保留旧历史；NVD metadata/offset、7 秒延后、20 页上限、PG 唯一重试和任务围栏保持。没有以参考文档或模型输出修改权限。

## 原失败闭合与输入边界

原 Must 2 输入继续使用前轮保存的公开响应：page1/page2 完全相同，115956 bytes，SHA-256 `f5007db50489ecebbbfec5d8cc8798eb18cff1d12faf503795ce97c85e6894e1`，真实 Link 中 after 为 `Y3Vyc29yOnYyOpHOAAg-eQ==`。此次不发任何外部 GET；该证据为 recorded/fixture 回放，PG 真实不等于来源 live。

原 `test_actual_vendor_pagination.py` 逐字节复制到新审查目录，未修改输入/断言；原本 7184 的 2 failed，现在 2 passed：固定请求使用 after 而非 page，handler 的 PG 位置也是实际 after，window 未被假置完成。原样本与测试文件 hash 由本轮 manifest/输入身份收据保存。

源码和可观察断言交叉核对：

1. Link 只接受 `https://api.github.com` 默认/显式 443、命名 vLLM 路径或已核实 numeric `599547518` 路径，固定 per_page=10/state=published/唯一 after。提取值后重建命名路径，未直接跟随不可信 URL；外域、私网、其他路径/仓库、userinfo、未知/重复/mixed page 参数、fragment、空端口、畸形 Link、重复 next 都被拒绝。
2. after 是 1..2048 的有界不透明 ASCII 查询值，不解码成操作。重复当前 after 明确失败；失败页所有业务/采集/回执修改回滚，保留已提交前页游标。
3. 两页实际走 `execute_job`/PG，第二页 URL 带 after；空末页和有新成员末页都结束。没有 next 的满十条页也结束，不再按条数猜下一页。下一任务延后 7 秒仍持久保存。
4. 旧持久位置 `page>1` 不联网、不清回执、不重置游标，错误码 `legacy_vendor_cursor_requires_restart` 且 blocked；`page=1` 仅兼容首位置。原文服务仍能接收历史 page URL，不代表新任务使用旧分页。
5. `source_documents` 的 6500 只覆盖 vendor 2048 字符最坏 URL 编码膨胀，NVD 仍为 2000。额外独立测试让最大游标经过第一任务/PG、第二次固定 URL、原响应入库和 `fetch_attempts.final_url`，超过 6000 字符的 URL 可完整保存并结束窗口；NVD 超 2000 仍拒绝。相关 DB 列为既有 Text，无迁移。
6. 共享 HTTP 的 `response.getheaders()` 原始列表先执行大小写不敏感重复 Link 检查，才 `dict(...)`。`Link`/`link`/`LINK` 三例均经实际 HTTP 解析+隔离 socket fixture 拒绝，socket 关闭；不是只在已经丢掉重复项的字典上判断。
7. sourcewriter 原 25 PG 回归继续覆盖原字节、原成员、事件别名、无 CVE/后补、A→B→A、scope、证据支持/坐标、整页 rollback 和四线程。未知 package 的 writer guard 仍不生成虚假产品/版本事实；本轮未重新定义 R16 撤回传播。

## 实际命令与结果

执行 cwd 均为新固定 WT 的 `backend`。工具为锁定 `uv run --locked`，CPython 3.12.13、68 包；独立 venv `/tmp/dianzi-r04-cursor-review-20261015/venv`，独立 `COVERAGE_FILE=/tmp/dianzi-r04-cursor-review-20261015/<label>.coverage`。完整 argv、cwd、+08:00 秒级起止、exit、JUnit 数量保存在同名 `*.command.json`，未覆盖旧失败。

| label / pytest 目标 | 开始–结束 +08:00 | 实际结果 |
|---|---|---|
| `original_must2_red_green_2` / 原独立两失败用例 | 14:52:20–14:52:29 | **2 pass**，1 纯函数+1 真实 PG；exit 0，0 fail/error/skip |
| `source_cursor_pg_2` / `tests/integration/test_r04_source_jobs_pg.py` | 14:52:20–14:53:14 | **19 真实 PG pass**；exit 0，0 skip |
| `writer_25_regression` / writer 精确资源副本 | 14:53:20–14:54:00 | **25 真实 PG pass**；exit 0，0 skip |
| `pure_unit_current` / `pytest tests/unit -q --cov-report=json:...` | 14:51:43–14:52:39 | **678 unit pass**；exit 0，0 fail/error/skip，1 既有 Starlette deprecation warning |
| `shared_http_114` / R03 transport 文件 | 14:52:20–14:52:23 | **90 socket-fixture pass**；exit 0，0 skip。label 预填 114 不代表数量，真实数量为 90 |
| `shared_http_post_24` / R05 POST + timeouts 两文件 | 14:54:40–14:54:42 | **24 socket-fixture pass**（20+4）；exit 0，0 skip；与前行共 114，非 live HTTP |
| `maximum_cursor_pg_and_nvd_boundary` / 本 reviewer 新边界 | 14:54:40–14:54:47 | **2 pass**，1 真实 PG+1 纯函数；exit 0，0 skip |
| `cursor_static` / Ruff check、format --check、mypy src | 14:53:20–14:53:25 | 三命令 exit 0；77 格式文件、72 源码类型检查 |

当前固定 root 候选含更多模型代码/测试，因此本轮纯 unit 数为 678、raw coverage `3511/5421 = 64.76664821988562%`（1910 missing、42 既有 excluded），不能写成作者旧树的 575 或 `3141/5093`。原 60 门保留，未混入 PG 抬覆盖率、未改金标/分母/阈值/skip/忽略规则。部分定向用例与完整 unit 重复，不相加成正式独立样本量。

第一次同时启动三个审查 wrapper 时，两个在 pytest 前因我自己的 check-then-CREATE DATABASE 竞态退出 1；另一个已创建同一个自有库。pytest 没有执行，测试数量 not_run，不是业务失败。摘要/实际错误/命令/工具 chunk 保留在 `pre_pytest_bootstrap_failure.json`；首次封装尚未记录时钟，start/end 保持 null，不编造。之后只核验已准备数据库，使用 `_2` 新 label 复跑，不改业务代码。其他检查没有失败或 skip。

自有库 `test_dianzi_r04_cursor_review_20261015`；每例隔离 schema，不升级旧数据库。原 writer 硬编码库名只在副本替换为此库，`FIXTURES` 和 conftest `PROJECT_ROOT` 绑定新 WT；输入/期望不变，`test_adaptations.json` 与逐文件 `.adaptation.diff` 保存 hash/diff。没有编辑业务树测试以匹配资源。

## 图索引与代码版本封存

未发现已注册 codebase-memory-mcp 工具，按已核对的 v0.11.0 portable CLI 实际执行 help→独立 index→schema→architecture→trace。项目 `dianzi-r04-cursor-review-8f6bd9f`，cache `/tmp/dianzi-cbm-r04-cursor-review-cache`，`CBM_ALLOWED_ROOT` 仅新 WT `backend/src`。实际 index **72 Python files / 958 nodes / 4529 edges**，not-indexed/skipped/partial/unusable 为 0，`__pycache__` 明确排除；无 secrets、holdout、样本或报告入图。

13 条命令及其时刻/exit 在 `cbm.command.json`，均 exit 0。图与源码/rg/PG 实测交叉追踪默认 runtime handler→固定 URL→共享 gateway→原文服务→`_next_position`/`_vendor_next_after`→PG cursor/receipt/outbox；`validate_vendor_after` 在写入边界和 Link/URL 路径共享。图仍未完整解析嵌套 handler，不把无边当作未接线。

native Windows Git 的 `candidate_windows_git.json` 保存固定 HEAD/tree、干净 status、diff exit 与每个源码的候选 blob/路径过滤后工作 blob/SHA-256。WSL Git 的全工作树 diff hash `109bd8e7...d8906e` 含 Windows 行尾过滤差异，不能当业务补丁；以 native 干净与源码 blob 一致性确认执行版本。原失败测试文件、CR、源文件及所有 raw 日志由 manifest 封存。

## 限制、资源与下一步

unit/录制合同/本次 PG 与 socket 边界检查通过；本 reviewer 没有启动真实 worker/浏览器、没有外部 GET、没有真实模型/产品 key 或付费任务。本轮没有调用 MinIO，未创建/删除对象桶；对象写入均为隔离 filesystem fixture。主控 MinIO 换段、真实厂商 403/额度缺口与后续 live 观测不由本报告认证，不能把录制回放或通过的整数 page 旧 fixture 计为来源覆盖。

完整 R04、NVD/厂商实际采集→worker→PG/MinIO→API/页面、真实后页覆盖、时间过滤/观测、R05 模型/UI/正式指标、R16 更新传播和 G-B 阶段门仍由对应任务/独立审查负责。本次只支持 F1/E1 的分页原子性与输入边界切片，不声称七类覆盖、准确率或连续运行时间。

改动只含本报告与 `reports/runs/recovery_r04_pipeline_review_1_recheck_20261015/**`。最终 `resource_close.json` 检查自有 schema/其他连接为零，保留空专用 DB 供复现；未关闭共享服务。秘密只在进程内读取测试 PG 连接；完整 DSN、完整密码及密码任意八字节片段扫描与文件 SHA-256/大小清单在 `secret_scan.json`、`manifest.json`。本轮结束释放审查执行资源，不自行接受整卡或 push。

下一步建议主控引用此固定 Must 2 闭合证据，在额度与受控资源就绪后补实际后页/剩余 R04 live/UI 证据，再交全新阶段 reviewer 检查；不能仅据本报告跨阶段。
