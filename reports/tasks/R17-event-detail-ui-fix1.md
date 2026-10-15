# R17 事件详情 UI 初审 P2 修复

状态：`awaiting_review`；本修复实现 `complete`，整 R17 仍 `partial`。基线 `e594cbbcaf82a0ccc36fc0b1cd9f4988da330127`（原代码 `c5ad9de9d31a28f927d45dcbd4589fa840a9101f`），修复源码 `592b49d6920a4b25db094212eab1d74ca964b1c2`，工作树 `D:/wt/r17-event-detail-ui`。仅修初审 finding 1；不修改共享 App/CSS/API/合同、依赖、后端、进度、原测试阈值或 fixture。原 review 与原作者 run 不覆盖。

已读初审 `D:/wt/r17-event-detail-ui-review-1/reports/reviews/recovery/G-E-R17-event-detail-ui-review-1.md`、原始 probe、当前 R17/T41/状态/交接与执行索引。沿用已读 Ponytail full 与项目设计合同，不重做研究。输入为相同事件 `10000000-0000-4000-8000-000000000001` 与同一 CVSS 按钮，390×844；输出为实际 action 触达高度≥40且原 Enter/focus/hash 行为保持。

修复前复制原独立 probe 到本轮 run，以原断言/fixture 和本工作树组件复跑；01:12:26–01:12:30+08:00，exit1，2passed/1failed，唯一失败 `Expected >=40, Received 24`，metrics minHeight=0px。原始 stdout/stderr/JSON/图片保留于本轮 run 的 original 快照，不移动或修改评审 WT。

改动只有 `frontend/src/features/events/events.css` 的两处 min-height：默认40px，≤640px44px，与现有移动阅读操作相同。直接回归扩入自有 `frontend/e2e/r17_event_detail_fixture.spec.ts`：1366/390 的全部新增断言按钮实际 bounds/computed minHeight，CVSS按钮 Enter 后目标断言 focus 和 hash保持；不检查 CSS 字符串，不减低门槛，不替换原输入。

固定修复源码 SHA 后跑现有30定向、typecheck/lint/build，复跑原独立3及自有/既有7 fixture浏览器；CSS尺寸变化不影响业务/公共合同，352全套已有原作者和独立评审通过，本轮不无意义再跑。live/真实后台/外网/模型调用0，独立复核由主控原reviewer安排；不accepted/push。

## 固定源码上的实际验证

run：`reports/runs/recovery_r17_event_detail_ui_fix1_20261016/`。`commands.jsonl` 与每条独立 `*.command.json` 记录实际 argv/cwd/source_commit/上海秒级起止/子进程退出码。所有最终检查均绑定 `592b49d...`。原始 stdout/stderr 由 subprocess byte capture 写 bytes；仅本 run 的 `.gitattributes` 使用 `*.log -text -diff` 保全原字节，不对源码或其他报告设置 ignore。

| 命令 | 时间（2026-10-16，+08:00） | exit / 结果 |
|---|---|---|
| `npm.cmd run test -- --run src/features/events/event-detail-view.test.tsx src/features/events/event-workspace.test.tsx --maxWorkers=1 --no-file-parallelism --reporter=json --outputFile=<newrun/events-tests.json>` | 01:13:57–01:14:01 | 0；30/30，0fail/skip |
| `npm.cmd run typecheck` | 01:14:01–01:14:04 | 0 |
| `npm.cmd run lint` | 01:14:04–01:14:06 | 0 |
| `npm.cmd run build` | 01:14:06–01:14:10 | 0；53modules，JS267.89kB/gzip82.20kB，CSS37.79kB/gzip7.76kB；生成 tsbuildinfo 已恢复 |
| `node node_modules/@playwright/test/cli.js test --config <newrun/browser-probes.config.mjs>` | 01:14:11–01:14:14 | 0；原独立输入/门槛3/3，0fail/skip/flaky |
| `node node_modules/@playwright/test/cli.js test --config <newrun/browser.config.mjs>` | 01:14:14–01:14:21 | 0；原7用例7/7，新增尺寸/Enter检查在原两 viewport 用例内，不虚增数量 |

原独立 probe 是逐字节复制，SHA256=`999901b621a1e59f927e5937e0ad20219faf40253be2a892ac5d90207c70aa05` 与评审 WT 一致。仅本轮 config 指向本工作树服务/输出与原 grep 的3项；没有编辑 probe 或把 ≥40 改低。作者复跑原 probe 不算新的独立评审。

修复前证据：`browser-probes-original.json`、`browser-probes-original.stdout.log` 与 `browser_probe_artifacts_original/`，`2pass/1fail`、84×24、minHeight0；修复后 `browser-probes.json` 与 `browser_probe_artifacts/.../new-fact-target-metrics.json`，`3pass/0fail`、84×44、minHeight44px、青绿2px focus ring。永久 e2e 的 `fact-target-metrics-1366/390` attachments 实测每个当前 fixture 断言按钮均84×40/84×44，对应 computed minHeight40px/44px；镜像读取结果见 `target-size-summary.json`。

实际查看本轮390按钮 focus截图，布局正常，较原24px有完整44px点击目标；Enter后准确 claim focus、hash仍原事件路径通过。现有深链/刷新/局部失败/reduced-motion/文本可读检查仍通过。浏览器使用已安装同锁工具、单worker与专用 loopback25317，所有 /v1/** 精确 fixture fulfil，结束无 listener；没有真实认证/来源/API/外网请求，不操作CNNVD或其他用户tab。

## 边界与交接

源码修复范围2文件，source diff check exit0。材料局部 scoped检查 exit0；原失败自动 error-context.md 的尾空格/末尾空行导致完整新证据 staged diff exit2，保留原bytes，不能声称全证据 whitespace通过。属性只对本newrun *.log生效，不清洗原red2pass1fail或原review数据。

D2/T41-C05/R17窄屏操作：本修复证明新增断言按钮满足本仓≥40触达约定与原键盘动作，不能外推所有触摸设备、WCAG完整合规或业务live。验证：定向unit/frontend/e2e fixture passed；真实backend/live、独立修复复核仍 `not_run`。本轮352全套 `not_run`，其此前作者/独立352通过证据仅作既有回归背景，不算592版本重新执行。

无合同/计划偏差、费用或外部调用。下一步仅由主控原reviewer在新固定SHA定向复核finding1，之后主控决定此切片状态；没有作者accepted/push或完整R17完成声明。

未检查：真实后台/live、完整v3/人工复核/重判、原生hidden暂停与所有设备触控；风险与原详情切片一致。
