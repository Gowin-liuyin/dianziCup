# G-C / R06 source worker 初审 M1/M2 定向复核

What this change does: 本修复把新资料来源的合法未知 offset/高精度时间保留为原值，PG 不写伪精确时刻，并加强固定 CAC 政策条款完整性。新小合同只使用已有 nullable 时间、unknown 精度、原文/metadata 与修订机制，无新 DTO、迁移或依赖。

**结论：Must fix M1。M2 按明确的新兼容合同关闭；M1 原末条正文洞已关闭，但“每条正文非空”在章节交界仍可被绕过。** 此意见只针对 `6dcce8b115ee3cb68bce814cf3f3ae91be9fcbf1`；不签整 R06、G-C、后续 polling/live 或原 T 整卡。

## 冻结范围和合同差异

- 同一非作者 reviewer `/root/r06_source_worker_combined_independent_review`，未参与任何修复实现。新干净 WT `D:/wt/r06-source-worker-review-1-recheck`、分支 `codex/r06-source-worker-review-1-recheck`；未在旧 b2bd 工作树改动。
- 基线 `b2bd53fd2320fc46f600ff0475298ec1b64b0172` → 冻结代码 `6dcce8b115ee3cb68bce814cf3f3ae91be9fcbf1`，7 文件、254 增/16 删：四产品 `catalog_pages.py`、`source_catalog.py`、`sources/osv.py`、`sources/github_releases.py`；两新增 boundary unit/PG 文件；`docs/decisions/CR-R06_source_timestamp_precision.md`。其它原 source worker/API/json budget 文件仍保持，当前完整运行字节 hash 与 checkout 过滤后的 Git 对象校验见 manifest。
- 沿用此前已读 AGENTS、执行地图、R06/原 T08/T11–T16、03/04/05/07、CR-R04-R03/04/06 和最新 ponytail-review，补读新小合同全文与全部 diff/直接测试/共同 caller。主库已有未提交状态/报告仍保留；本 reviewer 仅写自己报告和 run。
- 初审 M2 将三类输入均按 blocked 负例处理；新合同明确把**语法合法但不可无损表示的时间**改为保留 raw + NULL/unknown。真实录制 OSV 的 modified 确为 `2026-09-10T03:49:48.487641080Z`，不能为了维持旧拒绝策略删除该记录或伪造六位精确时间。
- 合同方向准确：非法 offset、日期、非 ASCII、非法 offset 秒仍失败；合法 `-00:00` 和超过六位小数不产生 instant，原值在响应/member payload/修订 metadata 中保持；原 NVD/vLLM 的已审严格策略未改。没有改变金标、holdout、评分阈值、总分母或 unknown 桶，本次未运行正式时延统计。
- 兼容与迁移边界：已有公开 nullable 时刻与 published_precision=unknown 可表示新结果；metadata/adapter 改为 catalog-pages-2，会使同原文的规则变化形成新修订，旧历史不覆盖。已读既有 save_document_revision 的末版内容+metadata 比较和只追加版本机制；本批无 schema 迁移，未另造历史数据库迁移演练。回滚只能停新采集、保留历史/游标，不能重新用已知错误旧时间发布当前结果。

## M1 仍须修复：下一章标题被当作上一条正文

位置：`backend/src/ai_intel/ingestion/catalog_pages.py:516–521`。

这是什么：新增逻辑要确保 24 条各有正文，并要求末条生效句处于末条范围。原末条删除负例已经通过；新的正文非空检测以“下一条 heading”为唯一终点，把位于两条之间的章节标题一起拼接。

实际输入：对原官方 HTML 分别去掉第四、八、十五、二十一条的全部正文，保留该条 heading 和紧接的下一章 heading，其余正文/最后生效句保持。复现函数 `policy_missing_body_before_chapter` 明确验证被删范围内没有下一条 heading；第八条实际完整变异输入为 `cac_missing_article_8_body.input.html`。

实际结果：四纯负例均未抛错，normalizer 返回 parsed/full_text；第八条真 PG worker 返回 succeeded，documents、document_revisions、source_cursors、source_page_receipts 各提交 1。`policy_chapter_observation.log` 另记录该缺正文输入仍 full_text。预期：章节标题不能满足本条正文非空，应 `SourceCatalogError` → blocked/source_response_invalid，本页资料、游标和回执 0 行。

根因：`:517–519` 直接拼接本条至下一条之间的全部 blocks，只移掉条号；第三章等章标题仍是非空 article_text。最小修复：正文边界同时识别下一章 heading，或明确排除章节标题；真正正文为空就隔离。保留原合法章节布局/所有条款和内联/跨块正文正例，不对原 HTML 改字。复验同四纯负例、第八条 PG 和原完整政策/末条负例。跳过修复会把缺正文的政策修订发布为当前全文并推进采集游标。

新独立 probes 的 5 个失败均属于这一具体缺陷；不把原泛回归通过当它关闭。root 已收到具体输入、行号、结果与最小修复方向，本 reviewer 未修改产品。

## M2 有依据关闭与原 probe 红例

四个共同来源链均核对：`_json_document` → arXiv/RSS/release/OSV；`parse_source_timestamp` 的其它生产 caller 是 GitHub release parser 与 OSV `_timestamp`，后者验证 published/modified/withdrawn。CBM 与完整 rg 记录为 `cbm_timestamp_trace.log`、`callers.log`，不是仅补 worker 特例。source_notes 追加有界精度说明，adapter2、raw 发布时间/修改时间及精度受修订版本保护；arXiv/RSS 既有规范时间仍兼容。原 NVD/vendor parser 未被此共享 helper 替换。

独立验证三种合法未知时间（-00:00、7 位、9 位小数）：纯转换保留原字符串、published=None、unknown、adapter2 和提示；OSV 与 release 共 6 个真 PG + 认证 HTTP GET 例均通过。每例原 response/member hash 明确不同、两对象 read_verified、source_response_hash/fetch_attempt 指向真实原 response，member 字段不丢 raw；双 /v1 与 /api/v1 GET 结果一致，nullable 時刻/unknown/raw/提示实际可见。

全部 OSV 例还使用未修改的真实 9 位 modified 原值，确认 source_modified_at=NULL、modified_at_raw 与 member payload 完整保持 `2026-09-10T03:49:48.487641080Z`。非法 +00:99、+24:00、坏日历、非 ASCII 和 offset 秒等独立负例实际通过，原无正文/非法 offset PG 0 写入例通过。

原 19 probes 从初审 WT **逐字节复制、不修改**，SHA256 `ba99307231353f4628dfce96f019633b7f3db0122dcc635de42071c7dc44cdf2`。本次原样复跑为 15 passed/4 failed：两纯例仍期待合法 unknown 被拒绝，因此 DID NOT RAISE；两旧 PG probe 在新 NULL 时间上调用 `.isoformat()`，产生 AttributeError。它们是旧策略/旧 non-null 观测假设与新合同不符的真实红例，原输出全部保留，未改 pass/skip。新增独立 raw/NULL/GET unknown 六例用于证明新合同，没有把原失败悄悄改绿。

## 独立命令、时刻与结果

环境：Windows / Python 3.12.13，自有 WT 运行 `uv sync --offline --frozen --extra semantic`，92 锁定包、无模型下载。正式 cwd 均 `D:/wt/r06-source-worker-review-1-recheck/backend`，python 为该目录 `.venv/Scripts/python.exe`；完整绝对 argv、开始/结束 +08、exit、JUnit 数量、产品 hash 和日志 hash在同名 JSON。run 根目录 `reports/runs/recovery_r06_source_worker_review_1_recheck_20261015/`。

| run / +08 时间 | 真实核心 argv | exit / 结果 |
|---|---|---|
| pure_frozen / 22:10:12–22:11:50 | `python -m pytest tests/unit tests/contract tests/security -m 'not real_pg' -q --tb=short --junitxml=… --cov-report=json:…` | 0；1788 passed、10 deselected、0 skip；74.52% ≥ 原 60% |
| pg_frozen / 22:10:13–22:12:06 | `python -m pytest tests/integration/test_r06_source_worker_pg.py tests/integration/test_r06_source_worker_api_pg.py tests/integration/test_r04_source_jobs_pg.py tests/integration/test_r06_source_boundary_pg.py --no-cov -q --tb=short --junitxml=…` | 0；96 passed、0 skip（原组合 91 + 新 boundary PG 5） |
| focused_unit / 22:13:28–22:13:30 | `python -m pytest tests/unit/test_r06_source_boundary_regressions.py --no-cov -q --tb=short --junitxml=…` | 0；28 passed |
| original_19_probes / 22:10:13–22:10:23 | `python -m pytest -c pyproject.toml <run>/test_independent_probes.py --no-cov -q --tb=short --junitxml=…` | 1；4 failed、15 passed、0 skip；旧策略红原样留档 |
| new_contract_probes / 22:13:28–22:13:44 | `python -m pytest -c pyproject.toml <run>/test_recheck_probes.py --no-cov -q --tb=short --junitxml=…` | 1；5 failed、14 passed、0 skip；其中 M2 六个 PG/HTTP 正例通过，M1 四纯+一PG失败 |
| static_ruff / 22:15:55–22:15:56 | `python -m ruff check` 四产品 + 两新增 boundary tests | 0 |
| static_format / 22:15:55–22:15:56 | `python -m ruff format --check` 同六文件 | 0；6 formatted |
| static_types / 同名 JSON | `python -m mypy src --cache-dir D:/tmp/dianzi-r06-review1-recheck-mypy-20261015` | 0；92 source files |
| product_diff_check / 22:15:55 | `git diff b2bd53f… 6dcce8b… --check` | 0 |

原回归 96 例含九来源/八类、原七源 raw/失败/partial/续页/恢复、原 HTTP 幂等与角色/CSRF/提交时变更、任务 ID 重放与原 NVD/vLLM 路径；只能据这次实际日志给新 SHA 背书。原 19 例中的真实留档 NIST 48 页、精确 CAC/AVID 和两个 raw hash 用例本次也通过，未复用旧 SHA 的通过结论。

PG 仅在进程内读取授权 WSL connection.json，替换为专库 `test_dianzi_r06_catalog_worker_20261015` 和 run ID `r06_catalog_worker_20261015`；每例新 UUID schema、schema 内 forward migrations 与 finally drop。所有 PG run public 前后均 `{table_names:[]}`；无 umbrella fixture、downgrade、共享/观察库修改、DSN/口令打印。已知 Starlette/httpx 弃用及外置 probes 导入时 pytest real_pg marker 注册顺序 warning 全保留，非失败根因，不变成 skip。

CBM 官方 v0.11 独立 cache `/tmp/dianzi-cbm-r06-source-worker-review-1-recheck-20261015`、项目 `r06-source-worker-review-1-recheck`；冻结 backend/src 的 92 文件、1234 nodes/6201 edges、0 skipped/partial，get_architecture/schema/trace 均 exit0。mypy/CBM cache 均仓外，产物清单不包含任何 __pycache__/.pyc/cache，未递归清理。

## 限制与交接

这是记录/合成 source 响应的 unit/contract/real-PG/本地 HTTP 验证，无新外网、模型、付费、DPAPI、浏览器或 scripts/PoC 执行；不计来源 live、持续监测、时延达标或正式分数。自动 polling、新集成 SHA 的全链/source live、正式统计桶与长期观测另审；旧审查仅为背景，不对后续版本自动生效。

当前复核状态 needs_changes（M1 仍阻断），M2 按本明确合同可关闭。下一建议：root 仅修章节标题误计正文，冻结新 SHA，原 reviewer 复跑同四纯/第八条 PG 红例与原合法章节/末条回归。新报告、probes、原输入、全部原始失败日志封存于自己的 run，未覆盖任何旧 run；未改业务/公共状态/锁/金标/阈值，未 push。日志尾 `E     ` 空白原样保持，未添加 ignore。

Verdict: Must fix M1；M2 closed under the explicit raw/NULL/unknown contract。
