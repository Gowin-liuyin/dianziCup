# G-C · R06/R17 资料库前端独立审查 1

状态：**needs_changes，仅资料库前端内部切片**。结论：先修复 Must 1、2；不签 R06/R09/R17 整卡、原 T 卡或 G-C。本改动新增资料列表、固定原文修订的正文分页、历史选择和研究导航，沿用现有黑绿色工作台、认证和低亮动态背景。正常路径及既有回归通过，但两个可达的失败/版本变化路径尚不正确。

审查者未参与实现。独立工作树 `D:/wt/r06-doc-review1`，detached HEAD `475f71e48f93e9888dfcf09954a7ce13e590add5`；作者活动目录未作为审查输入。源码冻结 `aa17db32c314555363bb4bca3105c2b434939b29`，基线 `1ca2ea34c224e23776431fa6eac5fe6549d8c65f`。HEAD tree `1108ec12073af3d2c9aec055480ff48697a57586`；源码 tree `c8f918a996ff2f9ce7162c2bdcd67c27ea84a9dd`；两版本 frontend tree 均为 `19ebef43e580e694b3c71ef8c51bc14cf8e424d9`。

读取 AGENTS、execution map、R06/R17 卡、03/05/08 合同、认证变更、固定版本 task_state、作者设计/交接，以及实际后端合同。固定状态 R06/R17 均 in_progress/partial。使用 Ponytail 5.2 review/full；不重新扩大设计调研，用户 UI 文件仅为参考材料。范围仅 frontend 的 document DTO/client/workspace/nav/App/preparation 及测试；原 source 合同、认证实现和依赖未改。

## Must

1. **[P2] 历史读取被拒绝后，仍展示已经失效的正文和标题。** [document-workspace.tsx:92](D:/wt/r06-doc-review1/frontend/src/features/documents/document-workspace.tsx:92)，关联渲染 113、128、141 行。

   输入：先成功打开 `#documents/00000000-0000-4000-8000-000000000101`，取得标题和原文；点击「加载更多历史版本」后，`GET /v1/documents/{id}/revisions?offset=1&limit=20` 返回 403，或文档现已不可见而返回 404。实际：catch 仅把 history 置 failed，正文 resource 仍 loaded，旧标题、来源、正文和来源链接继续可见。403 文案同时写「未展示记录标题或数量」，404 文案写「没有展示缓存标题」，与实际页面冲突。

   影响：用户已收到当前权限/可见性拒绝，仍可阅读这个文档的旧投影；不能把已撤销的可见性当成仍有效。此处仅确认前端 fixture 失败路径，不声称真实后端发生过泄漏。合同要求每页重新校验可见性，作者设计和组件注释也承诺权限拒绝时不展示旧资料。

   最小修复：同一检视对象的 history 403/404 必须同时使正文资源失效并阻止未完成详情请求回写；503 等暂时错误仍可保留已取得正文并明确不完整。不要把所有错误改为空列表或撤销其他业务权限。

   复验：保留并跑独立 `review.test.ts` 的两个 history 负例、Edge `review.browser.spec.ts` 的两个同名负例；增加首轮 history 403/404 与晚到 detail 200 的交叉顺序，确认旧标题/正文/链接均不复活。现有单元 2 红、Edge 2 红，见 [independent_unit.json](../../runs/recovery_r06_document_workspace_review_1_20261015/independent_unit.json)、[independent_browser_final.json](../../runs/recovery_r06_document_workspace_review_1_20261015/independent_browser_final.json) 和同目录 screenshots/error-context。

2. **[P2] 当前版本在正文分页期间更新后，「查看当前版本」不能重读。** [document-workspace.tsx:117](D:/wt/r06-doc-review1/frontend/src/features/documents/document-workspace.tsx:117)，关联首次固定 revision 61 行及 Inspector key 194 行。

   输入：地址为 `#documents/{id}`，首读当前 revision 2；后台出现 revision 3。点击更多正文仍正确发送 `revision_id=revision2`，该页返回 revision 2 的 `is_current=false`，页面出现「查看当前版本 →」。实际：链接 href 还是当前同一个 hash；点击未产生新的当前版本 GET，selectedRevision 也未清空。Edge 点击前后当前 GET 次数均为 2（开发 StrictMode 首读两次），页面仍显示 revision 2 的历史标题/正文。

   影响：用户按页面提供的入口无法查看新版，需关闭详情再重新打开；固定修订分页的正确性不能替代返回当前版本的可用性。

   最小修复：该入口显式触发当前版本重读，重置 selectedRevision、offset 和已拼接的旧证据；不能只依赖 hashchange。无需增加新的业务路由或重做导航。

   复验：`review.browser.spec.ts` 的 current-link 用例保持点击前请求基线，使用合法 revision 3 响应；点击必须增加不带 revision_id 的 GET，出现新版标题与正文，然后后续页重新固定 revision 3。确认显式历史深链返回当前仍正常。当前 [current_link_confirmed.json](../../runs/recovery_r06_document_workspace_review_1_20261015/current_link_confirmed.json) 为 1 红，最终 5 例中的该项也为红。

没有确认的 Should/Nice 或 Lean 删除建议；缺测与猜测不另包装为缺陷。

## 真实检查与证据

运行目录 `D:/wt/r06-doc-review1/frontend`；Node 24.13.1 / npm 11.8.0。复用已安装依赖的 junction，未安装/变更依赖。自有日志根 `reports/runs/recovery_r06_document_workspace_review_1_20261015/`；全部下列检查的起止时间、命令和退出码在 `commands.jsonl`，最终验证窗口 2026-10-15 19:48–19:56 +08:00。

| 实际命令 | 实际结果 | 日志 |
|---|---|---|
| `npm test -- --reporter=json --outputFile=<review>/unit.json` | exit 0，295/295，20 文件，0 失败/skip | unit.json / unit.log |
| `npm run typecheck` | exit 0 | typecheck.log |
| `npm run lint` | exit 0 | lint.log |
| `npm run build` | exit 0 | build.log |
| `DIANZI_E2E_FRONTEND_URL=http://127.0.0.1:25491 playwright test --config=playwright.documents.config.ts --output=<review>/e2e_original_artifacts --reporter=json` | 实际 Edge，原 4/4，0 skip/flaky | e2e_original.json / .log |
| `vitest run --config=<review>/review.vitest.config.ts --reporter=json --outputFile=<review>/independent_unit.json` | exit 1，独立 36 例：34 过、2 红、0 skip | independent_unit.json / .log |
| `playwright test --config=<review>/review.playwright.config.ts --reporter=json --output=<review>/independent_browser_final_artifacts` | exit 1，独立 Edge 5 例：2 过、3 红、0 skip/flaky | independent_browser_final.json / .log |
| 同 config，`--grep='390px long title' --reporter=json --output=<review>/longtext_browser_artifacts` | exit 0，1/1 | longtext_browser.json / .log |
| `playwright test --config=<review>/native_cache.playwright.config.ts --reporter=json` | exit 0，1/1；无 page.route，真实 Edge 缓存启用、本地 HTTP fixture | native_cache_browser.json / .log / native_cache_http_requests.jsonl |
| 同 review config，`--grep='current link reloads' --reporter=json --output=<review>/current_link_confirmed_artifacts` | exit 1，合法 revision 3 响应条件下 1 红；重复确认 Must 2，不计新题数 | current_link_confirmed.json / .log |

原 4 例和新增 7 个独立浏览器场景均是显式隔离 fixture；没有产品 fixture fallback。按不同场景去重，新浏览器结果 4 过、3 红；重跑次数不扩大分母。原 4 例验证 1366/390、Enter/Space、检视焦点、历史选择、证据 offset、失败/空/metadata、401、退出晚到列表。新增通过：切换 revision 后晚到旧正文被丢弃；新会话及 reload 不恢复旧正文；390px 长标题 451 字符、source_name 300、license 244、source_notes 948、raw 日期 HTML 字符串均作为文本，script/img/svg 为 0、注入标志不存在，Range bounds 和全页 scrollWidth 无横溢出；active 装饰动画可见、pointer-events:none，reduced-motion 下动画均 none。

原生缓存例没有浏览器路由拦截。HTTP fixture 故意对资料返回 `Cache-Control: private, max-age=600`，真实请求仍带 `no-cache`；退出/换用户后服务端资料 GET 计数从 2 增至 4，新会话标题可见、旧标题为 0。这是本地合成 HTTP 传输/浏览器缓存证据，不是实际 PG/API integration 或来源 live 证据。路由拦截例不用于证明浏览器 HTTP 缓存。

独立 DTO 负例覆盖全部 14 个网关敏感 query key，另含大小写及百分号编码；canonical/license 的 HTTPS、userinfo、fragment、2083 可接受/2084 拒绝；Unicode code point 标题界限、source/title/license/raw 日期/notes 上限；缺字段、未知字段/枚举、schema/data_mode、非法日期/无时区、精确 offset、calendar_date 不能升级 instant；evidence 修订/模式/schema 与固定 revision 的负例。403/404 evidence 页清正文、503 history 页保留正文且明确不完整均通过。

实际查看原 desktop/mobile full-page PNG、history 403 失败 PNG、current-link 失败 PNG、long-injection-390 PNG。黑绿色层次、低亮拓扑、焦点、中文标签、日期未知和覆盖/风险边界延续已有设计；长文本断行，390 单列可读。失败截图中错误块旁旧正文仍可见，直接支持 Must 1。低亮装饰未重新改造；最终人工使用体验验收仍未执行。

## 合同、架构与字节核对

实际后端根 `D:/wt/r06-integration`：`CR-R04-R06_document_read_api.md` 与 `document_contracts.py` 对 `225c0fcd501d85d355513a44308083407b18bb2a` 内容核对。当前根的两文件按 CRLF 归一后均相同；Python DTO 原始 SHA256 `f4064848be483bcb7a5ca56b11b72b2d5267c1919ba475307253e67f42bd6050`。既有 EvidenceResponse 直接复用，不暗改 source DTO。时间值复用 UTC 合同，发布时间精度单独展示，URI 敏感集合与网关相同。

CBM 官方 WSL 二进制 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` 0.11.0；独立 `XDG_CACHE_HOME=/tmp/r06-document-workspace-review1-cbm`。仅索引 `/mnt/d/wt/r06-doc-review1/frontend/src` fast；288 节点/1074 边，19 个测试文件由工具 fast-pattern 排除；测试另行直接读取/运行。实际执行 help、index_repository、get_graph_schema、get_architecture、trace_path(fetchJson inbound depth1)、trace_path(DocumentInspector both depth2)，与 `rg` 调用方交叉。fetchJson 17 个直接调用方；DocumentInspector 指向 document client、统一错误/时间/证据组件，并由 DocumentWorkspace/Workbench 使用。图谱只作导航，结论以固定源码和复现为依据；无秘密/holdout 索引。日志 cbm_*.json / rg_callers.log。

`source_audit.json` 记录 Git blob 的原始字节/SHA256、工作树字节/SHA256、CRLF 数、范围与 commit/tree。14 个 frontend 差异文件对 aa17 源码按 CRLF 归一后全部相同。design 文档与 aa17 的差异为 475f 的已知冻结元数据，未当作业务源码变更。构建生成的 tsconfig.tsbuildinfo 已在自有 clean WT 还原固定版本，最终 tracked diff 为空。

`git diff --check 1ca2ea3 aa17db3 -- frontend docs/design/recovery/r06_document_workspace.md reports/tasks/R06-document-workspace.md` exit 0。整元数据包 diff-check exit 2，原因均见 whole_metadata_diff_check.log：原生失败 Playwright log/error-context 含行末空白；原日志不洗、不新增忽略规则。普通人工 Markdown/测试脚本无行末空格，CRLF 是正常行尾，不把它冒充 trailing whitespace。报告、原生证据和复制结果以 SHA256 检查，不用 PowerShell 文本重写 Git blob。

审查过程纠正记录：current-link 初测只断言绝对请求数 2，忽略 dev StrictMode 初始两次 GET，形成假绿；随后改为点击前基线增量，合法新版响应下真实复跑为红，未降低断言。首轮独立 JSON 被配置中固定 outputFile 在后续单例运行覆盖；首轮 2 红原生 log、PNG、error-context 均保留，最终完整 5 例 JSON 重新独立保存。被覆盖文件及 `current_link_initial_flawed.json` 仅作过程记录，不能计通过证据。第一次 Git tree 命令未引用 `HEAD^{tree}` 的 PowerShell 解析错误、错路径/rg glob 和一次摘要管道语法错误都不是业务测试结果；随后用正确引用/路径和 Python 原始 subprocess 重新核对。

## 边界、评分证据与交接

仅新增本报告和自有 run 目录；未修改业务/金标/阈值/分母/公共合同/progress/全局配置；未 commit、push、accepted 或 spawn。基线代码的其他工作台仅通过原 295 回归，不做整站重审。默认假设单个研究人员分页核查已保存公开资料；未进行多用户负载、性能评分或内存极限测试。

integration/live 均 **not_run**：新真实 GET、worker、真实来源→PG→资料→浏览器尚未在该审查版本接线；本地 HTTP fixture 不替代这些链路。真实认证/PG 权限撤销、持续采集、来源覆盖和 R09 知识卡、R16 重判、完整资产/图谱/推荐/报告/Agent 工作台、跨浏览器/原生 hidden-page 暂停、最终人工验收未查。没有由 fixture 推断实际攻击/泄漏、准确率、时效或性能数字。

限定证据映射：F1/R1 为分类、覆盖与日期精度；F2/F3 为指定 revision 原文/定位与真实失败状态；D2 为列表/历史/键盘/窄屏；E1 为严格 DTO、文本注入与会话隔离。Must 1、2 未修复，因此此切片当前不能有限 Ship；不把任何整评分项记通过。

下一步建议：作者在允许的 frontend 切片修复两个 Must 并保留红例；冻结新源码后由同一 reviewer 定向复验，再由主控真实接线后运行 PG/API/browser 及权限负例。未完成这些步骤前保持 needs_changes / 原整卡 partial。

结论：**needs_changes，先修 1、2。** 未查事项与真实接线缺口见上；没有额外批准或计划变更要求。
