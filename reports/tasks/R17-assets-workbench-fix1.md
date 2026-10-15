# R17 / T42 资产工作台 · M01 范围失配清理 fix1

状态 `awaiting_review`，仅申请原 reviewer 对 M01 定向复核；不签 accepted、完整 R17/T42、G-E、backend/live 或人工验收。报告时间：2026-10-16T06:41:27+08:00。源码 `a25fd81c50f0ea14f44e7fda2c3edac5cab74d48`，基底为原材料 `6db161e59e1c081d249b510ac441c93ad2fd295b`。工作树/分支仍为 `D:/wt/r17-assets-workbench` / `codex/r17-assets-workbench`，未 push、未改 progress/gold/分母。

独立初审 G-E-R17-assets-workbench-review-1 为 needs_changes，M01 一根因、A/B 两条失败输入。先确认其报告已 seal（SHA256 `f5f7a0282deab873b959ce669a1960112e5f77a741db3e8b85bea9715f66342a`），再复制原 probe 字节（SHA256 `349b585720d400021385ada25c714ab262b52962e677e2547e83de13ca23205b`），待 reviewer 释放 25719 后自行 strictPort 启动本人旧 dist 复现。原五例 3 pass / 2 fail：A wrong-tenant 目录下一页后旧私有名称仍 1 处；B wrong-tenant 固定历史后仍 2 处。A/B 的原 toHaveCount(0) 断言未改，红 JSON/log/synthetic observation 完整保留。原 447 与 12 绿不能抵销这两条红。

根因：合同/client 拒绝范围错误，却统一抛普通 invalid_response；workspace failed 只为 401/403 清数据，详情 404 只清对应资源。范围失配因此留在局部重试分支，保留目录/详情/历史/上传入口；同一 auth 代次的并发读取和导入也仍可认为自己有效。新增单元红同时证实旧代码释放迟到 CSRF 后实际发 POST、释放迟到 import 后导航到新资产，原样保留于 scope_unit_red。

修复范围只有四份 owned 生产文件和一份直属新测试：

| 文件 | 最小变化 |
|---|---|
| `features/assets/asset-contracts.ts` | 本地 AssetResponseScopeMismatch 标识已确认 tenant / 请求对象范围矛盾；沿用公开 502 invalid_response，无收到的私有 ID/value 属性，retryable=false |
| `asset-client.ts` | current/fixed snapshot/追加 receipt 的明确 requested-ID 违例传播同一类型；端点、DTO、fetch/CSRF/原 File 没有改协议 |
| `asset-workspace.tsx` | 范围失配同步关闭本私有工作区；失效 ref 纳入现有 isCurrent，清 list/currentAsset/receipt/error/filter/product/cursor/pending，移除详情/历史/导入子树并触发其既有 cleanup/abort |
| `asset-status.tsx` | 显示“会话范围不一致，已清除私有资产工作区”，保留重新核对会话的明确路径 |
| `asset-scope.test.tsx` | 8 个新的可观察范围/迟到/反例检查，原 fixtures 和原测试期待未动 |

详情、history、File/request 位于被卸载的既有子树：其现有 cleanup 清 File/request 引用并 abort controller；工作区同步失效 ref 在 React commit/cleanup 之前就屏蔽所有共享 isCurrent 调用，阻止迟到 current/list/history/CSRF/import 恢复数据或继续 POST/导航。客户端没有持久资产缓存，localStorage/sessionStorage 保持空。该边界不会伪称服务器已回滚此前已发出的 POST；已提交操作仍需核对后端实际记录。

普通 503 与普通 schema 无效仍是其原错误种类；503 保留已取得目录和可重试操作，不登出、不伪造 session_expired。会话由原 AuthProvider 管理；范围错误只关闭对应资产私有工作区。共享 auth/API、global CSS、后端、权限表、默认 App、锁、公共 schema 与原业务样例均未修改。

## 真实检查与原红

应用 diagnosing-bugs 反馈循环与已有 Ponytail full。修改前独立 full CBM `r17_assets_fix1_before_20261016`，在真实 frontend/src 完成 index/schema/architecture/trace 四项 exit 0；使用 full 是已确认 fast 排除 assets 的工具边界，未拿空图做判断。修复后独立 `r17_assets_fix1_final_20261016` 四项 exit 0，690 nodes / 2734 edges、not_indexed/partial/unusable 0；AuthorizedAssets 36 callees / 3 callers，确认范围类型与共享有效性守卫接在真实调用链。

所有 npm cwd 为本人 frontend；实际 +08 开始/结束与命令数组在 fix1 run 对应 `.command.json`。既有依赖 junction 复用，没有下载/安装或新依赖。以下 count 不合并重复运行：

| 检查 | 实际命令 / 日志 | 结果 |
|---|---|---|
| 原五独立 red | `npm run test:e2e -- --config ../reports/runs/recovery_r17_assets_workbench_fix1_20261016/playwright.independent.config.cjs`，phase=red；independent_red.log | exit 1，3 pass / 2 fail / 0 skip/flaky；旧 dist、原断言 |
| 原五独立 green | 同一 probe 与配置，phase=green；independent_green.log | exit 0，5 pass / 0 fail/skip/flaky；新 dist，原断言 |
| 新直属反馈 | `npm run test -- --run src/features/assets/asset-scope.test.tsx` | red exit 1：7 fail / 1 pass；green/final exit 0：8 pass / 0 fail/skip |
| 完整前端 | `npm run test`；regression_final.log | 06:39:50.743+08 至 06:40:27.024+08，exit 0，35 files / 455 pass / 0 fail/skip，原 447 + 新 8 |
| 原 Edge | `npm run test:e2e -- --config ../reports/runs/recovery_r17_assets_workbench_fix1_20261016/playwright.baseline.config.cjs`；edge_baseline.log | exit 0，12 pass（资产6+原图6），原文件/期望不变 |
| 新真实鼠标连动 | `npm run test:e2e -- --config ../reports/runs/recovery_r17_assets_workbench_fix1_20261016/playwright.late.config.cjs`；edge_late.log | exit 0，F/G 两例通过，0 fail/skip/flaky |
| 工程 | `npm run typecheck` / `lint` / `build` | 均 exit 0，对应原始 log 与 receipts |
| Git / 原材料 | source + staged diff check，seal_fix.mjs --source / --verify | 源码检查通过；原 93 raw 长度/hash/Git blob 无差异，原 fixture/期待与禁改路径差异为空；新材料字节比对见 git_byte_audit / raw_manifest |

8 个直属检查包括 typed scope 与普通 schema 类型区分、A 下一页、B 固定历史且清已存回执/File、范围失败后的迟到 current 和 list、迟到 CSRF 禁 POST、迟到已提交 import 禁回执/导航、普通 503 可读且会话仍有效。全部通过真实 App/Auth/fetch/解析/effect 路径，不注入业务成功。

真实 Edge headless 用实际 dist、请求截获、page.mouse.click；原 probe 的 C/D/E（登出后的迟到 CSRF、503 原字节/同键重试/新文件新键/防双提交、404 后迟到 current）同样通过。新 F 延迟 current，再触发目录 wrong tenant、释放 current 后所有名称/详情仍为 0；G 提交后延迟 CSRF，再触发固定历史 wrong tenant，File/名称/历史清除，释放 CSRF 不发 POST，进入会话仍可见退出按钮。原五 probe helper prelude 被复用于新 F/G，只新增测试输入/断言，原 independent.spec.cjs 完全未改。

浏览器 output 全入新 fix1 run，未覆写原作者或 reviewer 材料。所有截图/IO 都为明显 synthetic，无 backend/PG/FOFA/model/provider 调用。25719 为 reviewer 明确释放后本人新建的 strictPort preview，各 Playwright run 自己关闭 Edge contexts/webServer；最终 cleanup 记录自有 port/nodes 为 0，无用户 IAB 或其它 PID 操作。测试期间的诊断 cleanup 记录有一个本人 Vitest PID，保留在 cleanup_during_tests，不伪称当时已全部结束。

新 run 的 .gitattributes 只保留 raw bytes，终端 `.log` 与精确新 run `**/error-context.md` 不按源码 whitespace 处理；不会改写旧日志或扩大业务忽略规则。原 reviewer 报告与原 probe 在新 run 可按上述 SHA 对照。原 93 raw、原 447/12日志及其缺口继续保留。

backend integration/live/manual/连续视频仍 not_run；观察、四态、研判与导出仍未就绪，当前修复不新增此类能力，也不借其它后端 live。F3/D2 证据限定为 M01 的私有范围失效与真实 UI/并发回归，不能据此验收完整原卡或 G-E。

下一步仅由原新非作者 reviewer 固定本 source/material/rawmanifest 定向复核 M01，再由主控决定该资产切片放行。实现者不签 Must 已关闭或 Ship。
