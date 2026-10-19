# G-E · R17 事件详情 UI finding 1 定向复核

本改动做什么：仅给新增的“查看断言与依据”按钮补足默认40px、窄屏44px高度，并在原1366/390浏览器用例内增加真实bounds、Enter/focus/hash回归。事实、修订、引用及API合同均未变化。

**Verdict: Ship.** 原 finding 1 已修复；结论仅限稳定schema2事件详情UI切片，不代表整R17 accepted、G-E过门或真实业务live。未扩展风格循环、未改进度、未commit/push。

原reviewer定向复核，未参与fix1实现且未spawn。新工作树 `D:/wt/r17-event-detail-ui-review-1-fix1`，分支 `codex/r17-event-detail-ui-review-1-fix1`；材料冻结 `6472d816471a8c8ff176745d199ae4a3ef73270f`，业务冻结 `592b49d6920a4b25db094212eab1d74ca964b1c2`，修复基线 `e594cbbcaf82a0ccc36fc0b1cd9f4988da330127`。重读AGENTS、当前执行索引/R17/T41与状态、冻结只读API合同、Ponytail 5.2 review及作者fix1报告；沿用首次review的设计/业务合同，不重做研究。

实际命令窗口 `2026-10-16T01:24:38–01:25:25+08:00`；形成报告时核实上海时钟 `01:25:38+08:00`，封存时间由本run manifest实际生成。所有独立 `*.command.json` 与顺序追加 `commands.jsonl` 保存真实argv/cwd/起止/exit/SHA，stdout/stderr原字节保存。run为 `reports/runs/recovery_r17_event_detail_ui_review_1_fix1_20261016/`。

## finding 1 的直接证据

`events.css:35` 默认 `min-height:40px`，`:78` 移动规则将同一 `.dimension-fact-link` 列入44px组；只有这两处CSS和原e2e的尺寸/操作断言变化。独立原探针逐字节复制，SHA256 `999901b621a1e59f927e5937e0ad20219faf40253be2a892ac5d90207c70aa05`，仍是原事件/原≥40断言，配置仅改变自有loopback和输出路径、选取原3项。

独立390×844实测按钮 `84×44px`、computed minHeight=44px，原来的24px不再出现。原7用例新增的浏览器attachment实测两个宽度下当前5个断言按钮：1366×900均40px、390×844均44px；镜像 `target-size-summary.json` 由实际browser.json attachment解码，不根据CSS字符串生成预期。原CVSS按钮Enter仍聚焦claim，hash仍事件路径；阅读位置→旧修订引用→指定revision证据、reload与焦点仍通过。

通过view_image实际查看本run独立390按钮focus与原7用例产生的390/1366按钮viewport图片。按钮目标完整，内容和邻近观测元数据可读；独立键盘截图青绿2px焦点环仍可見，未见新增重叠/整体横溢。图片只是这两个viewport观察，不推定所有触屏或完整WCAG合规。

## 实际执行

cwd为此WT的frontend；Git/audit为WT根。Node24.13.1/现有锁依赖junction，不安装依赖。

| 真实命令 | 上海起止（2026-10-16，+08:00） | exit与覆盖 |
|---|---|---|
| `npm.cmd run test -- --run src/features/events/event-detail-view.test.tsx src/features/events/event-workspace.test.tsx --maxWorkers=1 --no-file-parallelism --reporter=json --outputFile=<newrun/events-tests.json>` | 01:24:38–01:24:42 | 0；30/30，0fail/skip，原14新增+16既有 |
| `node node_modules/@playwright/test/cli.js test --config <newrun/browser-probes.config.mjs>` | 01:24:43–01:24:48 | 0；原独立3/3，0fail/skip/flaky |
| `node .../cli.js test --config <newrun/browser.config.mjs>` | 01:24:59–01:25:07 | 0；原7/7，0fail/skip/flaky，单worker |
| `npm.cmd run typecheck` | 01:25:08–01:25:11 | 0 |
| `npm.cmd run lint` | 01:25:11–01:25:13 | 0 |
| `npm.cmd run build` | 01:25:14–01:25:18 | 0；53modules；JS267.89kB/gzip82.20kB，CSS37.79kB/gzip7.76kB |
| `python <newrun/audit_author.py>`；逐条`git cat-file blob SHA:path` | 01:25:20–01:25:25 | 0；2源码+66证据全部匹配raw或LF合同，0invalid |
| `git diff --check e594cbb... 592b49d...` | 01:25:25 | 0；限定源码diff |
| `git diff --check 592b49d... 6472d81...` | 01:25:25 | 2；原红error-context尾空格/末尾空行，原字节不清洗 |

原探针同时证明loading不泄露值/不抢焦点、empty保留9维未知、revision不匹配时无quote；原7证明历史引用/深链/reload、局部503和401、窄屏文本与reduced-motion维持。新增高度和Enter断言融入原2个viewport用例，没有将同一用例拆分虚增数量。

本次352全套为 `not_run`：fix仅私有CSS尺寸和e2e，业务组件/客户代码/合同未改，直接30+原3+原7与全type/lint/build针对变更足够；首次review在c5/e594的352通过只作历史背景，不冒充592版本重新执行。

## 字节、原红与边界

作者`recovery_r17_event_detail_ui_fix1_20261016/artifact_manifest.json`的2源码与66证据逐条对业务/材料Git blob核对。raw与LF分列到 `author-manifest-audit.json`：68行中Git raw hash匹配58行，本地raw匹配46行；其余均文本EOL差异且LF一致，0内容invalid。不是声称68行raw完全相同。每行保留expected/raw/LF hash及Git/本地字节长度，未改作者报告、原始日志、PNG、error-context或属性。

作者局部 `.gitattributes` 仅 `*.log -text -diff` 保全本fix1原始日志，不全局忽略源码；保留原红2pass/1fail/24px的browser-probes-original及其Git blob，原review工作树未修改。本评审newrun不添加属性或清洗raw。当前材料whitespace exit2如实保留，不影响已复验的局部CSS修复。

浏览器只有自有loopback25321，所有 `/v1/**` 白名单fixture fulfil。两个controlledserve均明确start/end/PID，结束listener=false；人为终止Vite进程码1与listener清理码0分别记录。0秘密读取、0真实模型/FOFA/外网、0用户CNNVD或其他已有tab操作。未用根API/真实登录；fixture不计live。新WT只有review报告及newrun未跟踪，build生成的此WT tsbuildinfo已按材料HEAD单文件恢复；业务/tests/progress/contracts未改。

unit、frontend、fixture浏览器本次passed；真实backend integration/live、原生hidden、完整R17工作流/连续录像仍 `not_run`。F2/D2/T41-C05/R17窄屏/键盘仅此操作改善有证据；不提升最终U02/U08或评分项完整验收。没有合同/计划偏差，没有新增确认finding。

manifest本体SHA256另存 `artifact_manifest.sha256`，manifest内绑定源码/材料SHA、原probe hash、作者audit和所有本review文件；封存程序验证review未改tracked内容。下一步由主控登记限定切片结论，保留整R17 partial与live缺口。

**Verdict: Ship（仅本schema2事件详情UI切片）。** 未检查：352全套、真实后端/live、原生hidden、完整R17。
