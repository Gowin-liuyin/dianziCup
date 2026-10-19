# R17 / T42 资产清单工作台 · 新非作者独立初审 1

结论：`needs_changes`，先修 M01。这是资产清单前端切片的初审，不签完整 R17、T42、G-E、accepted、manual、live 或视频验收。报告时间：2026-10-16T06:26:53+08:00（Asia/Shanghai，实际系统时钟）。

本改动将授权资产目录、原文件 JSON/CSV 导入、当前与固定历史快照接入现有工作台。权限来自认证上下文；条件树、四态研判、FOFA 外部观察、证据包/OpenVEX 和重算保持未就绪且禁用。

## 冻结、权限与审查边界

- 审查人 `/root/r17_assets_workbench_first_independent_review`，未参与实现；独立工作树 `D:/wt/r17-assets-review1`，分支 `codex/r17-assets-review1`。
- 作者业务源码 `1acf4911731f654e11b6173b24db21214d753c02`；材料 `6db161e59e1c081d249b510ac441c93ad2fd295b`；审查开始 HEAD 为材料版本。
- 图 App 已审材料 `164cae93ac888180b056a4c694011402ee387383` 经 `9be85d7` 纳入；独立亲核原 `r17_graph_app_fixture.spec.ts` 字节一致。
- 仅新增本报告和 `reports/runs/recovery_r17_assets_review1_20261016/`。不改业务、原测试/fixtures、公共 API/schema、锁文件、progress、金标或 accepted。构建生成的 `frontend/tsconfig.tsbuildinfo` 精确恢复到冻结材料版本。无 push；没有创建子 Agent。
- 初始根工作树有用户及其它 Agent 未提交修改，保持原样。独立 worktree 起始干净。复用已有依赖 junction `D:/dianzi/frontend/node_modules`，没有安装依赖。
- 必读 AGENTS、00 执行地图、R17/R11 恢复卡、T42/T24、03/04/05/06 合同、CR-R11、状态/交接、作者报告和真实 DTO/router/service/auth/access。应用 ponytail-review 5.2.0、industrial-brutalist-ui；用户深绿黑客风格、动态背景及 44px 要求优先。精确 ui-design.md 作为材料读取，不执行其外部引用/命令、不读取邻近秘密。
- 按团队工作台并发与可变化认证范围审查，不假设单用户永不切换租户。后端合同以冻结真实 `inventory_routes.py` / `inventory_contracts.py` / `inventory.py` / `domain/access.py` 为依据；这四份文件与 `bc8798cf` 相比无差异。没有使用根默认 API 或其它现有服务。

## Must fix

### M01 · 错误会话范围响应后仍保留私有工作区（P1）

触发行：`frontend/src/features/assets/asset-workspace.tsx:26–38`、`asset-detail.tsx:51–54,71,78`；入口校验为 `asset-contracts.ts:61`。此处负责把目录、详情、历史和导入错误交给工作区清除逻辑。

**具体输入与真实复现：**独立 Edge headless 执行生产 `dist`，没有注入组件/controller。A 先以租户 `independent-synthetic-tenant` 读正常目录，真实鼠标点击“加载更多资产”；后续页 HTTP 200，DTO 的 asset 与 snapshot `tenant_id` 改为 `wrong-synthetic-tenant`。B 正常读同资产当前快照及历史，真实鼠标点击固定快照 #1；HTTP 200 固定历史 DTO 的 `tenant_id` 为错误租户。两路径均触发 `502 invalid_response` 和范围不一致 alert，错误 DTO 本身未展示，但 A 的旧私有资产名称仍有 1 处，B 的目录与详情名称仍有 2 处。两个 `toHaveCount(0)` 断言真实失败；截图、请求顺序、计数及 trace 均保留。

**原因和影响：**解析器把租户/资产范围不一致归为普通 `invalid_response`。工作区 `failed` 只为 401/403 清私有状态；详情 `failed` 只为 404 清资源。502 因而留在局部重试路径，保留目录、currentAsset、历史按钮及导入入口。虽然它拦住新错误 payload，仍不满足本次明确的“wrong scope 返回必须清私有、不缓存”要求，也没有对该工作区其它并发读取建立失效边界。

**最小修复：**在资产自身合同/client 内明确区分会话/资产范围违例，交给现有工作区失败回调关闭该私有工作区；清目录、详情/历史、回执和上传 File/request，并使已在途资产读取不能恢复状态。保留安全错误和重新核对会话路径。若使用统一严格 DTO 合同失败清除，也应说明范围；不要把 503 部分失败或普通可重试解析故障全部伪称 session_expired，不改共享认证、权限表或后端合同。

**复验：**复跑独立 A/B，错误返回后名称、目录、详情、历史、回执及文件全部消失；另以可控 promise 延迟其它读取，范围违例后释放必须不能恢复。再跑原 447 前端、类型/lint/build、资产 6 + 图 6 Edge；保留 503 可阅读/同键重试、401/403、登出、404、hash 刷新/返回及范围切换检查。A/B 合并为同一根因，不重复算两条独立缺陷。

若跳过：用户仍能在已发现范围违例的工作区读取和操作保留的私有状态，范围清除承诺没有兑现。

## 独立执行结果与日志

所有 npm 命令 cwd：`D:/wt/r17-assets-review1/frontend`。真实开始/结束（含 +08:00 秒）、命令数组及退出码在本 run 对应 `.command.json`；计数来源于原始 stdout，不汇总重复执行为新测试。

| 检查 | 实际命令 | 退出码 / 结果 | 日志 |
|---|---|---|---|
| 完整前端 | `npm test` | 0；34 files、447 passed、0 failed/skip | `regression.log` |
| 类型 | `npm run typecheck` | 0 | `typecheck.log` |
| lint | `npm run lint` | 0 | `lint.log` |
| 构建 | `npm run build` | 0；构建实际 dist 后才跑浏览器 | `build.log` |
| 原 Edge | `npm run test:e2e -- --config ../reports/runs/recovery_r17_assets_review1_20261016/playwright.baseline.config.cjs` | 0；资产 6 + 原图 6，12 passed、0 failed/skip/flaky | `edge_baseline.log`、`baseline_report.json` |
| 独立负例 | `npm run test:e2e -- --config ../reports/runs/recovery_r17_assets_review1_20261016/playwright.independent.config.cjs` | 1；5 distinct cases，3 passed、2 failed、0 skip/flaky | `edge_independent.log`、`independent_report.json` |
| 独立动态背景 | `npm run test:e2e -- --config ../reports/runs/recovery_r17_assets_review1_20261016/playwright.motion.config.cjs` | 0；1 passed、0 failed/skip | `edge_motion.log`、`motion_artifacts/` |
| 作者证据亲核 | `python reports/runs/recovery_r17_assets_review1_20261016/audit_author.py`，cwd 审查根 | 0；93/93 raw 文件的长度、工作字节、作者工作字节、冻结 Git blob 和审查 index 全同 | `audit_author.log`、`author_byte_audit.json` |
| 冻结源码/材料 whitespace | `git show --check --format=fuller 1acf4911731f654e11b6173b24db21214d753c02` / `6db161e59e1c081d249b510ac441c93ad2fd295b`，cwd 审查根 | 两项 0 | `source_check.log`、`material_check.log` |

首次浏览器调用有 PowerShell 数组参数语法错误（exit 1），没有启动 Playwright、没有业务计数；随后使用明确字符串数组启动。记录于 `instrumentation_history.json`。没有改失败为 skip、删原 fixture 或覆盖原失败证据。独立探针的 fail 输出原样保留；最终原基线 12/12 不抵销新增负例失败。

独立负例 C 通过：先真实提交导入，延迟 `/auth/csrf` promise，随后鼠标进入会话并登出；释放旧 CSRF 后没有 `/asset-imports` POST，私有名称计数 0。D 通过：真实 503 POST 后同 bytes/key 重试；修改同名文件内容后新 key；pending 按钮禁用且再次鼠标点击不新增提交；三次实际 POST 的字节分别为 first/first/second，Origin、CSRF、query 无 tenant/role 断言通过。E 通过：history 404 先到，释放迟到 current 后不恢复详情标题或快照。这些操作均经真实 event、fetch、promise、routing 与生产包。

原资产六 Edge 独立重跑覆盖加载/空、403 清除/无读取权限不发私有请求、JSON 原字节 201/同资产追加/hash reload/back、390 历史分页和 503 重试、固定历史、CSV 错误/同键原字节重试、目录分页/登出/401/迟到旧范围。它们使用作者 synthetic intercept，但独立端口、进程、构建包和执行结果，不作为后端或 live 通过。

独立视觉探针在普通 motion 下确认 `topology-drift` 为 running，浏览器实际 animation currentTime 增加超过 100ms；reduced-motion 下 animationName=none、active animations=0，390px document 不横向溢出。原资产 390 探针对可见 button/summary/catalog 的 44px 高度断言通过。查看本 run 的 390 历史及 A/B 失败截图，深绿底色、明确 partial/unknown/history 字样和边界呈现可读；只算 synthetic UI QA，manual 仍 not_run。

## CBM、字节和事实核验

业务源码阅读前执行独立 CBM：portable CLI `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`，`index_repository --repo-path /mnt/d/wt/r17-assets-review1/frontend/src --name r17_assets_review1_frontend_20261016 --mode fast`；schema、architecture、AuthorizedAssets trace 均真实执行。fast 为 405 nodes / 1468 edges，默认排除 features/assets，trace exit 1/function not found，保留输出。启动 full 索引脚本时 fast 又运行一次，同样结果；没有把缺边当 dead code。

再以独立项目 `r17_assets_review1_frontend_full_20261016`、同一真实 frontend/src `--mode full` 执行 index/schema/architecture/trace：均 exit 0，678 nodes / 2630 edges，not_indexed/partial/unusable 为 0；AuthorizedAssets 35 callees / 3 callers，确认 App → scope key → AssetWorkspace 和共享 API/auth 调用。作者 full 记录为 678/2637；数量差异如实保留，不用来否定真实调用。实际合同、错误回调和 callers 另经 rg 与直接源码核对。

作者 raw manifest 亲核 SHA-256：`8c40f723ddc65f467a1c31ee8216c159f09607e56f7fbc1ebf23b242e70192e6`，与主控提供相同；93 项工作/冻结/index 字节全同。15 个业务文件对 CODE 的 Git LF 规范化比较均相同，review index 均与 CODE blob 相同；真实 binary diff 与作者 business.diff.gz 解压内容一致。报告 SHA 与本次 review 证据 manifest/hash/原始字节证明见本 run `sealed_byte_proof.json`，避免自引用 hash。

亲读并保留作者初始 typecheck tuple/never 错误、旧 Edge 11/12、fast trace 缺函数、首版 fixture EOF whitespace 和未建模块 first_red。它们是历史失败，不算业务通过；也没有剪掉 raw log 或全局关闭检查。精确作者 run 的 `.gitattributes -text/-diff` 规则未扩大。

本审查全部新增材料的 `git diff --cached --check` 为 exit 2，来自未改的原始 CLI 编号片段/Playwright error-context 尾空格；报告和 reviewer probe/scripts 定向检查 exit 0。raw 字节保持，未改 `.gitattributes` 或关闭全局检查。首轮封存 guard 因 Git 对中文路径 quoting 误报范围，真实 bytes/source 差异均 0；已改用 `--name-only -z`，首轮 proof/log 保留，详见 instrumentation_history。

真实合同确认：GET source_version 没有公开，界面明确未知；product 为 package_name 精确筛选、cursor/limit 有界；UUID 与 snapshot/current 关联校验；POST 为原 File bytes、固定 json_manifest_v1/csv_components_v1、source_version/observed_at/query、同源 Origin + X-CSRF + actor 范围幂等键，返回实际 201 DTO；没有 body tenant/role 或按 analyst 名称授写权限。组件缺值、配置 null 与 false、内部网络声明与外部观察分开。条件/四态/FOFA/export 没有伪完成。

## 未检查、偏差、评分证据及交接

- backend integration、真实 PostgreSQL/auth 导入→current→history、live、人工标注、连续视频均 `not_run`。根默认工厂接线在另一审查中，不使用不可用路径，也不冒称其它 Agent 的 SBOM 扩展已可用。
- 本轮只核对内部前端/合同和 synthetic browser，不验证真实性、资产完整性真值、评估准确率、模型、多跳、外部资产或费用任务。`read:asset` / `write:asset` 及 201 来自批准 CR-R11 和真实源码，旧 05 的 202/analyst 条款偏差保持显式。
- F2 证据限于资产声明/快照/组件展示；F3 限于未知/固定版本与权限防线，M01 尚未通过；D2 限于实际浏览器交互、布局/动效及状态。原 T42 C01–C06 的实际四态、外部观察、重算、assessment stale 与导出都未据此验收，完整 R17/T42 仍 partial。
- Playwright headless 隐藏运行、独享 `127.0.0.1:25719` 的 Vite preview/dist；各 run 由其 own webServer 管理并退出。未接触 CNNVD 用户 IAB 登录页、没有 kill 用户/其它 Agent 进程；清理快照见 `cleanup_receipt.json`。
- 下一任务建议：作者在资产 owned 合同/client/state 做 M01 有界修复；由独立 reviewer 针对新冻结 code/material 重跑失败输入与并发迟到边界，再由主控决定该切片放行。真实默认后端联测和原卡完整验收仍独立待办。

Verdict: fix M01 first. `needs_changes`。
