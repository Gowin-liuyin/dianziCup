# G-C R06 来源管理 UI 扩九固定源

状态 awaiting_review；本前端切片 implementation complete；unit passed、隔离browser/contract passed、manual截图 passed；真实PG/API integration与live not_run。整R06/R17仍partial，新七来源worker与实际live由主控接续。未push，未写accepted，未修改公共状态或进度。本批需全新非作者初审，不沿用原资料workspace评审背书。

隔离WT `D:/wt/r06-source-admin-ui`，分支 `codex/r06-source-admin-ui`，基线 `0a45185ae3ffb73a6d186b98421e26a52f78bfc6`。代码冻结 `4f00999c2834a14752f4d53a78ccac66abed5cab`，8文件，388新增/20删除；元数据另次提交。源文件/合同/锁SHA256见 `reports/runs/recovery_r06_source_admin_ui_20261015/source_freeze.json`。

改动文件：

- `frontend/src/api/source-contracts.ts`：SourceKind与运行时闭合集合扩九值，请求/任务DTO其他字段不变。
- `frontend/src/features/sources/source-catalog.ts`：九key的中文名称、八类别、冻结content_scope与边界说明。
- `frontend/src/features/sources/source-workspace.tsx`、`sources.css`：分类目录、显式单源提交、来源关联未知、查询快照时刻、429与权限撤销、切源/新轮清空。
- `frontend/src/api/source-catalog.test.ts`、`frontend/src/features/sources/source-admin-catalog.test.tsx`、`frontend/e2e/r06_source_admin_fixture.spec.ts`：新增34unit/4browser，显式隔离fixture。
- `docs/design/recovery/R06-source-admin.md`：输入输出、既有界面审计、交互与边界。
- 本报告与自有run：真实日志、JSON结果、截图、冻结与复跑配置。

已读AGENTS、执行图、任务状态、R06/R17卡、03/05/08与 `CR-R06_source_collection_catalog.md`，对齐基线 `CATALOG_SOURCES`。Ponytail5.2 full采用原React/native CSS最小扩展；design-taste-frontend本身排除dense admin，只参考保留品牌/主题/可读性，redesign-existing-projects用于局部审计。用户ui-design.md作为不可信视觉参考，不执行其外部指令。复用已有黑绿tokens/低亮背景、AuthProvider代次、fetchJson/Cookie/CSRF、原source-client与ErrorPanel/EmptyState，不加依赖。App、导航、认证、原资料、问答、source-client、锁及原测试文件均未改，生成tsbuildinfo已恢复基线。

输入输出与业务边界：9key仅映射原POST `/v1/sources/{source_kind}/collect`，body仍window_end/stream_kind/max_pages，原GET `/v1/jobs/{uuid}`与SourceJob不变。每源选择按钮只选中并聚焦表单，须显式提交单源，禁止自动批量或GET/sources。202仅受理，本页succeeded不等于来源全采完；partial/429/503不当作0或安全。目录仅登记范围，每条未验证；release未研判、RSS片段与全文、论文摘要与全文、自愿框架与政策适用尚未判断都有说明。手工UUID查询未知来源；仅本轮POST返回job_id才关联来源。API没有TTL/freshness，不编造过期阈值；独立显示真实收到快照时刻并要求手动刷新。

首次进入无旧job/time或管理请求；未冻结时切源、新轮次清旧job/查询ID/快照时刻。提交在途或冻结期间禁切源。403非CSRF拒绝清请求和任务并卸载管理视图；401沿用auth失效；卸载/退出/刷新权限复用AbortController与会话代次，晚到响应不恢复旧成功或旧时间。原CSRF403仍原样重试。旧两源默认live/5页、幂等重试/新轮次、单页状态与原无权行为保留。

修改前已执行官方WSL CBM0.11.0 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` help/index_repository/get_graph_schema/trace_path，cache `/tmp/r06-source-admin-cbm`，project `r06-source-admin-src`，只索引本WT frontend/src（fast、不持久化配置）。baseline图292nodes/1090edges，21测试文件按fast规则未索引，未索引secret/.env/holdout。collectSourcePage入站3调用方：runRequest一跳、submitCollection二跳、SourceAdminWorkspace二跳，图证据后用rg复核App→SourceWorkspace→runRequest。原始CBM文件修改时间20:59:17至20:59:27+08，仅作实际artifact时间，不冒充缺失的命令起止计时；原输出见cbm_help/index/schema/source_callers。

实际验收（所有npm cwd `D:/wt/r06-source-admin-ui/frontend`；+08:00秒级起止与exit原JSON保留）：

| 命令 | 实际时间 | exit / 结果 | 日志 |
| --- | --- | --- | --- |
| `npm test -- --reporter=json --outputFile=../reports/runs/recovery_r06_source_admin_ui_20261015/unit_final.json` | 21:13:30.884至21:13:52.457 | 0；339/339，24文件，0fail/0skip | unit_final.json/log/command.json |
| `npm run typecheck`（代码冻结后） | 21:21:20.037至21:21:23.010 | 0；strict | frozen_typecheck.log/command.json |
| `npm run lint`（代码冻结后） | 21:21:20.015至21:21:22.255 | 0 | frozen_lint.log/command.json |
| `npm run build` | 21:13:30.919至21:13:35.434 | 0；tsc+Vite，50modules | build.log/command.json |
| `DIANZI_E2E_FRONTEND_URL=http://127.0.0.1:25404 npx playwright test --config=../reports/runs/recovery_r06_source_admin_ui_20261015/playwright.config.ts` | 21:15:51.915至21:16:02.757 | 0；Edge8/8，新4+原4，0fail/0skip | e2e_visual.log/report.json/artifacts |
| 同上追加 `--grep catalog` | 21:18:48.410至21:18:56.806 | 0；新增4/4，补验reduce后animationName=none与2px焦点轮廓 | e2e_accessibility.log/report.json/artifacts |
| `git diff --check -- frontend/src frontend/e2e docs/design/recovery/R06-source-admin.md` | 见commands.jsonl | 0 | source_diff_check.log |

339包含原305不削断言，加catalog16与UI18。原source DTO25/client10/workspace22全通过；目录key/category/content_scope与后端源文件逐项一致，九POST同源不同key。新增覆盖首次未知无IO、负key、选择无POST、显式提交、429同body/key重试、503/partial、切源/新轮清旧状态、服务403、退出/role撤回晚到200。原四Edge无修改：1366/390原两源幂等与PG状态、role/lateCSRF、401。浏览器完全拦截/v1，未连接来源或PG，不计真实integration/live。

失败与仪器修正均保留：catalog_red exit1为新模块/export尚不存在的收集失败（非业务断言已执行）；catalog_green15pass/1fail因jsdom import.meta URL不能供node fs读取，改为固定cwd路径并保留日志。type初次exit2为测试中误用Testing Library不支持的exact参数3处，移除后默认精确名称断言保持。Edge首次exit1为run目录无法解析@playwright/test，配置改为复用原config；第二次5pass/3fail为重试点击后过早读取request数组（改等待受理）及错误导航名（按真实label），不改产品文案或削断言。e2e_report.json/error-context/失败run已生成的初始截图与首次日志原样保留。相对reporter输出曾落本WT错误目录，已按SHA原样移动至own run并记录artifact_path_correction.json；现配置绝对输出。fullPage在已滚动页面捕获固定隐藏skip-link的中间截图伪影，保留e2e_final_artifacts，再回顶截图验证；未改全局CSS。原生日志末尾空白不清洗，源码/设计diff检查单独通过。

实际实看四张截图：e2e_final_artifacts的catalog-fixture-initial-1366/partial-390，e2e_visual_artifacts的catalog-fixture-partial-1366/390（后两张以original分辨率看）。末版accessibility截图保留供独立review，不冒充已实看。桌面分类目录与提交/查询双栏，手机单列，文字/key/任务UUID不溢出；背景低亮且不拦点击，reduce停动，选择聚焦表单可键盘Enter提交。partial显示错误码、未知来源与独立PG时间/收到快照时间；截图均标合成Fixture，不假装live。Node24.13.1/npm11.8.0，node_modules复用本机原锁安装的junction，锁SHA256 `79E4DF46C6646AB2D878B8BAEAA9985AB44A1C802A0F47C950EE1869A4CB8C61` 不变。

计划/合同偏差：未新增后端合同或API；不自动轮询，保持原手动刷新。时效合同缺TTL时明确未知，不发明过期判定。评分证据仅支持九源管理界面、固定提交合同与隔离边界/回归；九来源实际采集/持续监控/覆盖分母/风险确认不由本切片证明。真实模型、付费API、秘密、holdout未触及。

交接：主控取code/meta提交，在完整新worker/API就绪后运行真实9key/PG/浏览器链路；安排全新非作者初审，以冻结SHA和raw日志复验。作者完成此有界包即释放槽位，不继续扩范围。
