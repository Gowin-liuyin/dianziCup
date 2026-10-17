# G-E · R17 权限工作台三 P2 定向复核

任务：R17-permission-workspace-review-1-recheck。**限定 Ship：原三 P2 在本文冻结、受控、无标准输出 override 的调用范围内关闭。** 此结论只接收两个验收仪器文件；不签真实浏览器、整 R17/T40–T44 或任意 Playwright 输出参数。没有写 accepted 或更改状态。

本次变更行为：调查详情和 POST 监听对齐实际 `/api/v1` 路径；匿名请求监听覆盖现有14类业务首段；每组输出由唯一 run ID 原子预约，正常重用旧组明确拒绝，合法 loader/worker 可继承同次预约。

## 版本、范围与依据

- 本次 source：`4fa72a27562ddd37d1344cec80939fa186b2e254`。
- 作者 material：`1b73b4450950c5bc9b0f6b7d759465188bbdc44f`。
- 父源码：`5af9ef34dd2a82778cbac13a16b277ded77ef9c3`；首次 material：`7afaa55d24ab5efbef6b63185282acf1322292b2`；原 needs_changes 独审：`9d9df693a0ca6e3430bfcf85223f9ddcaccd791a`。
- 新独立 cleanWT：`D:/wt/r17-permission-review1-recheck`，`codex/r17-permission-review1-recheck`，初始 HEAD 为本次 material，初始 status 为空。
- 只审 `frontend/e2e/r17-real-workbench.spec.ts`、`frontend/e2e/r17-real-workbench.config.ts`。对5af的frontend diff仅两文件；权限组件/直属测试、App和public client Git字节完全未变，SHA在ownrun `final_evidence.json`。
- 读取新版 [Ponytail review 5.3.1](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.3.1/skills/ponytail-review/SKILL.md)、AGENTS、execution map、R17卡、T40–T44原验收与合同、task_state、新旧作者报告和原独审。整R17仍in_progress/partial。
- 新增本报告及 `reports/runs/r17_permission_workspace_review1_recheck_20261017/` 独占材料；未改两个源码、业务/合同/依赖/state/金标/秘密/holdout，未push。不导入新branch相对7af显示的旧材料缺席为删除：Root只接收两源文件与明确新材料路径，原7af/9d报告、raw、红记录保留在原branch/工作树。

## 三 P2 的实际闭合证据

| 原问题 | 复核 | 证据与边界 |
|---|---|---|
| 1 U09错误URL | 关闭，限定仪器 | spec:9–14、:140、:142，详情精确 `/api/v1/investigations/{jobId}`；POST覆盖create/cancel，排除GET、旧前缀、其他job、tool-runs和同名后缀。实际client:4/14/17/24对齐；9原callback保留。真实四状态业务尚未运行 |
| 2 组输出覆盖旧证据 | 关闭，限定默认受控参数 | config:38–54、:66–67，唯一ID+非recursive mkdir预约，reservation在artifacts之外；首次实际Playwright collect0，同ID真实Node exit1/EEXIST，前组results SHA未变；第二个新组collect0也保留前组SHA。未执行cleanup破坏性试验 |
| 3 匿名监听漏实际URI | 关闭，限定匹配器 | spec:6，14首段对应现有clients；静态来源清单14/14匹配、独立146边界断言通过，两前缀/集合/斜杠/子路径/query可识别，auth/health/类似后缀不误报。真实匿名页面还未运行 |

14首段为 events/evidence/documents/questions/answers/sources/jobs/assets/asset-imports/assessments/investigations/subscriptions/recommendations/reports。来源路径与literal anchor完整列在 `inventory.results.json`；`knowledge-client.ts` 的eventPath固定kind覆盖evidence，图谱归events，snapshot/SBOM归assets，推荐/报告由实际 `/api/v1` prefix构造。这里是**实际客户端源码URI清单与离线谓词验证，不是HTTP结果**。

两个输出组的第一组 results SHA256 均保持 `47a26225c62aa6f60dfa792e48cec2d2925d3fa50267370eaa5cc7ef7bef68d7`。`browser-list-reuse.command.json` 真实child exit1、failure=null，harness只有确认预期拒绝和原SHA不变才exit0；不把Node拒绝洗成Node通过。两组collection JSON与reservation已复制到ownrun，原组目录仍保留于本独立工作树。

worker预约除作者72的PID负例外，新增实际Node子进程验证：owner10048、child55364、实际PPID10048，outputDir与owner相同；同owner重新import成功、真实child继承成功、错误nonce真实child exit1，3检查通过。reservation前后SHA256均 `ddd46e2a367078ef74fcbeefec6d36ed999ecee190df37f3b1efef66ecca6683`。这证明真实Node父子身份路径；**没有执行Playwright业务worker或Edge**。

本机Playwright1.64.1调用链也已读：runner:1918–1926直接fork、复制process.env；common:1277–1290与worker entry:1480重新loadConfig。新nonce+owner PID/PPID与该正常链一致；72仪器另覆盖错误parent、非法ID、路径和junction。未发现默认合法loader/worker被拒的源码问题。

## 未封闭的标准输出 override 边界

不能把本配置宣称成任意Playwright参数的输出安全边界。本机 `common/index.js:589` 优先采用 CLI `--output`；`runner/index.js:1538` 优先采用 `PLAYWRIGHT_JSON_OUTPUT_FILE`。若操作方主动把这些值指向旧组，标准runner会绕过config中的新组artifact/results位置，旧文件可能被清理/覆盖。该源码优先级已确认，动态破坏性复现未运行。

本轮及作者交接中的固定受控命令均未使用 `--output`，实查三个 `PLAYWRIGHT_JSON_OUTPUT_FILE/DIR/NAME` 字段presence=false（不打印值）。这些override不在本切片明示的RUN_ID/OUTPUT_ROOT接口中。因此原三问题在该受控调用中关闭，**不对带override的调用给Ship**。Root预约实际组须继续使用冻结配置的两个输出字段；若要支持任意标准CLI/JSON override仍保证保全，需要新增拒绝/绑定检查与旧文件保留负例。此限制明确留给Root，不静默扩大本两文件复核范围。

## 独立命令、实际退出码、数量与起止

cwd=`D:/wt/r17-permission-review1-recheck`；PowerShell7 `login=false`，实际入口：

```powershell
& 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' 'reports/runs/r17_permission_workspace_review1_recheck_20261017/run_checks.py' instruments
& 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' 'reports/runs/r17_permission_workspace_review1_recheck_20261017/run_checks.py' inventory
& 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' 'reports/runs/r17_permission_workspace_review1_recheck_20261017/run_checks.py' worker-reservation
& 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' 'reports/runs/r17_permission_workspace_review1_recheck_20261017/run_checks.py' inventory-final
& 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' 'reports/runs/r17_permission_workspace_review1_recheck_20261017/run_checks.py' browser-list
& 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' 'reports/runs/r17_permission_workspace_review1_recheck_20261017/run_checks.py' browser-list-reuse
& 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' 'reports/runs/r17_permission_workspace_review1_recheck_20261017/run_checks.py' browser-list-group-two
& 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' 'reports/runs/r17_permission_workspace_review1_recheck_20261017/run_checks.py' typecheck
& 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' 'reports/runs/r17_permission_workspace_review1_recheck_20261017/run_checks.py' lint
```

所有Node精确argv/cwd、source hashes、起止、退出、完整birth-aware Win树和Native Job查询在同label的 `*.command.json`，原stdout/stderr未洗。

| 检查 | 时间 2026-10-17 +08:00 | 真实child exit / 数量 | Win峰 |
|---|---|---|---|
| instruments | 08:55:53.248–08:55:53.810 | 0；72passed/0failed/0skip | 4 |
| inventory初次仪器 | 08:57:15.962–08:57:16.410 | 1；我自己的anchor写错，未完成清单 | 4 |
| worker-reservation | 08:57:17.060–08:57:18.029 | 0；3检查，wrongnonce child1符合预期 | 5 |
| inventory-final | 08:58:05.496–08:58:05.827 | 0；14来源行、146边界断言，0failed | 4 |
| collect第一组 | 08:58:06.299–08:58:06.972 | 0；9collected/0executed/0业务skip | 4 |
| collect同组拒重用 | 08:58:07.471–08:58:07.973 | **1/EEXIST**；preservation harness0 | 4 |
| collect第二独占组 | 08:58:08.503–08:58:09.021 | 0；同9条，第一组SHA不变 | 4 |
| strictTS | 08:58:33.219–08:58:40.139 | 0；noEmit/incremental=false | 4 |
| 实际ESLint两文件 | 08:58:40.654–08:58:42.663 | 0；frontend cwd，0error/0warning | 4 |

最初inventory的错误是审查工具预期 `resourcePath("evidence", id)`，冻结源码实际为 `eventPath(id, "evidence")`。仅修ownprobe该anchor后以新label复跑；原exit1和stderr保留，不能记成产品失败或删掉。72、146、3均有重叠关注点，**不相加为211或另一个业务测试分母**。两collect仍是9个unique路径，不能加为18通过；JSON的skipped9是collection未执行标记，业务skip计0。

每次wall cap60s/Win完整cap10；实测4–5、guest0、remaining_owned_processes全部空。每个Job实查process memory536870912、Job1073741824、CPU833/10000×24logical=1.9992core；Node384MiB oldspace/8MiB semispace。无WSL/CBM/Edge/API/PG/模型/FOFA/付费过程。标准VM ExperimentalWarning原样保留，不能将其当浏览器通过。

CBM按Root独占分配规则**本轮not_run**，未与Source pin竞争、未新起cache或停daemon。前次9d限定图的697nodes/2726edges/56files属于旧切片且assets默认排除，不能用它签本次新增配置fs/worker链或全部前端。

## 六层状态、原证据保护与交接

| 层 | 本轮状态 | 限制 |
|---|---|---|
| 1 静态/合同 | 限定passed | 2文件源码/真实client URI/TS/实际lint；输出override不扩签 |
| 2 unit/仪器 | passed | 独立72、14URI/146边界、实际Node预约3；原143fixture未复跑、不累计 |
| 3 PG/API integration | not_run | 无资源窗口与账号、未启动或连接 |
| 4 真实浏览器e2e | not_run | 仅collect，原9callback从未执行；加载/空/权限/partial/stale/人工待处理六状态全部未新实测 |
| 5 live/性能/持续运行 | not_run | 无模型/来源/FOFA、6h、CoreWebVitals或完整问答延迟 |
| 6 独立/人工 | 定向独立completed；manual not_run | 不签整R17、原T六案例、U01–U13、人工双核或录像 |

ownrun `final_evidence.json`绑定source/material及真实数量；`raw_material_manifest.json`保存原bytes/CRLF/SHA，GitLF规范化不代替原执行hash。旧needs_changes报告raw SHA256 `1f362ed67cdd22916999286e6534177cb417a53db6c8ad387143f27560faa7c7`、旧证据 `d0a6e0fdc8d22aacc2b4b05b1d2d4a8c55de5b2aad998c847acb39dca7a72544`，仍在原独立工作树；此次没有改它们。Root tsbuildinfo仍 `3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d`，没有tsc-b。

限定两个源码diff检查exit0；本次新材料完整暂存 `git diff --cached --check` exit0，原初审/作者Vite原日志的末空行记录没有被改写。ownrecheck报告/run三类明显密钥pattern检查exit1=0匹配，只是限定扫描，不是全仓秘密门。独立运行生成的预约/sentinel/junction目录在本工作树 `reports/runs/r17_real_workbench_e2e_20261017/` 作为未跟踪自有产物保留；未stage其中产物，不将它们冒充源码或真实浏览器结果。

评分证据只限F3/E1/D2验收仪器的URI监测与证据保全；不提高完整F1/F2/F3、P3、正式分母或全部U。无公共合同、阈值、金标和计划变动。新recheck保留原失败历史，由Root依证据登记状态，本reviewer不写accepted。

下一步：Root精确接收这两个source文件与新材料，在无标准输出override、每组新RUN_ID及预约资源的固定调用中执行原9路径。服务origin/身份只内存注入/固定event-evidence-revision/空query/四持久调查状态/真正业务拒绝answer仍须Root提供。真实PG/API/浏览器必须另取独占授权；本复核不代签、不自行继续。

Verdict: Ship，限定上述受控仪器调用。Not checked: 标准输出override动态覆盖、真实Playwright业务worker/Edge、PG/API、CBM、外部live、性能、完整R17与人工验收。
