# R17 / T42 · 资产清单工作台接线

状态：`awaiting_review`。本资产清单前端切片实现完成；R17、T42 整体仍为 partial。未签 G-E、accepted 或 live，也未改 progress、金标、分母。报告时间：2026-10-16T06:15:25+08:00。

源码：`1acf4911731f654e11b6173b24db21214d753c02`；首次源码提交 `3f1553b7a470b111dc112dd53c33d4835be05c2f`。最终仅删掉一行 synthetic fixture EOF 空白，运行逻辑与已测版本相同。基底 `e310f7735bd499c4d9fbcefe8a644e2309a16a62`，已审默认图材料 `164cae93ac888180b056a4c694011402ee387383`（源码 `baa9fa7e024981f8a5516bd840e49910ce7cd1f9`）在本工作树合为 `9be85d7`。唯一冲突 .gitattributes 保留两侧精确 reports 规则并集。

工作树 `D:/wt/r17-assets-workbench`，分支 `codex/r17-assets-workbench`。不触碰 rootmain 未提交修改；本工作树 build 生成的 tsbuildinfo 已恢复到基底。后端、共享 auth/api、global CSS、依赖锁、迁移、其它事件/图实现未修改；普通本地提交已做，没有 push。

## 输入、合同和设计

编码前读取 AGENTS、00_execution_map、R17/R11 恢复卡、T42、03/04/05、CR-R11、进度/交接、现有 App/Auth/hash、assets inventory DTO/router/parser 与现有前端 client/status/style。修改前独立 CBM 项目 `r17_assets_frontend_20261016` 已完成 fast index/schema/architecture/fetchJson trace 与 rg；404 nodes / 1464 edges，partial/unusable 为 0。trace 有 28 callers，确认 App → AuthProvider、现有 fetchJson/CSRF 与子工作区之间的会话边界。先向主控交付端点/DTO/role 和精确文件清单，再写合同测试及业务代码。

应用 `industrial-brutalist-ui` 与新版 `ponytail` full：保留主控指定的现有深绿黑客终端底色、动态拓扑背景与 reduced-motion；资产区域采用直角、细线网格、等宽 ID/时间、目录与详情两栏，大数据表在本区域滚动。390px 改为单栏，操作按钮和完整关联标签提供至少 44px 目标。没有新全局样式库、图表/解析依赖或营销页面。用户 ui-design.md 只作为需求参考；只读取该精确文件，没有读取同目录 KEY/.env/其它材料。参考的 32px 密集行高不覆盖本轮 44px 操作要求。

后端实际接口保持为以下限定合同，GET 无 source_version，明确显示未知。03 的完整字段映射到私有 `r11-asset-candidate-1` DTO；没有宣称完成 public v2 AssetSnapshot 或新增业务 schema。

| 接口 | 投影 / 边界 |
|---|---|
| GET `/v1/assets?limit=20&cursor&product` | 当前认证 tenant 的 Asset + current Snapshot；product 是 package_name 精确筛选，next_cursor 驱动后续页 |
| GET `/v1/assets/{uuid}` | 单资产当前指针与完整当前快照 |
| GET `/v1/assets/{uuid}/snapshots?limit=20&cursor` | 保存历史分页；每项为完整 Snapshot |
| GET `/v1/assets/{uuid}/snapshots/{uuid}` | 点击历史时重新获取固定版本，校验 requested asset/snapshot/tenant 一致 |
| POST `/v1/asset-imports` | 原 File bytes，1..1048576；query display_name/source_version/observed_at/manifest_format，可选后端已知 asset_id 与 CSV mapping；同步 201 `{asset_id,snapshot,reused}` |

复用 fetchJson 的 Cookie include、no-store、超时和安全 ApiProblem；使用 getCsrfToken，浏览器同源 POST 自动提供 Origin，附 X-CSRF-Token 与 Idempotency-Key。JSON/CSV 格式仅 `json_manifest_v1` / `csv_components_v1`。JSON 本地预览只汇总格式/组件数量/完整性声明，不重新序列化上传；CSV 要求显式字段→列名映射。原 File 引用及同一请求幂等键在不确定失败后保持，编辑输入才创建新请求；重试同 bytes/key。追加仅使用已读取资产 UUID，名称锁定；返回其它资产的 receipt 拒绝为 invalid_response。

权限依据认证 permissions + 非空 tenant：`read:asset` 读、`write:asset` 写，不按角色名称 grant。当前 viewer 不读，analyst 只读，system_admin 未关联 tenant 同样拒绝。请求中不传 tenant/role/server_path。05 旧表的 analyst 写/异步 202 与已批准 CR-R11 实际限定不同，明确按真实权限和 201 执行。未来 202 不伪造 job 或动画进度；当前 async schema 尚不支持，返回合同错误并要求核对资产列表。

## 改动文件和可观察行为

| 文件 | 内容 |
|---|---|
| `frontend/src/App.tsx`、`app/workspace-navigation.ts` | #assets 与 #assets/{uuid}；会话 scope-key remount；保留已审图入口 |
| `features/assets/asset-contracts.ts`、`asset-client.ts` | 完整 DTO 严格解析、UUID/tenant/当前指针关联、cursor 与原字节导入 |
| `asset-workspace.tsx`、`asset-detail.tsx`、`asset-import.tsx`、`asset-status.tsx`、`assets.css` | 授权目录、筛选/分页、当前/固定历史、导入/预览/安全错误与状态 |
| `asset-contracts.test.ts`、`asset-client.test.ts`、`synthetic-fixtures.ts`、`frontend/tests/t42_assets_assessment_ui.test.tsx` | 22 项明确 synthetic 合同/client/组件行为检查 |
| `frontend/e2e/r17-assets.fixture.ts`、`r17_assets_fixture.spec.ts` | 独立 Edge 六场景；原图六场景保持原文件 |
| `.gitattributes`、本报告与 `reports/runs/recovery_r17_assets_workbench_20261016/` | 仅本 run 原始字节保留与真实证据 |

目录中的数量只表示已读资产/组件声明，不显示总影响或安全。未知版本、比较方案、purl、镜像摘要、声明范围和工具权限分别可见；configuration null 与 false 不合并，输入通道/网络声明同样保持未知。组件可读取生态、完整版本、purl、镜像摘要、依赖路径、component_id 与 source_field_locator；组件超过 20 项时在完整快照中分页展示。

历史页与 current 是独立读取，发现更高 snapshot_number 时将当前指针标为待复核，要求刷新；历史版本保持保存声明，不当作当前研判。503 历史/分页失败保留可阅读的已读内容并显示未重新验证；403 清私有目录/详情/回执，401 失效立即清状态并显示“会话已失效，私有资产已清除”。404 失效资源清详情，并阻止同一资源迟到的读取恢复字段。hash 刷新/返回重新读取 API；私有结果/File 不入 localStorage/sessionStorage，不跨 tenant/auth 代次恢复。

外部观察、条件树/四态、评估 freshness、重算任务、证据包/OpenVEX 明确未接通且禁用。网络配置声明与外部观察分栏；网络不可达不解释成软件修复。没有源码执行、任意 URL、第三方扫描或外发消息。原 File 只在浏览器内存与私有后端；日志/截图全部使用显式 synthetic 清单。

## 实际验证

执行目录为本工作树 frontend；每项最终命令的 +08 开始/结束、退出码均见对应 `.command.json`。Node v24.13.1 / npm 11.8.0，复用已存在 node_modules junction，没有安装依赖或修改锁。下列是真实执行结果，不是待执行说明。

| 检查 | 实际命令 | 结果 / 日志 |
|---|---|---|
| 新合同/client/UI | `npm run test -- --run src/features/assets/asset-contracts.test.ts src/features/assets/asset-client.test.ts tests/t42_assets_assessment_ui.test.tsx` | exit 0，22 passed / 0 failed / 0 skipped；unit_seal.log |
| 完整前端回归 | `npm run test` | 2026-10-16T06:11:11.927+08 至 06:11:45.262+08；exit 0，34 files / 447 passed / 0 failed / 0 skipped；425 原有 + 22 新增；regression_delivery.log |
| 类型 | `npm run typecheck` | exit 0；typecheck_delivery.log |
| 风格 | `npm run lint` | exit 0；lint_delivery.log |
| 构建 | `npm run build` | 2026-10-16T06:12:30.999+08 至 06:12:35.540+08；exit 0；build_delivery.log |
| Edge | `npm run test:e2e -- --config ../reports/runs/recovery_r17_assets_workbench_20261016/playwright.assets.config.cjs` | 2026-10-16T06:11:36.785+08 至 06:11:51.024+08；exit 0，12 passed / 0 failed / 0 skipped / 0 flaky；edge_delivery.log / 派生 edge_delivery_report.json |
| CBM 最终 | portable CLI 独立 full index/schema/architecture/AuthorizedAssets trace | exit 0；678 nodes / 2637 edges，partial/unusable 0，trace 35 callees / 3 callers；cbm_seal_full_*.json 与 command receipts |
| 源码 whitespace | `git show --check --format=fuller HEAD` | 最终 exit 0；source_final_diff_check.log |

Edge channel=msedge，独立 127.0.0.1:25387，不复用用户服务或浏览器。主要操作通过实际 bounding box + page.mouse.click；覆盖加载→空、403/只读 gate、JSON 原 bytes 201/追加同资产/深链刷新返回、390px 历史分页/503→重试/固定历史、CSV 字段错误/503→同 key 原 bytes 重试、目录分页/登出/401/迟到旧租户响应。390px document 不横向溢出，可见按钮/summary/catalog 至少 44px，reduced-motion 动态背景为 none。六条已审图 Edge 回归未改且通过。cleanup_receipt 确认本端口连接与本工作树 node 进程均为 0；Playwright 关闭自建 Edge profiles，未访问用户 CNNVD IAB、未 kill 其它进程。

截图均 synthetic。作者检查 loading/empty-import、import-success、history-390 的像素，布局与可读性满足本切片；人工验收、连续录像、真实后端联测和 live 为 not_run，不能用这些截图代替。生产包没有 synthetic-fixtures 的示例名称/包名 payload，见 verification_summary。

保留首次失败而不改 skip：first_red 是计划中新 DTO 模块尚未建立而无法收集，exit 1，并非环境/业务通过；首次 typecheck 的 mock tuple 和 Testing Library exact 测试类型错误修复后 exit 0；ui_pointer_red 为 8 pass / 2 fail（新版本指针和 404 边界），修复后 10 pass；edge_seal 为 11 pass / 1 fail（同资产追加显示两处成功回执），删重复回执后 12 pass。最终 fast CBM 默认排除 features/assets，trace exit 1“function not found”，没有拿空图冒充；另建 full 项目实际完成资产 trace。首次 staged whitespace 检查发现 fixture EOF 空行，exit 2；同一 shell 未阻断本地 3f 提交，已以独立 1acf 修复并保留 source_first_diff_check.log，不 push。raw stdout 派生 JSON 首次脚本假设 LF，因 CRLF 解析失败，改为读取首个 JSON 对象后 source_audit exit 0。

原始证据由 raw_manifest.json / .sha256 索引长度与 SHA-256，business.diff.gz 留完整 source patch（未压缩 hash 在 source_receipt）；Git 字节比对见 git_byte_audit。仅本 run `-text` 保留 raw logs/JSON/PNG，不扩展到业务源码；本 run `.log -diff` 与精确 `edge_append_failure_context.md -diff` 防止原始终端/Playwright 编号代码片段输出被当作源码 whitespace。material_first_diff_check 记录后者的原始尾空格失败，保持字节并限定例外后复查；没有删改日志。业务文件的 core.autocrlf 差异单独记录，没有修改事实材料。源码、输入合同/锁/参考文件的真实 SHA 在 source_receipt，不将生成结果冒称输入版本。

## 未运行、偏差与交接

integration/live=`not_run`，由主控完成默认后端 app 真实接线后在隔离 PostgreSQL 环境联测，不标 live passed。manual=`not_run`；作者 synthetic 视觉检查仅是 UI QA。私有原清单下载不支持；GET 没有 source_version，也没有 source trust/coverage 独立验证或 assessment freshness，本页明确未知。共享 fetchJson 不传递后端公开 locator 扩展，因此导入失败以安全 code 映射的字段/表头说明显示；成功快照的完整字段 locator 可读，没有猜失败的精确行号。

| 原 T42 案例 | 本切片证据与剩余条件 |
|---|---|
| C01 三不同快照实际判定 | 历史/current 读取有证据；实际四态判定未运行 |
| C02 缺版本/观察时间 | 缺版本/来源版本与 null 配置明确未知；现有 DTO 观察时间必填，未知观察时间不能提交，没有填造时间；整项部分 |
| C03 外部不可达 | 内部网络声明不推断修复；外部观察真实调用未运行 |
| C04 修改演示配置后重算 | 原 bytes 导入/追加固定资产经过同 API；实际 Assessment/job 重算未运行 |
| C05 旧结论 stale | 历史快照与当前指针待复核边界有测试；Assessment freshness 尚未接通 |
| C06 导出权限/映射不足 | 明确禁用和失败限制；真实证据包/OpenVEX 权限/映射验收未运行 |

评分证据限定为 F2 的完整授权清单/版本/字段呈现、F3 的范围/未知/固定版本阅读边界、D2 的真实前端操作/错误状态/390px/reduced-motion。没有登记准确率、持续运行、性能、真实多跳、FOFA 或完整 R17/T42 达标。

下一建议：由未参与实现的新 reviewer 固定本源码与材料 hash，独立复跑 447 前端与 12 Edge synthetic 检查；主控随后做真实 backend/auth/PG 导入→current→history 联测。主控负责更新状态及 G-E 限定审查，本实现者不签 accepted。
