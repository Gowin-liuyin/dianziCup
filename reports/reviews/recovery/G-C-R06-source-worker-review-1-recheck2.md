# G-C / R06 source worker M1 第二次定向复核

What this change does: 本次只把固定政策条款的正文终点同时限制到下一章标题，并把 CAC adapter 从 2 升到 3。合法原文继续完整解析；章节标题不再替缺失条款正文满足完整性条件。

**结论：Ship，限定冻结 `1456e22f8187643a9978e9fa44d57c945e73b5bc` 的 source normalizer + worker 已审组合切片，M1/M2 可关闭。** M2 依据明确 raw/NULL/unknown 合同，M1 依据原始负例定向复跑；不签整 R06、G-C、原 T 整卡或后续未审 polling/live。公共状态登记交主控，本 reviewer 未写 accepted。

## 版本、范围与独立性

- 同一非作者 reviewer `/root/r06_source_worker_combined_independent_review`，未参与修复实现。新干净 WT `D:/wt/r06-source-worker-review-1-recheck2`、分支 `codex/r06-source-worker-review-1-recheck2`，没有在旧两轮 WT 改产品或覆盖报告/日志。
- 父版本 `6dcce8b115ee3cb68bce814cf3f3ae91be9fcbf1` → 当前 `1456e22f8187643a9978e9fa44d57c945e73b5bc`，4 文件、36 增/5 删：`catalog_pages.py`、`tests/r06_source_worker_fixtures.py`、`test_r06_source_boundary_regressions.py`、`test_r06_source_boundary_pg.py`。唯一产品增量为 4 行章节终点检查和 CAC adapter3，其余为直接回归输入/断言。
- 原组合审查基线 49ee33f6 → 5243347/b2bd；首次修复 6dc 的 M2 明确合同、共同调用者、nullable 时间/API 投影和回滚/版本语义见前一轮复核报告。这些产品字节在 1456 未改，并在当前 117 unit/97 PG/19 独立 probes 内再次验证所需相关行为；不拿前一 SHA 的数字当当前实际运行数。
- 沿用已读 AGENTS/执行地图/R06/原 T08/T11–T16/03/04/05/07、CR-R04-R03/04/06、CR-R06 固定九源和时间精度小合同、最新 ponytail-review；本轮读全部新 diff、共同 parser/writer/caller 和直接测试。没有公共 DTO/schema/依赖/锁/金标/阈值/评分分母变化。

## 缺陷闭合证据

M1：`:517–521` 在拼接 article_text 前查找第一处下一章标题，将 end 截到该 block，不把章标题纳入上一条正文；既有下一条边界和末条内精确生效句检查保留。未改原 HTML 字节，固定源结构/生效句改变仍隔离，不据此判断法律适用性。CAC adapter3 明确标记新规则，原版本仍可追溯；JSON 来源 adapter2、AVID/NIST adapter1 保持。

6dc 本轮已证实的四纯负例和第八条 PG 负例从原 run **逐字节复制**后复跑。新 probes 文件 SHA256 `0768f52e51dfe2731624408895ee9a4caefa67cd5d52f92f20cd984db388457f`；第八条输入 SHA256 `fb203010bfa63596dea2482056e3baf30075bf3e7120552b9472114311a670b6`。四/八/十五/二十一条正文删除输入全部拒绝；第八条 worker blocked，documents/revisions/cursor/receipt 全 0。原完整官方 24 条、章布局、内联末条和末条正文删除正负例也通过，未修改旧红例期望。

M2：新合同合法 -00:00/7 位/9 位小数保持原文、PG NULL 和 published_precision unknown，非法 +00:99 等隔离。本次独立 OSV/release 共 6 个真 PG + 认证 HTTP GET 测试再次通过：原 response 与派生 member hash 各自校验，公开原值/unknown/精度提示一致，两个 API 前缀相同。真实 OSV `modified=2026-09-10T03:49:48.487641080Z` 原值保持，source_modified_at NULL，未伪截成六位 instant；adapter2/metadata/source_notes 仍受修订版本保护。

初审原 19 probes 文件 SHA256 `ba99307231353f4628dfce96f019633b7f3db0122dcc635de42071c7dc44cdf2`，仍完全原样。本次 15 passed/4 failed；仅两合法 unknown 的旧 blocked 期待和两旧 PG probe 的 NULL.isoformat 假设红。原输出保留，不改成 pass/skip；明确兼容合同的新 raw/NULL/API 断言独立全通过，因此不把这四个旧策略红例误称未修复产品错误。原非法偏移和缺末条正文失败条件实际已恢复。

## 实际命令与结果

环境 Windows/Python 3.12.13，自有 WT `uv sync --offline --frozen --extra semantic` 安装锁定 92 包，无模型下载。正式 cwd `D:/wt/r06-source-worker-review-1-recheck2/backend`，python 为该目录 `.venv/Scripts/python.exe`；独立 run `reports/runs/recovery_r06_source_worker_review_1_recheck2_20261015/`。同名 JSON 保存完整 argv（含绝对 JUnit/cache 路径）、+08 秒级时间、exit、数量、源码/日志 hash。

| run / +08 时间 | 实际核心命令 | exit / 结果 |
|---|---|---|
| focused_related / 22:21:25–22:21:32 | `python -m pytest tests/unit/test_r06_source_boundary_regressions.py tests/unit/test_r06_catalog_pages.py tests/unit/test_r06_source_catalog.py tests/unit/test_r06_source_worker.py --no-cov -q --tb=short --junitxml=…` | 0；117 passed（32+16+12+57）、0 skip |
| pg_frozen / 22:21:26–22:23:23 | `python -m pytest tests/integration/test_r06_source_worker_pg.py tests/integration/test_r06_source_worker_api_pg.py tests/integration/test_r04_source_jobs_pg.py tests/integration/test_r06_source_boundary_pg.py --no-cov -q --tb=short --junitxml=…` | 0；97 passed、0 skip（33 worker + 39 API 含原 HTTP11 + 原 worker19 + boundary6） |
| fixed_19_probes / 22:21:26–22:21:47 | `python -m pytest -c pyproject.toml <run>/test_recheck_probes.py --no-cov -q --tb=short --junitxml=…` | 0；19 passed、0 skip（原 5 红全部转绿，M2/API 相关正负例亦通过） |
| original_19_probes / 22:21:26–22:21:37 | 同命令，原 `test_independent_probes.py` | 1；4 failed/15 passed、0 skip；旧策略红原样保留 |
| static_ruff / 22:22:25 | `python -m ruff check` 四直接改动文件 | 0 |
| static_format / 22:22:25 | `python -m ruff format --check` 同四文件 | 0；4 formatted |
| static_types / 22:22:25–22:22:37 | `python -m mypy src --cache-dir D:/tmp/dianzi-r06-review1-recheck2-mypy-20261015` | 0；92 source files |
| product_diff_check / 22:22:25 | `git diff 6dcce8b… 1456e22… --check` | 0 |

PG 仅授权专库 `test_dianzi_r06_catalog_worker_20261015`、run ID `r06_catalog_worker_20261015`，逐例新 UUID schema。授权连接只进程内读取/替换，所有 PG run public 前后均 `{table_names:[]}`，无 umbrella fixture、downgrade、观察库修改或 DSN/口令输出。当前 97 例覆盖原九来源/八类、固定 POST/GET/MIME、raw/evidence、失败回滚/游标、partial/续页/重放恢复、原两源、HTTP 幂等/角色/CSRF/提交时认证变化；实际默认 runtime handler 与 PG 权威不变。

独立 CBM 官方 v0.11 新 cache/project 指向本冻结 WT backend/src，92 文件、1234 nodes/6208 edges、0 skipped/partial；get_architecture/schema/_policy_document trace 和完整 rg caller exit0。CBM/mypy cache 在仓外，产物清单排除全部 __pycache__/.pyc/cache；没有递归清理。已知 Starlette/httpx 弃用与外置 probes 导入前 real_pg marker 注册顺序 warning 都保留，不是业务失败，不以 skip 隐藏。

## 未运行与交接

依主控有界授权，本轮没有重复全纯门：**1456 全 unit/contract/security 覆盖率门 not_run**；前一冻结 6dc 的独立 1788/74.52% 属历史证据，不能写成 1456 成绩。当前只确认上述 117 相关 unit、97 PG、19 新合同 probes 和静态检查。主控最后集成仍应按最终同 SHA 运行阶段全门。

没有新外网、模型、付费、DPAPI、浏览器、HTML scripts 或 PoC 执行。记录/合成响应、实际隔离 PG 和本地 HTTP 只算对应合同/集成，不能算新七源 live、持续时效、正式分母达标或评分优秀。自动 polling/正式统计/长期观测与整 R06/G-C 未查。后续建议为主控登记限定闭合、合入冻结组合，再由各范围 reviewer 审 polling/UI 和执行同集成 SHA 的 live 验证。

没有业务/公共状态/锁/金标/阈值修改或 push。所有旧报告、旧失败日志与旧 probes 继续保留；本报告/manifest 冻结时间与 hash 见 evidence_manifest.json。结束本次复核并释放槽位。

Verdict: Ship（仅此冻结 source normalizer + worker 已审切片；M1/M2 closed）。
