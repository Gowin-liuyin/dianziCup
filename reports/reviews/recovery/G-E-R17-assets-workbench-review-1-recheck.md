# R17 / T42 资产工作台 · M01 fix1 定向复核

结论：M01 关闭；`Verdict: Ship.` 仅限已冻结资产清单前端切片的代码级放行。不签完整 R17/T42、G-E、accepted、backend integration/live/manual 或连续视频。状态登记仍由主控决定。报告时间：2026-10-16T06:51:02+08:00（Asia/Shanghai，实际系统时钟）。

这次修复把已确认的租户或请求对象范围违例作为资产工作区失效事件。范围错误到达时同步关闭私有有效性，清除并卸载目录、详情、历史、回执和 File/request 子树；普通 503 与普通 schema 故障仍能局部重试。

## 冻结与边界

非作者复核人仍为 `/root/r17_assets_workbench_first_independent_review`。新独立工作树 `D:/wt/r17-assets-review1-fix1`、分支 `codex/r17-assets-review1-fix1`，固定源码 `a25fd81c50f0ea14f44e7fda2c3edac5cab74d48`、材料 `f9f041056ac717c6be2287a4ad97058538adce66`。初审 worktree 和封存报告不修改；初审 M01 报告 SHA `f5f7a0282deab873b959ce669a1960112e5f77a741db3e8b85bea9715f66342a`。

复读本轮 AGENTS、00/R17 恢复卡、T42、03/05/06、冻结进度与 fix1 作者报告，沿用已读 ponytail-review 5.2.0、industrial-brutalist-ui 和真实后端合同。无新合同/角色/依赖决策。只新增本复核报告及 `reports/runs/recovery_r17_assets_review1_fix1_20261016/`；不改业务、原测试/fixture/API/schema/auth/锁、progress/gold/分母/accepted，不 push、不创建子 Agent。build 生成 tsbuildinfo 精确恢复到材料版本。

亲核 source diff：生产只改四份 owned 文件 `asset-contracts.ts`、`asset-client.ts`、`asset-workspace.tsx`、`asset-status.tsx`，另新增 `asset-scope.test.tsx`。原 447 对应测试/fixture 和原资产/图 Edge 文件字节不变。后端、shared api/auth、App/navigation/global CSS、锁、文档合同、progress/金标路径无差异。材料的 `.gitattributes` 只增加 fix1 精确 run 的 raw `-text`、`.log -diff` 和本 run `error-context.md -diff`；不扩大到业务或全局。

## M01 关闭证据

原触发行是工作区 failed 回调仅为 401/403 清除，以及详情仅为 404 清资源。fix1 在 `asset-contracts.ts:25–31,69,80` 保留公开 `502 invalid_response`，用本地 `AssetResponseScopeMismatch` 明确标识范围违例，不携带收到的私有标识。current/fixed/append receipt 请求 UUID 与返回 UUID 不一致经 client 同类传播。

`asset-workspace.tsx:25–35` 在失败回调内同步置 `privateScopeInvalidated.current=true`，既有所有异步流程共用的 isCurrent 立刻返回 false；随后清 list/currentAsset/receipt/filter/cursor/error/pending，并渲染 denied 错误区，使详情/历史/导入的既有 cleanup 卸载、abort 和清 request。这条同步守卫覆盖 React commit 之前的有效性窗口；业务代码没有新增万能层或共享认证改写。

原独立 probe 是完整字节副本，SHA `349b585720d400021385ada25c714ab262b52962e677e2547e83de13ca23205b`。本 reviewer 再在原冻结初审 dist 上执行，A/B 仍为名称残留 1/2，5 例 3 pass / 2 fail；旧红新 run 保留，不改预期。新固定 dist 上执行完全相同 probe：5 pass / 0 fail。A 后续目录 wrong tenant 和 B 固定历史 wrong tenant 均清除原私有名称；C 登出后的迟到 CSRF、D 同 bytes/key 重试及内容改变新 key/防双提交、E history 404 后迟到 current 保持通过。

另外自行新写 9 条独立真实 Edge dist/mouse 负例，全部通过；没有复用作者 controller 成功值：

| Case | 实际触发顺序 | 可观察结果 |
|---|---|---|
| L1 | 延迟 current → 目录下一页 wrong tenant → 释放 current | 名称/目录/快照/历史/File/receipt 均不能恢复 |
| L2 | 延迟首个目录请求 → 固定历史 wrong tenant → 释放目录 | 迟到目录不能恢复私有工作区 |
| L3 | 选真实 File 并提交 → 延迟 CSRF → 固定历史 wrong tenant → 释放 CSRF | File 移除，实际 import POST 数为 0，认证会话仍有退出按钮 |
| L4 | 原 File 实际 POST → 延迟 201 receipt → 固定历史 wrong tenant → 释放其它 asset receipt | POST 已真实发生 1 次，原 bytes 验证通过；不恢复回执、不跳新 asset、不声称后端回滚 |
| L5 | 选 File → 目录分页普通 503 → 正常重试 | 原资产仍可读、原 File 仍在、局部重试恢复、会话有效且没有 POST/logout |
| L6 | current 返回其它请求 asset UUID，DTO 本身同租户且内部关联一致 | 清目录/详情，标识范围错误 |
| L7 | fixed 返回其它请求 snapshot UUID，同租户/资产 | 清详情/历史/目录 |
| L8 | 正常选择追加 → 实际 POST → receipt 返回其它 asset UUID | 清 File 与工作区，无错误导航，query 的 append asset_id 仍为原资产 |
| L9 | fixed 返回同范围但 schema_version 无效 | 保留授权目录与局部固定快照重试，未伪称会话失效 |

所有清除场景都断言私有名称、目录/历史/快照标题、文件输入和成功回执为 0，localStorage/sessionStorage 为 0。实际截图、请求顺序、上传字节摘要表示和 URL 在 `late_artifacts/`；查看 L3 清除和 L5 对照截图，错误语义与视觉状态一致。作者新增 8 项 App/fetch 回归也作为本 reviewer 全量 455 的一部分真实执行，其中已有回执/File 清除和普通 schema 类型区分保持通过。没有把组件测试当作真实鼠标操作。

本轮未发现新的 Must/Should；没有风格偏好阻断。

## 独立命令与结果

npm cwd 都为 `D:/wt/r17-assets-review1-fix1/frontend`。每条命令的实际 +08:00 秒级起止、command/cwd/exit 在对应 `.command.json`。浏览器来自 self-created headless Edge，独占 `127.0.0.1:25719` 的 strictPort preview；读取实际 dist。

| 检查 | 实际命令 | 结果与日志 |
|---|---|---|
| 全量前端 | `npm test` | exit 0；35 files / 455 passed / 0 failed/skip；regression.log |
| 工程 | `npm run typecheck`、`npm run lint`、`npm run build` | 三项 exit 0；各 log / receipts |
| 原红反馈 | `npm run test:e2e -- --config ../reports/runs/recovery_r17_assets_review1_fix1_20261016/playwright.oldred.config.cjs` | exit 1；旧 dist 原五例 3 pass / 2 fail / 0 skip/flaky；edge_oldred.log / oldred_report.json |
| 原探针新绿 | 同前命令使用 `playwright.green.config.cjs` | exit 0；5 pass / 0 fail/skip/flaky；edge_green.log / green_report.json |
| 新独立迟到/对照 | 同前命令使用 `playwright.late.config.cjs` | exit 0；9 pass / 0 fail/skip/flaky；edge_late.log / late_report.json |
| 原资产 + 图 Edge | 同前命令使用 `playwright.baseline.config.cjs` | exit 0；资产6 + 原图6，共12 pass / 0 fail/skip/flaky；edge_baseline.log / baseline_report.json |
| 冻结 source/material 检查 | `git show --check --format=fuller a25fd81c50f0ea14f44e7fda2c3edac5cab74d48` / `f9f041056ac717c6be2287a4ad97058538adce66`，cwd 审查根 | 两项 exit 0；source_check.log / material_check.log |
| 原始字节亲核 | `python reports/runs/recovery_r17_assets_review1_fix1_20261016/audit_author.py`，cwd 审查根 | exit 0；原93 + 新95 全同；audit_author.log / author_byte_audit.json |

不把旧红的 3 pass 加到新绿，不累计作者和 reviewer 的重复测试。455 为原447 + 新8；12 为原资产6 + 原图6。原探针5、独立新9 和原12 是本轮不同 test cases。所有 API 路由均显式 synthetic intercept，数值和截图仅证明 UI/合同，不是后端/PG/live/e2e 产品全链路。

独立 CBM 在业务 diff 阅读前完成 full index/schema/architecture/AuthorizedAssets trace，项目 `r17_assets_review1_fix1_frontend_full_20261016`，路径 `/mnt/d/wt/r17-assets-review1-fix1/frontend/src`。四项 exit 0，690 nodes / 2734 edges，not_indexed/partial/unusable=0，36 callees / 3 callers。初审已证实 fast 排除 assets，故本次使用真实 full，并没有复用作者图或把 missing edge 当死代码；实际调用与同步 guard 另经源码核对。

新作者 raw manifest SHA `2e72d1ba9f571a83c55f3ea6d925d2859ac343245494cfcfdc4115f9be8c99b0`；95/95 项长度、作者工作字节、review 工作字节、冻结 material blob 和 review index 相同。原 raw manifest SHA `8c40f723ddc65f467a1c31ee8216c159f09607e56f7fbc1ebf23b242e70192e6`；原93与6db/f9/两个工作树/index 一致。五份新增/修改代码的规范化 Git LF 和 index 与 a25 一致；binary diff 与 business.diff.gz 解压字节同 SHA `709388e9c29b79405849823f1b865a3e9af9e77fb17036c8bc340d58f6755791`。原 probe、作者副本、本 reviewer 副本三份 SHA 相同；封存初审报告副本 SHA f5f7…相同。没有删改初版 type/Edge11of12/fasttrace/EOF 或本轮 red8(7失败)/oldred(2失败)证据。

本次报告 SHA、review raw manifest 与 index 字节证明在本 run `sealed_byte_proof.json`；原始日志保持字节。本 reviewer 的 `git diff --cached --check` 全 raw 为 exit 2，来自 CLI/error-context 原片段尾空格；报告/自身 probe/scripts 定向检查 exit 0，不关闭全局检查、不改 .gitattributes。

## 未检查与交接

真实后端/auth/PG 导入→current→history、live、FOFA/模型、人工标注、连续视频与原卡完整评估均 not_run。GET source_version 未公开保持未知，观察/四态/研判/重算/证据包/OpenVEX 仍禁用，不将其它 Agent 的 SBOM 或根默认 API 状态当本轮能力。原 T42 六案例与完整 R17/G-E 仍待独立验收。

F3/D2 证据只支持 M01 范围失效、迟到隔离和真实前端交互回归。对原审查范围的其余结论引用初审，不扩大这次定向审查。cleanup_receipt 记录本 run port/owned Node 归零；未触碰用户 CNNVD IAB、没有 kill 用户或其它 Agent PID，保留初审工作树和 raw。

下一建议：主控据本冻结 code/material/report hash 决定资产前端切片登记，并在默认后端接线独立放行后安排真实隔离 PG 联测；本 reviewer 不改 progress 或 accepted。

Verdict: Ship. 仅资产清单前端切片代码级；M01 closed。
