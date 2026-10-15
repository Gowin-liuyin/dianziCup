# R06 · 真实来源兼容修复

状态 **awaiting_review**；本实施切片 complete，未独立评审、未签 accepted、未 push，不表示整R06或G-C通过。代码冻结 `e900cd6b95dde7c6fe8d11d8c15122eb48a4acdc`，基线 `1a52e17ffe327fb8a0c1d4f97372948a699910e3`；分支 `codex/r06-live-compat-fix`，工作树 `D:/wt/r06-live-compat-fix`。root已明确授权本地显式文件commit，唯一作者 `/root/r06_live_source_failure_diagnosis`，转实施后不担任本批独立评审。

本轮范围是release来源页预算和AVID screenshot上下文兼容，映射恢复R06及T08/T13/T16来源切片，E1/F1/R1。已核对实际AGENTS、00、12的R06/T映射、03合同和最新插件Ponytail full；复用固定1156只读诊断及296既有/22诊断用例证据。root派单描述的 `source_adapters/` 目录不存在，经rg和root确认以下实际路径，未猜建目录。

## 改动清单与输入输出

仅修改以下4个代码/测试文件；另外写本报告与 `reports/runs/recovery_r06_live_compat_fix_20261015/**`。

- `backend/src/ai_intel/ingestion/sources/github_releases.py`：来源专用 `MAX_RELEASE_JSON_NODES=50000`，第一JSON读取显式使用。
- `backend/src/ai_intel/ingestion/catalog_pages.py`：第二release JSON读取使用相同来源预算，wrapper字节上界明确对应原2MiB+10个包装字节；AVID资料保留截图引用并说明未读取图片，适配器版本 `catalog-pages-3`。
- `backend/src/ai_intel/ingestion/sources/avid_records.py`：精确识别 `type=screenshot`、全匹配 `../img/R[0-9]{5}.png` 的context-only引用，不赋advisory ID。
- `backend/tests/unit/test_r06_live_source_compatibility.py`：32个显式合成用例，包括正常大页、字段/游标保持、节点/字节/深度/坏JSON、模型默认、AVID原payload/版本/截图语义和非法引用。

禁止范围均未修改：公共schema、迁移、锁、模型JSON helper默认、source_jobs/runtime/executor、其他来源行为、全局进度/集成文档、金标/门槛/分母。未读真实秘密/holdout/答案/DPAPI/KEY，未运行PoC，0网络请求、0模型调用、0测绘调用、0PG调用，未改变任何服务/库/队列/用户。

## 实现行为与调用方影响

release响应保持原20条完整原字段、稳定ID、发布时刻和分页。两个caller必须一起修：`parse_github_releases`与`_release_page`均曾触发模型helper10000节点上界；现在只source caller显式请求50000。原2MiB body门、最大100记录、深度32、重复键、NaN/无限数、NUL、UTF8、非法ID/URL/时间及固定分页均保留。模型默认仍10000，不改generation、model clients或其他来源helper。

AVID先验证原Git blob身份、size和路径匹配，再归一0.2记录。仅已观察的repository screenshot模式作为文本上下文保留；不解析相对路径、不补HTTP scheme、不获取图片、不创建CVE/GHSA等advisory ID、不证明PoC/漏洞/资产影响。完整type/label/url和 `data_version=0.2` 仍在原payload/JSON证据中；Git tree/blob及HTTP源响应hash链未改。source_notes明确“未获取或读取图片”，新的AVID适配器规则版本为3，旧历史不覆盖。

同路径非 `screenshot`、额外父目录/遍历、查询/fragment、控制字符、反斜线、百分号编码、未知后缀、私网/带凭据/不允许端口URL继续拒绝。未来来源模式扩大需新证据；本批不把任意相对引用当合法URL。新规则应用于以后AVID归一，版本元数据变化可能形成新资料修订，沿既有末版metadata比较/历史链处理；这项PG行为仍待后续真实复验。

新增小predicate `is_avid_screenshot_reference`由AVID record validation和catalog资料说明共同使用，避免两套接受条件。调用方核查用 `callers_rg.log`、CBM source-only trace和实际源码交叉；没有新公共DTO或泛用service层。此前错误PG cursor包装harness诊断已撤回，actual worker先剥包装，游标代码没有放宽。

## 真实原样输入离线复验

全量原bytes只在既有仓外路径读取，不复制到Git；路径/固定游标/安全Link见run的 `official_response_manifest.json`。这些bytes由先前授权诊断GET取得，不能冒充本版本live采集。

| 来源 | 已验证输入 | 修复后输出 |
|---|---|---|
| release | 616207 bytes，SHA256 `972aa16090d1bbeae02a8deb2c32352ff77be894754e998e7a8c7555b031a5cf`；20条、24817节点/深度6 | 20文档，全parsed；原字段与响应数组逐条相等；next page2；risk仍not_assessed |
| AVID | envelope2860 bytes，SHA256 `f8808b9479707e2b3ca074e569f9f678d692033c85767b387e15fbf31c3b246e` | AVID-2023-V027 parsed；原payload字节相同；advisoryIDs空；adapter3/未读取图片notes；nextoffset2 |
| AVID identity | tree raw445091 bytes、SHA256 `0c04c3689ee1cd32714083b8e066c8f10c06439ebd2b0c7a10b9a2c4ecb4b5e5`；固定tree `8eda5f4e6f74a3738eb980b795c4f813c6e52ca8` | decoded1871 bytes，SHA256 `b5c4be5ed298e38eba9cba4ae81d880b3968dafe52dfc14130b95266743b9819`；Gitblob `2571bc68a6be88cd93af9b31ca14eb85791828d4`保持 |

原 `references[0]` type真实为screenshot，url为必要短字段 `../img/R00031.png`。已保存的pinned tree存在 `reports/img/R00031.png`，Gitblob `3e015be1724343d5e6e6a02350291e03f359b55d`/62176 bytes；只核目录元数据，未取图。引用从报告上下文留到漏洞记录，不能按当前漏洞文件位置猜图像URI。截图不是已阅读的证据内容。

`replay_official_sources.py` 两例全部passed，最终回放2026-10-15T23:30:47+08:00，exit0；原首次pass收据保存为 `official_replay_initial.json`。最终收据含三业务文件实际hash和无IO计数，供独立评审校验。

## 命令与验证状态

下表时间全部为2026-10-15实际Asia/Shanghai秒级 `+08:00`。检查cwd为本WT/backend；Python为本WT `.venv/Scripts/python.exe`。完整argv/cwd/start/end/exit见每个 `*_command.json`，原日志和JUnit均保留。

| 验收类 | 命令范围与实际结果 | 状态 |
|---|---|---|
| unit 新红例 | 23:24:38–42，`pytest --no-cov -q tests/unit/test_r06_live_source_compatibility.py`：2fail/30pass、0skip、exit1 | 红日志冻结；两个正常源正例失败 |
| unit 新绿例 | 23:26:16–17，同32用例：32pass、0fail/skip、exit0 | passed |
| unit 相关回归 | 23:28:14–20，原6份source unit文件+新增文件：328pass（原296+新32）、0fail/skip、1warning、exit0 | passed |
| contract | 23:28:14–16，repository_source_samples+archived_feed_replay：5pass、0fail/skip、exit0 | passed；既有留档离线合同 |
| security | 23:28:14–16，test_t08_network_and_sources：8pass、0fail/skip、exit0 | passed；注入式策略检查，无真实网络 |
| integration | 23:28:36–38，source_worker_pg+catalog_documents_pg：54 collected、0 executed、exit0 | **not_run**；本批未授权/配置PG执行，不读凭据，不将collect-only算pass |
| frontend/e2e | 不涉及前端或交互变更 | not_run |
| live/manual | 后续独立采集/PG/API/浏览器验收；本版本0网络/模型/测绘 | not_run |
| mypy | 23:28:36–48，`mypy src`：93源文件无问题、exit0 | passed |
| ruff/format/diff | 最终四变更文件lint、format --check、git diff --check均exit0 | passed |

相关unit实际完整argv：

```text
.venv/Scripts/python.exe -m pytest --no-cov -q tests/unit/test_r06_github_release_adapter.py tests/unit/test_r06_catalog_pages.py tests/unit/test_r06_source_boundary_regressions.py tests/unit/test_r06_feed_parsers.py tests/unit/test_r06_avid_record_adapter.py tests/unit/test_r06_source_worker.py tests/unit/test_r06_live_source_compatibility.py --junitxml=../reports/runs/recovery_r06_live_compat_fix_20261015/unit_regression.xml
```

复验不是降门：使用已授权定向--no-cov，未改任何全局coverage配置/门槛，未执行全套coverage。未新增skip或改既有测试预期。unit中的警告由实际日志记录，未隐藏。

首轮ruff指出catalog条件行103>100，exit1；仅换行修正后exit0。首轮format检查指出新test需格式化，exit1；formatter改一处构造调用换行后check0。红测试文件hash在 `red_tests_frozen.json`；格式化前后AST SHA相同（`test_format_only.json`），没有改变fixture/期望/用例。源码条件换行也无业务语义变化，原bytes最终又回放通过。所有首轮失败日志保留。

环境：`uv sync --offline --frozen --extra semantic` exit0，本WT独立venv/92 packages；准确时间和日志见environment_command/log。没有共享双路径venv复用。CBM v0.11采用新WT/src-only项目 `r06-live-compat-fix-1a52-src`，cache仓外 `/tmp/dianzi-cbm-r06-live-compat-fix-1a52-cache`；11项version/index/schema/architecture/真实函数trace全exit0，93Python文件、1250nodes/6285edges、无未索引项。不索引仓外原文/秘密/holdout。

## 评分、偏差、边界和交接

E1/F1/R1证据为两个已复现来源输入通过正确归一，及正常/非法边界保持。这里只完成R06兼容小批，不签八类live覆盖、正式时效/漏采统计、持续运行、整R06或G-C。CAC完整性和OSV未知时间精度原回归保持；没有绕开原验收条件。

arXiv原失败bytes未保存仍是缺口，补充请求网络错误不能确定原parser根因，未猜测或修改arXiv。失败body在normalizer前丢失的typed failure metadata/跨rollback留存设计在前一份独立诊断报告另列；本批未夹带executor/任务持久化变更。

代码commit2026-10-15T23:31:26+08:00，显式4文件、exit0；见code_add/code_commit日志。后续证据commit只含本批report/run，代码SHA仍上述e900cd6。独立审核人应核冻结SHA、原hash、有限源预算/模型默认、type+path交叉负界、原payload/截图未读取语义及调用方范围；本实现者不自审。

下一任务建议：全新未参与本批的Agent初审并复跑；root集成后在独立受控环境实测两个来源/PG/API/UI，明确正常页或隔离页状态。PG、live、截图内容、arXiv初次根因均未检查；未知来源变形仍会明确隔离。
