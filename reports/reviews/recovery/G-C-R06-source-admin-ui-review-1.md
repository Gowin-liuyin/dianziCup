# G-C R06 九固定来源管理 UI 独立初审 1

What this change does: 将既有单源采集页面扩为九个封闭来源入口，按八类展示登记范围。仍由用户显式提交一源、读取 PG 单页任务，保留 Cookie、CSRF、Origin、幂等键与权限边界。

**结论：限定 Ship。** 未发现本切片需要修复的已证实 bug。此结论仅覆盖下述冻结 UI 代码与隔离验证；整 R06、R17、G-C 不签 accepted，九来源真实 API/PG/采集与持续监测不计通过。

## 身份、版本与审查边界

本批全新独立 reviewer `/root/r06_source_admin_ui_independent_review`，未参与实现，也未采用作者结论作验收依据。读实际 AGENTS、执行地图、R06/R17 卡、03/05/08 合同、`CR-R06_source_collection_catalog.md`，按官方 Ponytail 5.2.0 `ponytail-review/SKILL.md` 检查调用链与具体错误场景；用户要求的中文报告优先于技能英文输出偏好。

| 项目 | 固定值 |
| --- | --- |
| 主库 / 作者树 | `D:/dianzi` / `D:/wt/r06-source-admin-ui` |
| 基线 | `0a45185ae3ffb73a6d186b98421e26a52f78bfc6` |
| UI 代码 | `4f00999c2834a14752f4d53a78ccac66abed5cab` |
| 材料 / 审查 HEAD | `6f38d4284e62820415d829c9f113193e9bfce1b0` |
| 独立树 / 分支 | `D:/wt/r06-source-admin-ui-review-1` / `codex/r06-source-admin-ui-review-1` |
| 冻结记录时间 | `2026-10-15T21:27:33.8091039+08:00`；这是记录创建时间，之前只读与建树未补造秒级起点 |
| 报告时间 | 2026-10-15，+08:00；文件实际落盘/冻结时间见 manifest，未补造编辑开始秒级时间 |

实际执行 `git worktree add -b codex/r06-source-admin-ui-review-1 D:/wt/r06-source-admin-ui-review-1 6f38d4284e62820415d829c9f113193e9bfce1b0`，初始干净，审查全程未改变 HEAD。主库已有其他进度/报告未提交修改，未触及。

代码差异共八文件、388 增/20 删：

- `frontend/src/api/source-contracts.ts`、`source-catalog.test.ts`。
- `frontend/src/features/sources/source-catalog.ts`、`source-workspace.tsx`、`sources.css`、`source-admin-catalog.test.tsx`。
- `frontend/e2e/r06_source_admin_fixture.spec.ts`。
- `docs/design/recovery/R06-source-admin.md`。

核对 App、auth/app、source-client、package/lock、原 source DTO/client/workspace 测试与原 r17 fixture 均无此 diff。源码及设计 SHA256、完整 diff、所有权核对在本 run。审查仅写本报告及 `reports/runs/recovery_r06_source_admin_ui_review_1_20261015/`，无业务补丁、push 或状态登记；build 生成的已跟踪 `frontend/tsconfig.tsbuildinfo` 已恢复本审查 HEAD。

## 合同与源码追踪

封闭九 key 与 `ingestion.source_catalog.CATALOG_SOURCES` 的 key、八 category、content_scope 逐项一致，NVD/OSV 共一类。目录保持九条「未验证」，不把登记数、fixture 受理或按钮数算作 live 覆盖。release、RSS 片段、论文摘要/全文、自愿框架与政策适用判断都有独立边界文字。

使用已有 WSL `Ubuntu-22.04` 官方 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` **0.11.0**，对本审查树 **frontend/src** 独立 `fast` 索引，project `r06-source-admin-review-1-frontend-src`，`persistence=false`。结果 299 nodes / 1115 edges，23 个测试文件按 fast-pattern 排除；索引根不含 backend、reports、secret 或 holdout。未修改工具配置，未使用作者索引。

图证据 `SourceWorkspace` inbound 为 `Workbench → App`；`collectSourcePage` inbound 为 `runRequest → SourceAdminWorkspace/submitCollection → SourceWorkspace → Workbench`。outbound 指向 `validateSourceSubmission → getCsrfToken → fetchJson → parseSourceJob`。图含 heuristic 边，已用 `rg` 与实际源码复核，未将图推断当事实。

`App.tsx:143,208` 以身份、租户、权限版本、模式和会话代次隔离 workspace；`source-workspace.tsx:66–141` 冻结提交、清旧 job/time、单个 in-flight、卸载 abort 与代次 fencing；`source-client.ts:5–22` 保存原 body/path/key、CSRF 后重新检查当前会话、Cookie credentials include、GET UUID 对应检查；`source-contracts.ts:34–57` 在网络前限制来源、过去带时区窗口、1–20 页及固定 body 字段。只走已有 POST `/v1/sources/{source_kind}/collect` 与 GET `/v1/jobs/{uuid}`，没有 GET sources 或渲染时批量采集，请求不含 tenant、任意 URL、token 或自报权限。Origin 来自浏览器，不由客户端伪造。

**集成边界已核实：** 本冻结树 `backend/src/ai_intel/ingestion/source_jobs.py:57` 仍是原两 key；此 UI 分包没有改后端 route/worker。九 key 对齐的是批准的 catalog 扩展合同，不能推论该树真实 API 已接通九 key。后端扩展与同集成 SHA 的真实验证是主控后续前置；这是已批准分包边界，不作为本 UI bug。

## 独立命令与实际结果

所有 npm 命令 cwd 为本审查树 `frontend`。Node 24.13.1 / npm 11.8.0；node_modules 是 `D:/dianzi/frontend/node_modules` junction，两树锁 SHA256 同为 `79E4DF46C6646AB2D878B8BAEAA9985AB44A1C802A0F47C950EE1869A4CB8C61`。没有 npm 下载，也没有做全新依赖安装复现。补查 `npm ls --depth=0 --offline` exit0，实际 Playwright 1.64.1、Vitest 4.1.11、TypeScript 5.7.3、Vite 6.4.3；junction 使传递包被 npm 显示为 extraneous，此记录不证明干净安装，起止和输出见 `dependency_tree_command.json/log`。

| 实际命令 | +08:00 开始 → 结束 | exit / 结果 | 本 run 证据 |
| --- | --- | --- | --- |
| `npm test -- --reporter=json --outputFile=../reports/runs/recovery_r06_source_admin_ui_review_1_20261015/unit_all.json` | 21:27:58.9816680 → 21:28:22.3620522 | 0；339/339，24 文件，0 fail/0 skip | `unit_all.json/log/command.json`、`unit_files.json` |
| `npm run typecheck` | 21:27:58.9836176 → 21:28:03.2760906 | 0 | `typecheck.log/command.json` |
| `npm run lint` | 21:27:58.9910247 → 21:28:02.6531127 | 0 | `lint.log/command.json` |
| `npm run build` | 21:28:56.3202198 → 21:28:59.9206887 | 0；tsc + Vite，50 modules | `build.log/command.json` |
| `DIANZI_E2E_FRONTEND_URL=http://127.0.0.1:25516 npx --no-install playwright test --config=../reports/runs/recovery_r06_source_admin_ui_review_1_20261015/playwright.review.config.ts` | 21:33:15.4811099 → 21:33:37.8118549 | 0；真实 Edge 20/20，原 8 + 独立新增 12，0 fail/skip/flaky | `edge.log/report.json/command.json`、`edge_artifacts/` |
| `git diff --check 0a45185...4f00999 -- frontend/src frontend/e2e docs/design/recovery/R06-source-admin.md`，实际完整 SHA 命令见 JSON | 21:36:23.7118635 → 21:36:23.7837021 | 0 | `diff_check.log/command.json` |

339 单元是原 305 + 新目录 16 + 新 UI 18，作者宣称的数量已独立重跑核实。原 DTO 25/client 10/workspace 22 保留且通过；覆盖原两来源、封闭非法 key、字段/时间/页界限、九种 PG 状态、恶意结果字段、CSRF/权限/幂等/取消与网络错误。

Edge 使用本树自有 Vite、单 worker、msedge channel、严格 loopback 端口、`reuseExistingServer=false`；API proxy 指向无服务 `127.0.0.1:9`。全部身份/管理/任务接口明确浏览器 fixture 拦截，新增 fixture 还阻断非 loopback 请求，未知接口直接失败。没有连接 PG、模型或上游。trace/video/失败自动截图关闭；仅主动截来源页，无真实账号输入。

Playwright 已自动结束自有 Vite；`2026-10-15T21:34:39.3942776+08:00` 核对 25516 无监听，`teardown.json` 为 `listening_count=0`。

## 新增负例：触发、预期与实际

独立测试保存在本 run 的 `review_negative.spec.ts`，未写或改产品/原测试。期望以可见行为及冻结合同定义，不从业务函数生成。

| 独立触发 | 预期 | 实际 / 数量 |
| --- | --- | --- |
| 网信办新源 CSRF 延迟；尝试切源、新轮与重复提交；释放后改 OSV | 在途与冻结控件禁用；仅原源一次 POST；新轮/切源清旧 job/time；键盘选择聚焦表单 | pass，1；请求 Cookie/Origin/CSRF/key 与三个 body 字段核对通过，390px 截图 |
| arXiv 已受理后 GET 401 或 403 | 清身份或全部管理资源；不保留旧成功、job、快照时间 | pass，2；目录、任务 article 与旧受理标题均消失 |
| Ollama release POST 迟到，在返回前退出并登录新会话 | 晚到旧 202 不恢复旧受理/job/time | pass，1；新页仍为空状态、空 UUID |
| NIST CSRF 迟到时刷新会话为 analyst | 权限撤回后不发送 POST | pass，1；writes=0 |
| AVID 查询迟到时重新验证管理员权限版本 | 新会话代次不能被旧查询恢复 | pass，1；返回新页后 job/time/旧受理为空 |
| 已取得手工快照后 GET 404/422/429/503 | 分别展示错误；旧快照消失，未知不写 0；原 UUID 可手动恢复，不暴露服务端 raw detail；再切源清 UUID | pass，4 |
| NIST POST CSRF 403 后取得新 CSRF 原样重试 | 来源/body/key 不变，仅 token 更新；冻结时仍不能切源 | pass，1；两次 POST 比对通过 |
| 390px 最大安全整数尝试次数、99 字符 error_code、200 字符 PG 引用的 partial | 文本换行不横向溢出；partial 仍提示后续页；背景不拦操作；reduce 停动画 | pass，1；DOM 边界与截图通过 |

原 8 Edge 在本树重新跑：九源桌面/390 key/类别/单源/429 相同 body-key/partial/unknown-source/503/切源，权限撤回、logout 迟到 GET，新页面旧两源 retry/state、非管理员与晚到 CSRF、401。

## 视觉检查与错误语义

实际使用 view_image 原分辨率查看本次生成的三图：`catalog-fixture-initial-1366.png`、`catalog-fixture-partial-390.png`、`review-long-metadata-partial-390.png`。桌面目录与操作双栏、手机单列；名称/key/说明/长元数据可读并换行，无页面横向溢出。背景低亮、不覆盖内容，pointer-events none；Enter/Space 选择、Enter 提交、2px 焦点与 reduced-motion 停动画有浏览器断言。共八张原始截图完整保留，另五张不冒充已人工实看。

页面不伪造百分比或持续时长；尚未查询与 HTTP 失败分离，finished_at null 显示未知，手工 UUID 来源未知。仅匹配本轮 POST 的 job_id 才标来源；`succeeded` 解释为本页完成，`partial` 仍提示有后续页。PG created/finished 与本次客户端收到快照时间分别显示 +08:00；未发明 API 未提供的 freshness/TTL。429/503 不改 key 或自动提交新轮；401/403/卸载/新会话晚到结果不恢复旧成功。

## 发现、限制与交接

**已证实 bug：无。** 不建立无具体触发的猜测 findings，也不因个人风格提出补丁；最小修复与缺陷复验均不适用。本次自动测试无失败或 skip。

**缺测 / 未检查：** 九来源真实 API/PG/worker/上游链路、真实权限事务竞争、实际持续采集与时延分母、全新 npm ci、屏幕阅读器与原生后台 hidden 暂停均未验收。integration/live 为 not_run，授权禁止本批真实采集；这些限制不能算通过，也不伪装成业务失败。未读取 DPAPI、秘密/holdout，未调用收费 API、外网或运行 PoC。

工具探索出现两次非业务问题：未安装名为 Ubuntu 的 distro，改用实际 Ubuntu-22.04；空参数试探 index_repository exit1 报 repo_path required，读取 CLI help 后以文档 flags 成功。CBM 首批命令起止秒级时间未记录，只保留真实产物时间，不补造耗时；具体命令及限制见 `cbm_commands.json`。没有降低断言或修产品来取得通过。

评分证据仅支持 F1/D2/E1 的固定入口、可观察状态、权限/错误/重试与窄屏体验切片；不证明八类 live 覆盖、持续监控、性能目标、完整工作台或整阶段验收。主控下一步合并同版本后端扩展，按同一集成 SHA 做九 key 真实 POST → PG job/outbox/游标 → UI 手动 GET 与失败/partial 验证，再决定该集成切片状态。

产物精确清单与 SHA256 见本 run `artifact_manifest.json`；本报告独立 hash 由最终交接返回。状态只为独立审查完成、限定 Ship 建议，未登记 accepted。

Verdict: **Ship — 仅 4f00999c2834a14752f4d53a78ccac66abed5cab 九固定来源 UI 切片。** Not checked: 上述真实集成/live 与完整 R06/R17/G-C。
