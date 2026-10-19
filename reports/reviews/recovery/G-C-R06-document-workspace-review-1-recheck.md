# G-C · R06/R17 资料库前端初审 1 定向复核

结论：**needs_changes**。初审 Must 1、2 的已报告路径均已修复，原样负例转绿；本轮相邻 READ_PUBLIC 权限负例确认新增 Must 3。仅评审资料 workspace 前端切片，不签 R06/R09/R17 整卡、原 T 卡、G-C 或真实接线验收。

审查者为原独立 reviewer，未参与作者修复。新 detached 工作树 `D:/wt/r06-doc-recheck1` 固定元数据 SHA `ef3a0583179a27ccdaca05b771afccc90429dc35`，源码 SHA `e492a8fb6b58465c60cf3b355caacbd077483967`；原审源码基线 `aa17db32c314555363bb4bca3105c2b434939b29`。HEAD tree `624cb3bd4baf6a195eac979c588913ae8eb4668b`；源码与 HEAD 的 frontend tree 同为 `1d621254af8cc2670407afc5d62f050744cc68f5`。只读固定版本及作者第二轮报告/diff，不审作者活动目录。

沿用初审 AGENTS、execution map、R06/R17、03/05/08 与后端 `225c0fc` 的实际 document read 合同；Ponytail 5.2 review/full 继续生效。固定状态 R06/R17 均 in_progress/partial。业务改动仅 document-workspace.tsx 与新增 document-recovery.test.tsx；共享 DTO、source 合同、认证、依赖、金标/阈值/分母未变。

## 初审两项结论

| 初审项 | 本轮结果 | 实际证据 |
|---|---|---|
| Must 1：history 403/404 后旧正文仍显示 | **关闭已报告路径** | 原样单元与 Edge 均通过；正文/history/catalog 清空；新增初轮拒绝与在途其他资源/目录晚到成功的四个并发负例也通过 |
| Must 2：当前版本分页变历史后，同 hash 链接不重读 | **关闭** | 原样 Edge 产生新的无 revision_id GET，显示合法 revision 3；新增单元继续加载时固定 revision 3，并没有旧版拼接正文 |

修复机制实读：Inspector 的 readGeneration/AbortController 集合使 detail/history 的 403/404 同时取消待完成读取并清状态，父目录代次阻止晚到目录恢复；当前链接显式重挂检视区并重读，不能只依赖 hashchange。503 后续页保留已取得部分原文及历史，并分别说明不完整；401 仍清身份，不形成 auth/me 恢复循环。

## Must 3 · 新确认的相邻权限路径

**[P2] 资料列表返回 READ_PUBLIC 403 后，在途详情/历史 200 仍可恢复正文。** [document-workspace.tsx:203](D:/wt/r06-doc-recheck1/frontend/src/features/documents/document-workspace.tsx:203)，具体 catch 205 行；关联 Inspector resource 渲染 135、163 行。

输入：已登录查看者直接打开 `#documents/00000000-0000-4000-8000-000000000101`；列表、详情与历史并发读取。`GET /v1/documents?limit=20` 先返回 403，另两个已发出的成功响应暂缓，随后返回 200。三个资料 GET 按冻结合同使用同一个 READ_PUBLIC 权限；此序列可表示权限读取时点不同的在途请求。

实际：列表 catch 只设列表 failed，403 不触发 Inspector 失效或卸载。晚到 detail/history 200 仍进入 loaded：左栏显示「没有资料查看权限」「未展示记录标题或数量」，右栏同时出现标题、来源地址、历史与原文。独立单元 1 红、实际 Edge 1 红；实际已看失败 PNG。此前 history/detail 发出的拒绝能清目录，但目录发出的同权限拒绝仍未清检视区。

影响：系统已经取得资料 READ_PUBLIC 拒绝，仍向用户展示同一资料读取流程的成功旧响应，错误文字与可见内容冲突。此处是确定的前端 fixture 失败路径；未声称真实 API 已发生数据泄漏。

最小修复：列表 403 同步清除/卸载当前检视区并取消其仍在途的 detail/history，晚到 200 不能恢复；可以复用现有资料代次/卸载机制，不扩大认证合同。保持列表 503、404 待接通等状态各自语义，不把所有错误统一为空。

复验：保留并运行 `catalog_privacy.test.ts` 与 `catalog_privacy.browser.spec.ts`；断言 403 后标题、source link、正文和历史控件为 0，待完成请求已取消，释放成功响应仍为 0。保持本轮 7 个并发/503/新版本分页负例、原 36/6、原 299/4 回归；补该路径 401 对照。修复前红日志在 `catalog_privacy_unit.json` / `catalog_privacy_browser.json`，截图 `catalog_privacy_browser_artifacts/.../catalog-403-late-body.png`，不删红例、不改为 skip。

## 真实复跑

工作目录 `D:/wt/r06-doc-recheck1/frontend`；Node 24.13.1 / npm 11.8.0，复用已安装依赖 junction，未安装/变更依赖。新日志根 `reports/runs/recovery_r06_document_workspace_review_1_recheck_20261015/`。实际时间窗口 2026-10-15 20:11:26–20:16:11 +08:00；逐命令真实起止与退出码在 `commands_*.jsonl`。以下 `<recheck>` 为该目录相对于 frontend 的路径。

| 实际命令 | 结果 | 日志 |
|---|---|---|
| `npm test -- --reporter=json --outputFile=<recheck>/unit.json` | exit 0，299/299、21 文件、0 失败/skip；含新增永久 4 例，不额外扩大分母 | unit.json / .log |
| `npm run typecheck`、`npm run lint`、`npm run build` | 全 exit 0，lint 无 warning | typecheck/lint/build.log |
| `vitest run --config=<recheck>/recheck.vitest.config.ts --reporter=json --outputFile=<recheck>/independent_unit.json` | exit 0，原样 36/36，0 skip | independent_unit.json / .log |
| `playwright test --config=<recheck>/recheck.playwright.config.ts --reporter=json`，独占 25495、msedge | exit 0，原样 6/6，0 skip/flaky | independent_browser.json / .log |
| `DIANZI_E2E_FRONTEND_URL=http://127.0.0.1:25496 playwright test --config=playwright.documents.config.ts --reporter=json --output=<recheck>/e2e_original_artifacts` | exit 0，原 4/4，0 skip/flaky | e2e_original.json / .log |
| `vitest run --config=<recheck>/recheck.race.vitest.config.ts --reporter=json --outputFile=<recheck>/race_unit_final.json` | exit 0，新增 7/7，0 skip | race_unit_final.json / .log |
| `playwright test --config=<recheck>/native_cache.playwright.config.ts --reporter=json`，msedge | exit 0，原样 HTTP fixture 1/1，无 page.route | native_cache_browser.json / .log / native_cache_http_requests.jsonl |
| `vitest run --config=<recheck>/catalog_privacy.vitest.config.ts --reporter=json --outputFile=<recheck>/catalog_privacy_unit.json` | exit 1，新增权限路径 1 红 | catalog_privacy_unit.json / .log |
| `playwright test --config=<recheck>/catalog_privacy.playwright.config.ts --reporter=json`，独占 25497、msedge | exit 1，同权限路径 Edge 1 红，0 skip/flaky | catalog_privacy_browser.json / .log / artifacts |

补充 7 例验证：初轮 detail 或 history 403/404 时另一个资源及目录延迟成功不会恢复；当前仍在途两请求确实被取消；初轮 history 401 清身份，晚到正文/目录无复活且 auth/me 只一次；同时 history/evidence 503 保留部分正文与两个明确不完整说明；同 hash 重读后正文页固定新 revision 3。没有把暂时失败改成权限失效或空结果。

所有浏览器均为真实本机 Edge 进程，实际 fixture 明示，不计 live。原样 6 与原 4 包括加载、空、metadata、401、退出晚到、跨 session 重登/reload、历史选择、正文分页、Enter/Space、焦点、1366/390、长文本注入/Range bounds 无横溢出、active 背景 pointer-events:none 和 reduced-motion 静态降级。已实际查看修复后的 history 403、revision 3、390 历史页及新增 catalog 403 失败 PNG。截图旧名称含 stale 来自原用例，不表示原两 Must 仍失败。

HTTP fixture 未使用 page.route，浏览器缓存启用；资料故意返回 `private,max-age=600`，跨会话服务端真实 GET 计数仍 2→4，新资料可见、旧资料不恢复。该证据只证明此浏览器/本地合成 HTTP 的 no-store 行为，不替代真实 PG/API 会话或来源链路。

## 输入与源码完整性

从原初审 run 目录原样复制断言/fixture；仅新 config 改 include、cwd、端口与输出。初末哈希在 input_hashes.jsonl / source_audit.json：

- `review.test.ts`：`aa85efb493e10b02beb0f8037581cb1426d02c6e8e175b14cb9914b70a314749`。
- `review.browser.spec.ts`：`e79bc1c9034770e4cfd30b81598d390eb910bd67875b086adad84c426cbae13e`。
- native cache test/HTTP fixture 也逐字节相同。原初审报告 SHA256 仍为 `9c1824aaed8dc8c33e8051a875af4e7fce2e6fed67b06846104121b4fcd4600b`，未修改。

`source_audit.json` 保留两个修复源码的 Git blob 原始字节/SHA256、工作树 SHA256、CRLF 数、commit/tree、范围和输入哈希。源码按正常 CRLF 归一后全部相同；构建生成的 tsconfig.tsbuildinfo 已仅在自有 clean WT 还原冻结字节，最终 tracked diff 为空。源码/人工文档 `git diff --check aa17db32 e492a8f -- frontend docs/design/recovery/r06_document_workspace.md reports/tasks/R06-document-workspace.md` 和对 ef3 对应检查均 exit 0。原生日志/error-context 行末空白完整保留，不洗日志、不新增忽略规则；人工报告/脚本按普通行尾规则核对。

CBM 官方 WSL `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` 0.11.0，独立 cache `/tmp/r06-document-workspace-recheck1-cbm`；只索引新 SHA 的 `/mnt/d/wt/r06-doc-recheck1/frontend/src` fast，289 节点/1077 边，20 个测试文件由工具排除，测试另行直接读取运行。实际重新 index、schema、architecture、DocumentInspector both/depth2 trace，与 rg 全部 caller 交叉；调用链仍为 Workbench→DocumentWorkspace→DocumentInspector→document client，新增回调只在该模块流转。日志 cbm_*.json / rg_callers.log；未索引秘密或 holdout，不用图谱替代实际断言。

本轮自有新并发测试初次 7 中 3 过/4 红：误将已完成的拒绝响应也断言为 aborted，而 fetchJson 已正确解除其外层 abort listener。修正为只核对仍等待 barrier 的两请求，并继续释放已取消请求的成功响应检查 UI；最终 7/7。初轮原生 race_unit.json/.log 保留，不把测试断言错误记为业务缺陷，不计新场景数；原样 36/6 文件从未修改。

## 边界与交接

仅新增本复核报告及新自有 run 目录；无业务/合同/状态/金标/阈值/分母/全局配置修改，无 commit/push/accepted/spawn。已有两项关闭记录不覆盖原初审红证据，新增 Must 3 独立记录。

真实新 GET、worker、PG/API/browser 来源链路尚未接线，integration/live **not_run**。未查真实权限撤销、持续采集、性能/多用户负载、其他浏览器、原生 hidden-page 暂停、R09/R16 和完整 R17 业务、最终人工验收。没有由 fixture 推断实际泄漏、覆盖、准确率、时效或评分通过。

F1/R1 分类/覆盖/日期、F2/F3 revision/永久定位、D2 中文窄屏/键盘、E1 strict DTO/文本/会话的初审限定证据仍保留；当前新增权限失败使资料接口切片仍不能有限 Ship。不签整评分项或阶段。

下一步：作者仅补列表 403 到检视区的失效/取消路径，保留本轮两个红用例，冻结新源码后定向复验；之后主控真实接线与独立集成验收。**结论：原 Must 1、2 关闭，新增 Must 3 先修；needs_changes。**
