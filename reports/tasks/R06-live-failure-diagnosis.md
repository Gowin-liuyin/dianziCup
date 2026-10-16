# R06 真实来源失败独立诊断

任务状态：awaiting_review；诊断 complete；产品实现 not_started。本报告不更新全局进度、不签 accepted。固定源码 `1156b2ed6616e3a4297215c2893d2cbe633f5215`，独立 detached 工作树 `D:/wt/r06-live-diagnosis-1156`。本轮只写本报告和 `reports/runs/recovery_r06_live_failure_diagnosis_20261015/**`；无业务代码、原测试、合同、依赖锁修改，无提交/push。

应用新版 Ponytail full 与 diagnosing-bugs；已读实际 AGENTS、00 执行索引、12 的 R06、03/04/05/06 合同、两个 R06 来源/时间决策和实际 worker 调用链。准备命令 `uv sync --offline --frozen --extra semantic` 在本 WT/backend 执行 exit 0、92 packages；使用独立 `.venv`，未复用共享环境。准备命令的精确起止时间未捕获，不补造时间。所有后续收据为实际 Asia/Shanghai 秒级 `+08:00`。

## 结论与原始输入身份

| 来源 | 可验证结论 | 输入与结果 |
|---|---|---|
| Ollama release | 两个来源调用误用模型 JSON 默认节点预算 | 额外受控官方 GET HTTP200，616207 bytes，SHA256 `972aa16090d1bbeae02a8deb2c32352ff77be894754e998e7a8c7555b031a5cf`；原 bytes 回放两次均 `RepositoryFetchError: invalid release JSON response` |
| AVID 第二页 | `screenshot` 的仓库相对图片引用被当成绝对 HTTP URL 拒绝 | 固定 tree/实际 offset1 的受控诊断重读；blob envelope HTTP200，2860 bytes，SHA256 `f8808b9479707e2b3ca074e569f9f678d692033c85767b387e15fbf31c3b246e`；两次回放均 `RepositoryFetchError: AVID reference URL is not public HTTP metadata` |
| arXiv 根 | 原 `source_response_invalid` 根因不可确定 | 原 worker 没有失败 HTTP/body/hash 记录；补充固定 GET 是 `NetworkRequestError`，没有 body，不能当成原解析失败复现 |

原 worker 失败 body 本轮没有取得。release 和 AVID 输入是独立受控诊断重读，有准确来源/hash；不是偷换原 worker 输入，也不覆盖历史。真实外部请求由 live agent 执行，共原授权 4 次（release、arXiv、固定 tree、固定 blob），本诊断 Agent 发出 0 次外部请求、0 次数据库调用、0 次模型调用、未读秘密。全量原响应留在仓外；本报告仅含 hash、结构和必要短字段。

准确外部路径、游标、HTTP Link 在 run 的 `official_response_manifest.json`。tree body SHA256 `0c04c3689ee1cd32714083b8e066c8f10c06439ebd2b0c7a10b9a2c4ecb4b5e5`，445091 bytes，Git tree `8eda5f4e6f74a3738eb980b795c4f813c6e52ca8`。AVID decoded payload 1871 bytes，SHA256 `b5c4be5ed298e38eba9cba4ae81d880b3968dafe52dfc14130b95266743b9819`，Git blob SHA1 `2571bc68a6be88cd93af9b31ca14eb85791828d4`。

## 1. Release：页级节点预算

实际调用：`source_jobs.collect_page:452` → `_fetch_catalog_page:381` → `normalize_catalog_page:604` → `_release_page:325` → `parse_github_releases:25` → `strict_json_object:36`。helper 默认 `maximum_nodes=10000`，数的是键和值等 JSON 节点，不是记录数。原响应是合法 20 条数组、24817 节点、最大深度6；不是超2MiB、非法 JSON 或坏单条。20 条逐条均通过；前8条9931节点通过、前9条11171节点失败。只在内存删 assets 时全页通过，此探针不能当产品修复。

最小修复：`sources/github_releases.py:25` 和 `catalog_pages.py:326` 两处调用都显式使用来源专用、有限 `maximum_nodes=50000`。已有 `strict_json_object` 支持该参数，无新依赖、无需修改模型默认或架构。只改第一处，第二处仍拒绝；局部内存探针改两处后，原 bytes + 真实 Link 归一20份文档，全部 parsed，next_cursor page2。该探针不是已实现产品代码或 live 通过。

必须保留原2MiB来源字节上限、深度32、有限节点上界、UTF8、重复键、NUL、非有限数、ID/URL/时间/记录数校验。50000仅为有界来源输入，不表示任意大合法页均自动接收；超界仍明确隔离。模型 helper 的10000默认和所有模型 caller 不变。受影响位置只有这两个 release caller；`_json_document`/JSON证据解析按单条继续处理，同源 Link 数字仓库别名已支持，无需再改。

正负用例：正常20条带资产元数据超过10000节点应归一并保留全部元数据和翻页；仅放宽第一caller应仍捕获第二caller失败；来源超过50000节点、过深、重复键/NUL/坏Unicode/NaN必须拒绝；模型10000默认继续拒绝。run 内已有显式合成红回归，不能复制原 release 全文进Git。

## 2. AVID：相对 screenshot 元数据

真实 worker 的 `SourceCursorRepository._lease_from_row:318` 通过 `_cursor_state` 剥离 PG cursor 包装，`collect_page:454` 传的是 `{tree_sha, record_offset}`。live agent 首轮把整个 PG 包装直接传给 `_fetch_catalog_page` 导致:331拒绝，只是诊断 harness 输入错误，已明确撤回；不能放宽游标来“修”原 worker。

正确 offset1 从 pinned tree 选择 `vulnerabilities/2023/AVID-2023-V027.json`。实际链：`_fetch_catalog_page:379` → `normalize_avid_blob:170` → `normalize_avid_vulnerability:118` → `_reference_identifier:65`。Git blob/envelope/decoded size 与身份校验先通过。唯一引用 `references[0].type="screenshot"`、`url="../img/R00031.png"`，label为str/28字符，不复制label正文。此字段是仓库图片上下文，不是绝对 HTTP URL。已保存的同一 pinned tree 确有 `reports/img/R00031.png`，Git blob `3e015be1724343d5e6e6a02350291e03f359b55d`、62176 bytes；仅核目录元数据，没有获取或读取图像。该相对引用从报告上下文保留到漏洞记录，不能按 vulnerabilities/2023 当前路径猜测URL或据此宣称看过截图。

当前 CommunityArticle 只输出 `referenced_advisory_ids`，类型/label/url的完整原值由 `normalize_avid_blob` 保留的原始 payload 和 JSON证据保存；HTTP envelope hash由现有 persistence链关联。相对图片不能产生 advisory ID，也不能产生CVEs、PoC成功或资产影响事实。

最小修复建议：在 AVID reference 分支，只认可 `type == "screenshot"` 且严格全匹配 `../img/R[0-9]{5}.png` 的已观察来源模式，作为 context-only 返回无 advisory ID；不解析为任意路径、不 fetch、不执行、不补HTTP scheme、不删除原引用。其余相对路径、未知类型、扩展名变化、额外父目录、查询/fragment、反斜线、百分号编码、控制字符、私网/凭据/不允许端口URL仍走现有拒绝。若后续源格式扩展，另取证，不静默放宽。

资料 source_notes 应说明存在仓库 screenshot 元数据、图片未读取；原 payload 和 HTTP hash保持。图片字段作为 JSON 文本证据不等于图像内容证据。必要时增加精确图片覆盖说明，不能把图像核查写成 full-text 图像阅读。只对已知上下文模式应用兼容，不将未知当已确认。

局部内存 regex 探针：原 decoded payload字节不变，AVID-2023-V027 parsed，advisory IDs空，nextoffset2；尚未在产品实现。合成正例应使用 screenshot，另加同路径 website类型负例、任意遍历/控制/编码/私网URL负例、Git身份/size失败回归。Caller只有 `normalize_avid_vulnerability`；blob完整性、AVID0.2/日期/稳定ID规则保持。

## 3. arXiv 证据缺口

已只扫描本run授权仓外161个对象：158 JSON、1PDF、1HTML、1RSS，全部 SHA匹配文件名，无 Atom signature。该结论限此run；不代表来源当时没有响应。补充GET的网络错误不能证明初次解析器根因，不能据此修改 URI、Atom时间、页语义或将失败改成功。最小所需输入是原失败或下一次受控固定请求的完整 bytes、MIME/status、hash和实际游标；取到后直接 `normalize_catalog_page("arxiv_security", body, actual_cursor)` 回放。本文未运行新的arXiv真实解析验收。

## 4. 独立审计缺口：解析失败前没有原文留存

这与arXiv初次根因缺输入分开。`_fetch_catalog_page:381` 先 normalize 才返回；`collect_page:460–471` 在返回后才调用 `register_response_content` 和 `record_fetch_attempt`。因此合法MIME/size已收取但解析拒绝的 body，根本未到保存阶段。纯离线实际handler观察：收到1个合成HTTP200坏JSON，捕获 `JobExecutionError(source_response_invalid, blocked=True)`，原文登记0、资料0；不是PG实测。原文留存时序不满足故障诊断/隔离证据需求。

最小独立行为修复路径（本兼容批不实现）：网关完成受控来源/size/MIME校验后，通过现有 ContentStorage 保存并校验不可变 bytes，随后解析；安全错误对象只携带固定 typed failure metadata（受控source kind/固定请求身份、aware观察时间、状态、hash、size、枚举MIME/错误码、最多两个AVID响应），不携带body、异常原文、Header、凭据或自由URL。响应身份从服务端来源/固定cursor生成，租户来自 context，不信任任务自报字段。

`workers/executor.py:55–74` 的 JobExecutionError 目前只有安全code/permanent/blocked/retry，不允许任意异常文本；可增可选、严格类型/长度的来源失败metadata。`execute_job:103–132` 回滚handler事务后，于:134的新失败事务内验证任务/来源权限和尝试围栏，复核已存hash/size，复用 `register_response_content` 登记content_objects并写failed fetch_attempt，与失败Job状态同事务提交；幂等键包含job/attempt/响应序号。executor注入原有可信store/受控来源失败记录器，旧非来源caller行为兼容，不用通用 arbitrary callback/任意URL插件。

现有 `SourceFetchFailure:150` 只支持HTTP400–599且没有hash，不能直接伪装HTTP200解析失败；现有content_objects/fetch_attempts已有hash外键，可复用，无需顺带改公共API或任意SQL接口。`register_response_content` 与GC共hash锁并做读回验证，`cleanup_unreferenced_object` 已保护 fetch_attempt response引用；需处理保存→rollback→新引用之间崩溃/GC竞态，不能把尚无PG引用的对象当已登记成功。未持久成功明确失败，不能伪造审计成功。

必须验证：失败原文可读回且hash一致；失败资料/事实/游标均未提交；AVID第二响应拒绝仍保留两响应身份；回滚后新事务才记录失败；重放/并发围栏/租户撤销/GC并发；没body的网络失败仍nullable hash；size/MIME/秘密元数据拒绝；日志/API不泄漏body或secret URL。真实PG/MinIO复验由后续独立小批执行，本轮未执行。

## 真实命令、结果与边界

全部检查cwd `D:/wt/r06-live-diagnosis-1156/backend`，Python为本WT `.venv/Scripts/python.exe`；完整argv、时间、退出码见run JSON收据。

| 检查 | 时间/退出 | 实际数量 |
|---|---|---|
| 官方bytes回放 `replay_originals.py official_response_manifest.json official_response_replay_1` | 23:07:44+08 / exit1 | release、AVID两预期失败 |
| 同输入回放 `_2` | 23:11:35+08 / exit1 | 同两失败一致 |
| `probe_release_structure.py` | 23:00:16–17+08 / exit0 | 20单条pass，8/9前缀界限；两来源预算探针20文档pass |
| `probe_avid_reference.py` | 23:11:11+08 / exit0 | 唯一引用失败；受限context内存探针pass，原payload保持 |
| pytest原source相关六文件 `--no-cov` | 23:03:47–52+08 / exit0 | 296 passed，1warning |
| pytest run内两份兼容合成tests `--no-cov` | 见final_check_commands / exit1 | 2 failed、20 passed（两个正常源正例精确红） |
| pytest失败留存时序观察 `--no-cov` | 见final_check_commands / exit0 | 1 passed（观察到当前缺口，不表示修复） |
| CBM v0.11 src-only index/schema/architecture/traces | 22:55:05–37+08 | 独立cache与project；93Python文件/1250节点/6296边；一次错误函数名trace exit1，纠正 `_fetch_catalog_page` 后exit0 |

原定向命令：`python -m pytest --no-cov -q tests/unit/test_r06_github_release_adapter.py tests/unit/test_r06_catalog_pages.py tests/unit/test_r06_source_boundary_regressions.py tests/unit/test_r06_feed_parsers.py tests/unit/test_r06_avid_record_adapter.py tests/unit/test_r06_source_worker.py --junitxml=<run>/existing_source_regression.xml`。

保留误差/失败：首个检查capture wrapper以UTF8读取Windows locale输出，UnicodeDecodeError继发TypeError，exit1；该包装错误不是产品失败。收据 `check_capture_failure.json` 精确时间未捕获；设置子进程PYTHONUTF8=1后复跑并保留原XML。首份合成负例错误期望ValueError而适配器实际合同为RepositoryFetchError，造成额外6失败；原7fail/1pass日志保留，纠正断言后1fail/7pass，再扩AVID得2fail/20pass。没有删难例或改金标。

验证：现有unit回归passed；新增兼容回归failed（预期红，产品未修）；原响应local replay复现passed；真实PG/网络/模型执行not_run；arXiv原bytes blocked；未跑全局coverage、全套类型/格式/前端/集成，无源码修改，不改全局门。

评分证据：E1/F1/R1对应来源解析兼容和原文故障可追溯证据；不声称八类live完成、时效指标达标、连续监测完成或整R06/G-C验收。既有CAC末条完整性和OSV未知时间精度策略没有变。

下一步：root指定唯一作者仅实现release两caller预算与AVID已知 screenshot context兼容，新增正负用例，再交全新未参与该批的Agent初审；另开失败原文保留小批；arXiv待有效bytes后诊断。本人结束本只读诊断后若转实现，不担任该批独立评审。
