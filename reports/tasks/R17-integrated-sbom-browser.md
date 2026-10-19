# R17 · 已审 SBOM 工作台与默认 API 浏览器集成

状态：本有界切片 `awaiting_review`；实现 `complete`。整 R17/T42/G-E 保持 `partial`，不得据此登记 accepted。作者 `/root/r17_integrated_sbom_browser_workbench_implementation`，未再 spawn。

工作树 `D:/wt/r17-integrated-sbom-browser`，分支 `codex/r17-integrated-sbom-browser`。固定基线 `17ab90e0a6b100530a3078dd525f9086813c9728`，源码提交 `4a17fa3fb7357a8c2b9d647f62c875958a24a27d`，源码 tree `c5d3f2642f64ca00952aa70491e2ad2e8a3b846c`。本报告及材料提交另由 Git 记录，不把作者提交当独立验收。

## 范围与实际改动

仅改两个获准产品文件：`frontend/src/features/assets/sbom-detail.tsx`、`assets.css`。新增 `frontend/e2e/r17_integrated_sbom_api.spec.ts` 及直属 `helpers/r17-sbom-inputs.ts`、`helpers/r17_sbom_control.py`。其余新增文件限本报告和 `reports/runs/recovery_r17_integrated_sbom_browser_20261016/`。

固定快照 SBOM 新增六类声明的页内导航，数量直接来自当前 typed sidecar 数组。按钮将键盘焦点移到相应固定快照区段，立即滚动，不修改 App hash 路由。组件来源以同一固定 snapshot 的 component_id 查找已保存组件名称，保留类型、引用、UUID、字段位置和 checksum 声明。没有计算风险、版本真值或依赖完整性。

复用 `AssetDetail → SnapshotView → SbomDetail → getAssetSnapshotSbom → fetchJson → parseSnapshotSbom`。独立 CBM 宽 frontend 索引明确排除 assets；另建窄 assets full 索引，实际 trace 确认以上调用链和安全 parser。`asset-client.ts`、`asset-contracts.ts`、`sbom-contracts.ts`、导入/详情、认证、默认后端、迁移、公共 schema、依赖锁及原测试未改。按源码提交核对固定17ab实际58个原前端测试文件及受保护文件，全部 Git blob 不变；5587与17ab按.test/.spec枚举都是58且集合相同。任务提示的57与这次枚举计数有差异，保护范围取全部58，不删任何原用例、不改测试分母。raw 与 Git LF SHA 分别保存于 `source_proof.json`。

主工作区用户 `D:/dianzi/frontend/tsconfig.tsbuildinfo` 全程只读，前后 SHA256 都为 `3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d`。编译只在本工作树；自己的 buildinfo 已恢复 HEAD 字节。没有 push、公开发布、修改生产/开发 DSN、下载模型、运行 PoC 或第三方资产访问。

## 设计审计与取舍

读取 AGENTS、00 execution map、R17 恢复卡、T41/T42/T43、03/04 合同、R11 sidecar/default reader 变更、当前状态、R11 默认 API privacy 复核、R17 SBOM Must1 非作者复核，以及用户外部 ui-design.md。后者只作参考文本。

应用 Ponytail 5.2 full；design-taste-frontend 按用户要求采用审计与渐进改造部分。该 skill 明确排除密集产品 UI，本轮未套用营销 block 或引入 UI 依赖。设计读法是防御情报人员使用的高密度资产工作台；preserve 模式，variance 3 / motion 2 / density 8。延续近黑炭色、青绿主强调、琥珀未知/限制、系统中文字体、Consolas 数字、方角资产工作区、44px 操作目标。

实际在 CUA 打开并展开 [Elastic Timeline 官方截图](https://www.elastic.co/docs/solutions/security/investigate/timeline)，观察查询栏、字段侧栏、表格与行内上下文；参考其保留列表上下文和可追溯详情的层级。未下载/复制竞品素材。另读 [OpenCTI Cases 官方文档](https://docs.opencti.io/latest/usage/exploring-cases/)，未单独审看其截图，不声称有该视觉证据。临时 CUA 页已关闭。

改动前实际 Edge fixture 渲染 6/6，查看桌面与 390px 原始 PNG。现状可以保留：列表/详情分栏、版本时间和未知、私有清单标记、文本证据、局部横滚表格。需改善：多段 SBOM 很长，组件来源只用 UUID，不便回读组件；因此只补导航和名称对应。现有共享 ambient 背景已满足克制动效，未扩展 ownership。真实 API 浏览器中实际采集两帧并断言 transform 改变；reduced-motion 下 animationName 为 none。未把动效当监测或 Agent 进度。

## 默认应用、资源与真实性边界

真实浏览器为已安装 Edge，访问本工作树 dist 的 Vite preview `127.0.0.1:26773`，同源代理到自有默认 Uvicorn API `127.0.0.1:28773`。正常调用 `create_application(settings=...)`，不注入 auth_service、不 monkeypatch engine/业务方法、不 `route.fulfill`。

应用配置 `app_env=test` / `data_mode=fixture`，七个随机合成账号、各自租户、真实密码校验、HTTP-only Strict Cookie、CSRF 和 PG 会话。资产目录显著显示“合成 Fixture · 非真实资产”，名称为 Synthetic browser 授权测试清单；测试数据不与真实来源混记。所有资产操作使用实际 `/v1/asset-imports`、资产列表/详情/历史/fixed snapshot/SBOM 路由。

自有标记数据库 `test_dianzi_r17_integrated_sbom_browser_20261016`，授权测试 PG loopback25432，正常 forward migration 到 `public / 0022_sbom_sidecars`。未执行 downgrade 或业务 create_all。DPAPI 仅由指定 pwsh7 子进程在 runner 内存读取 `TEST_DATABASE_URL`，核对原 test 数据库/账号/端口后派生自有数据库。DSN、密码均未进 argv、报告或截图。

原生默认 factory 自己拥有并关闭其 engine；bootstrap、控制与 audit engine 使用自己的 NullPool 并 dispose。503 注入只将本库唯一 SBOM 表临时改名，所有实际路径通过 finally 恢复；不禁用不可变 trigger、不改历史 payload。loading 使用本库短暂独占表锁，真实查询等待三秒后释放，不伪造响应。角色降为 viewer、会话 revoked_at 更新只作用于本次合成账号。

每轮后台 API 的 PID/launcher parent PID、nonce、+08 boot/shutdown、来源路径及端口保存；Windows 实际 SessionId=1，与本 runner 一致，未把它谎称为 0。最终自有 PG 其他连接数为 0。后台进程使用 CREATE_NO_WINDOW；正常 stdin stop、Uvicorn lifespan 完成、API exit0；未 kill 别人的服务。

## 最终六例的实际输入与可观察证据

| 用例 | 实际行为与断言 |
|---|---|
| R17-API01 | 真登录后 200 空目录；浏览器上传原 CycloneDX UTF-8 File，POST201；PG raw_input SHA 与上传输入相等、public0022；typed sidecar 原文 hash、npm scoped purl、组件名称/类型、关系字段位置可读；六声明导航用 Enter 将焦点移到固定 section；相对/URI 字段被 redacted-field 隐藏；真表锁下 loading 可见 |
| R17-API02 | 另一认证租户对 API01 fixed sidecar 得404，无 component_sources/tenant_id/private title；自身 SPDX POST201、标准 DESCRIBES 与 purl 可读；只检查公开 HTTP href，不联网打开；file URI 为 null/隐藏说明，危险 href 与原值均不在 DOM |
| R17-API03 | UI 同一路径追加 1.0、2.0、无版本三快照；原先错误的 PURL/version 冲突输入另以同 API 验证422；历史固定原 hash/空关系保留，reload 恢复当前；真 API 再追加第四快照，仅刷新历史时显示 REVALIDATE 和“当前指针需要复核”；刷新资产切到 #4、旧警告消失；原 #2 历史关系仍可读；外部观察/研判/VEX 入口准确未就绪 |
| R17-API04 | 自有表改名后 actual sidecar GET503；已取得的快照和组件可查看，sidecar 未显示旧 hash；恢复原表并点重试，GET200、同原 hash恢复，无伪造安全结果 |
| R17-API05 | 显示资产后真实 PG 角色降为 viewer，第一个资产请求403触发清空列表/历史/上传 DOM；另一真实账号会话撤销后第一个资产请求401、认证代次清除、私有 DOM 不恢复；local/session storage为0 |
| R17-API06 | 真 API 保存25组件；390px 页面无整体横溢出，组件20→5分页由 Enter 操作；声明区焦点正确；reduced-motion 无动画；正常 motion 两帧与 transform 改变证据 |

最终保留 26 PNG（13 full-page + 13 viewport）、6份只记 path/method/status/时间的 HTTP flow、9份 PG raw-upload 核验 JSON及原合成上传字节。Cookie/请求 header/密码不写 flow；视频、trace和失败自动截图关闭，避免留登录秘密。agent 已查看真实桌面、mobile viewport、stale 指针、503/撤销截图；它不是人的最终人工验收或连续操作录像。

原截图和失败上下文不覆盖。最终原件在 `actual_edge_7_stale_artifacts/`；上一轮完整 green `actual_edge_6*` 与所有 red `actual_edge_1–5*` 分别保留，不能相加为12个新业务用例。

## 实际检查与失败记录

命令 cwd 除 Python runner/材料脚本为本工作树根目录，npm/Playwright 均为本工作树 frontend。解释器为 `D:/dianzi/backend/.venv/Scripts/python.exe`；Node/npm 为已安装 Node24。完整 argv、+08起止、exit、HEAD 在同 label receipt；最终源码身份由 source_proof 绑定当时 dirty source，commit没有改变文件内容。

| 检查 / 命令 | +08 起止 | 结果 |
|---|---|---|
| 改动前 fixture Edge：node playwright CLI，playwright.before.cjs | 见 edge_before_fixture.json | exit0；6/6，0fail/skip/flaky，仅视觉 baseline |
| npm run build | 见 build.json | exit0；本树 dist生成，不计业务测试 |
| npm run test -- --reporter=json --outputFile=.../unit_all_3_result.json | 10:44:08.213–10:44:42.520 | exit0；原557/557，0fail/pending/suite error，含原8 serializer cases |
| python browser_runner.py actual_edge_6 | 10:48:57.364–10:49:23.452 | exit0；actual default API/PG/Edge 6/6，0skip/flaky；此轮未单独诱发 newer-history pointer |
| python browser_runner.py actual_edge_7_stale | 10:51:20.078–10:51:52.461 | exit0；原六用例加真实 stale pointer 仍6/6，0unexpected/skip/flaky |
| npm run lint / npm run typecheck | 10:51:57.822–10:52:01.739 / 10:51:57.815–10:52:02.100 | 各exit0 |
| material_seal_final_2 | 见 material_seal_final_2_command.json | 固定基线实际58原文件（40 unit+18原E2E），公共边界、source/raw archive、557/6/26实际数量核验 |

首个 fixture 启动误用 npm exec，参数未透传，误跑默认 E2E；exit1日志保留 `before_fixture.log`，不算产品失败或通过。其误生成的本WT默认R01 e2e_report/e2e_artifacts 经 git未跟踪、非reparse、绝对路径仍在本WT等检查后，原字节搬到 own run `misconfigured_default_e2e_raw/`；原R01已跟踪日志/截图不动，主工作区不动。25173/26773/28773最终监听均0。后改用已安装 node 的精确 CLI/config，实际6/6 baseline。

首次 unit reporter结果被同名 command receipt 覆盖，原exit1/日志仍保留，数量不可恢复，未编造。第二次可读结果为549 passed、0 failed tests、1 suite ENOENT；原因是 Git17ab缺原8 serializer依赖文件。原测试没修改、没 skip。恢复原冻结字节后第三次557/557。

运行器前两轮未进 browser：Windows venv launcher与实际服务PID不同；最初错误假设SessionId0，后来定位为 PID ancestry/readiness 问题。两轮 API都正常停机，原 boot/shutdown保留；早期初始化/read-only命令及这两次未单独结构化的启动起止不补造。另同进程 migration 的闲置池在 runner退出前留1连接；改为有限子进程运行正常 run_migrations，最终连接0，不 monkeypatch factory。

实际 Edge3为0/6：Edge File 请求的 postDataBuffer() 不提供字节，错误的零buffer fallback断言全部失败。此检测不再把null当空文件；相同原上传字节使用PG raw_input核验，wire是否可读单列，未宣称取得不可用的wire bytes。

Edge4为3/6：marker正常出现在未映射和隐藏说明两处，单元素 locator失配；第二版本与旧purl版本冲突导致422，后明确保留冲突输入为拒绝分例，并生成对应合法2.0输入；退出按钮只在会话页，测试未导航到会话页。Edge5为4/6：404 Problem.instance合法回显已经由请求给出的ID；撤权时detail403先到并取消list请求，错误等待list响应超时。最终针对真实拒绝状态/对象清空断言，私有payload仍禁止泄漏。所有相关原spec/输入、PNG/上下文/log均保存，未改金标、分母或后台合同。

材料 seal 首次因 Windows 默认GBK读取UTF-8 reporter失败，保存 seal_v1_frozen.py；v2明确UTF-8读取，未改产品断言。v2只枚举40个unit文件，最终材料检查补入所有原E2E；错误硬编码57导致一次材料exit1，真实git ls-tree显示40+18=58，原5587集合亦为同58文件。最终保护全部58原文件；测试通过分母仍557与6，未改任何业务期待。前一次40文件proof与原archive另存。早期执行命令的结构化记录缺口与 reporter覆盖如实保留，不把它们补写成全程无失败。

## 原8 serializer fixture 的新鲜 Git 依赖

原材料 `5587deb124f06b9aa14fb7feb22cdc9493ae4883` 中路径 `reports/runs/recovery_r17_sbom_workbench_20261016/backend_contract_samples.json`，blob `82c40263274fb65517037ab5e3f2d3982f151d67`，raw SHA256 `92f5a0cac56ccd97c63af16bd14418cbc1c42cf4803c3ab6627f419235a6e331`。本轮从固定 reviewer 路径复制，另通过 git show核精确blob/raw字节；原8cases期待的 backend_material_sha仍5be873，未用新实现生成新金标。原文件精确备份为 own run `backend_contract_samples.original.json`。

该原路径不在本source5files范围，交root显式恢复到主控相同path，才能让freshGit直接npm test复跑。此处557通过明确依赖原8 fixture已挂载，不将Git17ab无资源状态称为557可复现通过。

## 合同与原验收覆盖

不修改公共合同、认证权限、指标分母、枚举或计分；不为不稳定接口创造前端API。原 T42六验收完整保留：C01不同版本的真实影响判定仍not_run；C02本切片证明缺版本/来源版本unknown，未知观察时间仍按现合同禁止提交；C03只证明未接通外部入口不伪造修复，真实FOFA外部不可达判断not_run；C04真追加保持新snapshot与旧历史，但研判重算/job关联not_run；C05真实当前指针待复核passed，assessment freshness/stale not_run；C06真实导出未就绪限制passed，权限/映射/OpenVEX实际导出not_run。不能用snapshot差异替代四态判定。

原 T41 C01–C06与T43 C01–C06未由本资产/SBOM切片验收；无事件多源归并/修订原文引用、多轮回答、长Agent任务恢复/取消、订阅推荐或三插件入口的新增通过证明。真实来源、模型、FOFA、多跳问答、付费调用、持续运行、正式金标评分/性能和人的人工验收/连续录像均not_run，整R17不complete。

有限评分证据：F2/F3为授权私有清单与固定typed声明、历史/raw摘要/定位/未知与权限边界；D2为桌面/390px/键盘/动态背景与明确未就绪操作；E1/X1为默认factory/cookie/PG0022/撤销与恢复。没有登记正式准确率、时效或性能数值。

最终资源审计：actual_edge_7_stale APIexit0、lifespan完成、ownPG连接0、两端口0、原SBOM表存在/临时名null；205个文本文件精确授权DSN/当前随机密码扫描0。所有该轮密码仅内存SecretStr，异常只输出类型；flow不保存headers/响应cookie。主用户buildinfo原SHA不变。自有测试数据库保留marker供非作者有界复跑，没有drop或终止其他会话。

下一步由root提交原8 fixture依赖并派 NEW非作者 reviewer，在新工作树复跑当前source与raw材料。后续R17切片继续接已冻结的研判/导出、真实问答Agent、推荐及插件接口，原六验收、live阻塞、阶段门不删。
