# G-C · R06/R17 资料 workspace 初审 1 第三轮定向复核

结论：**有限 Ship，仅本资料 workspace 前端接口与已报告 Must 的修复范围。Must 3 关闭；Must 1、2 保持关闭。** 未发现新的、经本轮实际负例确认的阻塞缺陷。此结论不签 R06/R09/R17 整卡、原 T 卡、G-C、真实 API/browser/live 或最终人工验收，不自行写 accepted。

原独立 reviewer，新 detached 工作树 `D:/wt/r06-doc-recheck2`；元数据冻结 `0a8a3b826cf47185e8de5af555948dfedb2bc3f0`，源码冻结 `2f5c7ef225ce2d29da2438a4d5caa51cdc6a9231`，基线 `ef3a0583179a27ccdaca05b771afccc90429dc35`。HEAD tree `e330daad1b5a3971371d4470bb24e4d3ad4a187e`；源码与 HEAD frontend tree 均为 `3ae0832fc0905e1bb71dcea72a67ce9a09ad42cf`。不审作者活动目录，未参与业务修复。

沿用 AGENTS、execution map、R06/R17、03/05/08、既有认证及 `225c0fc` 的 document read 合同，读取固定版本第三轮报告与实际 diff。Ponytail 5.2 review/full 继续使用；没有扩大 UI 设计调研。固定 task_state 中 R06/R17 仍 in_progress/partial。

## Must 3 的关闭证据

问题原为：列表 READ_PUBLIC 403 先返回，仍在途的 detail/history 200 晚到后恢复原标题、来源链接、历史和正文。新实现将原私有 generation/controllers 移到 DocumentWorkspace 的单个资料读取 scope；list/detail/history 使用共同的取消代次。列表 403/401 同步提升代次、取消资料请求并卸载 Inspector；搜索、下一页、回第一页和重试同样取消旧查询 scope，当前版本重读保留明确的新读入口。没有引入全局 store、框架或新身份合同。

原有效 `catalog_privacy.test.ts` 完全原样，**1/1 通过**，晚到成功不恢复正文。独立修正 Edge 探针在 403 deep-link、401 deep-link、搜索后 403、下一页 403、503 后重试取得 403 五个场景中实际观察 `started=4 / settled=4 / cancelled=4`（开发 StrictMode 实际两次各资源请求）；释放全部 barrier 并等待 handler 结束及浏览器帧后，标题、原文、source URL、历史控件和详情 DOM 均为 0。503 对照允许合法详情返回，保留「仅摘要/未保存完整正文」，没有伪造本页零记录。

同一修正探针在独立旧 WT `D:/wt/r06-doc-recheck1`、确认 HEAD 为 ef3 的前端服务上跑 403 deep-link：**exit 1，1 红**；取消仅 2/4，释放并 settled 后原标题仍为 1。它能检出旧缺陷，也能验证新版本，不是删除失败条件后形成的假绿。日志 `corrected_probe_before_fix_final.json/.log`。

原两 Must 没有重开：原样 6 个 Edge 和 36 个单元转绿仍成立；原样 7 个并发/503/当前版本绑定单元通过。同 hash 当前重读获取合法 revision 3，旧证据不拼接，后续页继续固定新 revision；history/detail 403/404 清缓存及晚到响应隔离仍通过。

## 修正 reviewer 自有 Edge 探针

我上一轮的 `catalog_privacy.browser.spec.ts` 在 release 后先 `await 漏洞原文.toBeVisible()`，然后断言 count 0。这个前置只适合修前泄漏复现，正确修后正文永不出现，会在前置超时，不能用来判定产品未修。它是 reviewer 测试设计错误，不是作者修复失败。

原文件、hash、修前红 JSON/log/PNG/error-context 均保留，未让作者修改独立断言。原文件本轮再次原样执行，**exit 1，1 项前置 toBeVisible 超时**，结果明确归类仪器失败，不计产品失败或通过、没有改成 skip。旧 hash 为 `092bedcad878acbe66428c6a8ab2e5851318c573b40e8b5a54c0b3ce3bc1734b`。

另建 `catalog_privacy.corrected.browser.spec.ts`，不等待漏洞正文出现：记录实际在途/取消数，释放响应、等 handler settled，再直接断言无标题/正文/source URL/历史。网络取消使用 soft 断言仅为让旧版继续执行可见性检查；任何 soft 失败仍使整项失败，没有降低通过条件。新旧完整文本差异在 `legacy_corrected_probe.diff`；该 diff 的 exit 1 表示文件有差异，不是业务测试失败。新探针 SHA256 `4d7eb2ff38a94fae9cf410f25066bedadf70304329825f9306b5c4981fb6db65`。

## 真实复跑

工作目录 `D:/wt/r06-doc-recheck2/frontend`；Node 24.13.1 / npm 11.8.0，既有 node_modules junction，未装/改依赖。日志根 `reports/runs/recovery_r06_document_workspace_review_1_recheck2_20261015/`；真实检查时间窗 2026-10-15 20:40:26–20:51:15 +08:00，逐命令起止/exit 见 `commands_*.jsonl`。下表 `<recheck2>` 指该目录相对于 frontend 的路径。

| 实际命令 | 结果 | 日志 |
|---|---|---|
| `npm test -- --reporter=json --outputFile=<recheck2>/unit.json` | exit 0，305/305、22 文件、0 skip；原 299 保留加永久 6，未另加到分母 | unit.json / .log |
| `npm run typecheck`、`npm run lint`、`npm run build` | 全 exit 0，lint 无 warning | typecheck/lint/build.log |
| `vitest run --config=<recheck2>/recheck.vitest.config.ts --reporter=json --outputFile=<recheck2>/independent_unit.json` | exit 0，原样 36+7+1 = 44/44，0 skip | independent_unit.json / .log |
| `playwright test --config=<recheck2>/recheck.playwright.config.ts --reporter=json`，msedge、25501 | exit 0，原样独立 6/6，0 skip/flaky | independent_browser.json / .log |
| `DIANZI_E2E_FRONTEND_URL=http://127.0.0.1:25503 playwright test --config=playwright.documents.config.ts --reporter=json --output=<recheck2>/e2e_permanent_artifacts` | exit 0，原 4+永久 4 = 8/8，0 skip/flaky | e2e_permanent.json / .log |
| `playwright test --config=<recheck2>/corrected_probe.playwright.config.ts --reporter=json`，msedge、25504 | 最终 exit 0，独立修正 6/6，0 skip/flaky | corrected_probe_final_retry.json / .log |
| `playwright test --config=<recheck2>/corrected_probe_before_fix.playwright.config.ts --grep='403/deep_link' --reporter=json`，msedge、25505、旧 ef3 服务 | exit 1，探针有效性对照 1 红，不计当前版本缺陷 | corrected_probe_before_fix_final.json / .log |
| `playwright test --config=<recheck2>/legacy_probe.playwright.config.ts --reporter=json`，msedge、25502 | exit 1，原探针前置超时；仪器失败，非当前产品红例 | legacy_probe_after_fix.json / .log |
| `playwright test --config=<recheck2>/native_cache.playwright.config.ts --reporter=json`，msedge、无 page.route | exit 0，原样 HTTP fixture 1/1 | native_cache_browser.json / .log / native_cache_http_requests.jsonl |

原 36/7/1 单元、原 6 Edge 与 HTTP fixture 测试文件字节未动，输入初末 hash 在 `input_hashes.jsonl / source_audit.json`：review.test.ts=`aa85efb493e10b02beb0f8037581cb1426d02c6e8e175b14cb9914b70a314749`；review.browser.spec.ts=`e79bc1c9034770e4cfd30b81598d390eb910bd67875b086adad84c426cbae13e`；recheck.race.test.ts=`c77c4767106618dc02198a0fc82c9ad3095456f688ac1168ee976e7811b52fb1`；catalog_privacy.test.ts=`e1df2ef900bf6a277b381b0781d56359259d670a5906a88b3761d7a434a763ab`。只改自有 config 的 include/cwd/端口/输出，原初审与前次报告未改。

验证覆盖：deep-link 权限/401、目录晚到、搜索/分页/回首页/重试取消路径；实际浏览器 requestfailed 与释放成功响应后的不可见；503 目录与正文/历史 partial 分开；strict DTO、日期精度、URI/敏感 query、revision/data_mode 绑定；换会话、换版本后晚到响应；当前重读和新 revision 分页；加载/空/metadata；Enter/Space、焦点、1366/390、长文本注入/Range bounds/无横溢出、低亮背景 pointer-events:none 与 reduced-motion。原样与永久回归重复场景不累计为新场景数。

全部浏览器是真实 Edge 进程，但 API 响应是明确的隔离 fixture。另一个 HTTP fixture 未使用 page.route，浏览器缓存启用；服务故意给资料 `private,max-age=600`，换会话仍产生服务端 GET 2→4，旧资料不恢复。均不是实际 PG/来源/live 证据。实际查看独立修正 403/401 PNG，403 后仅通用核查提示，401 后仅匿名/失效状态；原样截图及永久窄屏/历史/重读证据也留存，不以作者截图替代本轮复跑。

## 架构、字节与范围

CBM 官方 WSL `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` 0.11.0；独立 cache `/tmp/r06-document-workspace-recheck2-cbm`。仅索引新 SHA 的 `/mnt/d/wt/r06-doc-recheck2/frontend/src` fast，292 节点/1090 边，21 个测试文件由工具排除，测试另读另跑。实际 index/schema/architecture/cancelDocumentReads both-depth2 trace，并用 rg 全调用方交叉；取消 scope 保留在该资料模块内，未变全局认证。日志 cbm_*.json / rg_callers.log。未索引秘密/holdout，不把图谱当验证结果。

四个 frontend 差异文件：document-workspace.tsx、document-scope.test.tsx、r06_document_scope_fixture.spec.ts、playwright.documents.config.ts；其 Git blob 原始字节/SHA256、工作树字节/SHA256与 CRLF 数在 source_audit.json，按普通 CRLF 归一后均与 2f5 源码相同。构建 tsconfig.tsbuildinfo 只在自有 WT 还原冻结字节，最终 tracked diff 为空。`git diff --check ef3a058 2f5c7ef -- frontend docs/design/recovery/r06_document_workspace.md reports/tasks/R06-document-workspace.md` 及对 0a8 对应检查均 exit 0。人工 Markdown/脚本无 trailing whitespace；原生失败 log/error-context 保持原始空白/ANSI/行尾，不洗日志、不增加忽略规则。

旧前次报告 SHA256 仍 `7750eecf506c652bfccb52133016c14697026cbd22213ad71c7c283d6d36a96b`。本轮仅新增报告与新自有 run，未改业务/状态/合同/认证/依赖/金标/阈值/分母/全局配置，无 commit/push/accepted/spawn。

## 缺测、评分边界与交接

本轮真实集成 API/browser 与 worker/来源链仍 **integration/live=not_run**，待主控后端装配；不等待也不代签其他独立后端审查。未查真实权限撤销/持续采集、跨浏览器、原生 hidden-page 暂停、性能/多用户负载、R09/R16 与完整 R17 业务及最终人工体验。没有由 fixture 推断实际泄漏、覆盖、准确率、时效或整评分项通过。

F1/R1 的分类/覆盖/日期、F2/F3 的 revision/定位、D2 的界面/键盘/窄屏、E1 的严格类型/文本与会话隔离，只保留此前与本轮限定前端证据。已关闭的三 Must 与本 workspace UI 可有限 Ship；整 R06/R17、G-C 及实际功能链验收继续由主控按真实证据推进。

下一步建议：集成该冻结前端与经过独立审查的真实 API 后，使用真实授权会话复跑资料列表→历史→正文→新版本→权限撤销/退出→窄屏链路。**结论：Must 3 关闭，原 Must 1、2 保持关闭；有限 Ship，仅上述前端切片。**
