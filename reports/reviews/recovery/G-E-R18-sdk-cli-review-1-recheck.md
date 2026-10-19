# G-E · R18 SDK/CLI 独立初审 1 定向复核

What this change does: 修复公共 UUID/时间原始 JSON 字形边界，并让 CLI 输出完整的 ASCII 转义 JSON。固定 HTTP 操作、服务端业务真相和旧风险不确定退出 2 保持。

**Verdict: Ship，仅限当前 SDK/CLI 切片；原 Must fix 1、2 已关闭。** 整 R18、T04/T32/T35/T51 和 G-E 保持 partial，未签 accepted。未覆盖的完整协议/产品/live 缺口继续存在，不把切片 Ship 当作整个项目通过。

复核人：原非作者 `/root/r18_sdk_cli_first_independent_review`。
独立 WT `D:/wt/r18-sdk-client-review1-fix1`；分支 `codex/r18-sdk-client-review1-fix1`。
原候选 base/material `d1c30d27dee54bb7895c0860c6a3ce18ea4d4632`；本次 source `6d85742b0114cc5e304e88b2aa930755ccce9bc9`、source tree `88018597cb9bb94971edb38d90e4525f6b04a8a4`；固定修复 material/HEAD `0601f469f1a90b9061ca77f718aa845051e76641`、material tree `f043302555fcedaa2183f1c79ddf153580d8944c`。
作者 active report `reports/tasks/R18-sdk-client-fix1-material-repair.md` raw SHA256 `975d055fb5d9ebd0e5d9dae0d71971ffb9915689968da9503555744f88796257`。
本报告首次写作开始/证据截止：2026-10-16T09:34:06.831+08:00；结束见 `freeze_receipt.json`。准备阶段未采集逐秒时钟的阅读/复制命令保持历史未记录，不以 mtime 补造。正式验证全部保存实际 +08 起止、cwd、argv、退出码、计数与原始日志。

## 原两 Must fix 的关闭证据

| 原问题 | 修复位置与实际行为 | 本次非作者复验 | 结论 |
|---|---|---|---|
| 1. UUID/时间被宽松接受并改写 | `models.py:61` 先检查 UUID 连字符字形，`:71` 检查 RFC3339 文本；`:88–89` PublicUuid/PublicDateTime 覆盖全部既有 UUID/aware 字段及数组。JSON 日期路径调用原 strict AwareDatetime TypeAdapter，Pydantic 继续校验日历/时区；普通 typed Python UUID/aware datetime 正常。 | 原 65 的三种 ID、四种实际漏拒日期（原 7 红）全绿；新 46 覆盖字段/数组、JSON/HTTP、合法大小写 UUID、小写 t/z、UTC/正负偏移/+23:59、闰年、微秒、typed 输入与 naive 拒绝。原合法 99/冻结 Schema 9 同时通过。 | closed |
| 2. 非 ASCII 回答在 ASCII stdout 崩溃并退出 1 | `models.py:95` wire_json 新增兼容默认 `ensure_ascii=False`；`cli.py:71/77` 两实际输出分支使用 `True`，完整 Unicode 值由 JSON 转义保存，仍返回保守 2。 | 原 ASCII 中文 emoji 问答子进程失败用例转绿；新 11 测 ASCII/UTF-8 的 ask/check/queued、401、原始格式错、输出 sink 失败。另独立执行六个实际子进程保存 stdout/stderr.raw，每项 exit 2、完整 JSON、单个请求、无 traceback/Key。 | closed |

原输入、预期和断言未修改：本 run 中的原 65 文件与原 reviewer 文件/作者固定 WT 文件 raw bytes 三者相同；fresh Git checkout 的 CRLF 文本经 LF 正规化相同。CLI 11 也逐字复制到本 reviewer run 执行，避免 session fixture 向作者被冻结目录写新的网络收据。原 99/9 和八业务＋6 common 的 14 defs 未变。已检查 source→material SDK diff 0；base→material 对原客户端 transport/exports/99 tests、contracts/backend/progress/根依赖等指定范围 diff 0。

没有新增 Must/Should fix。此结论覆盖实际运行的失败边界，不宣称 UUID 或原文证据真实性、产品租户鉴权或所有 RFC 日期形式已经验证；继承冻结格式检查器不支持的闰秒范围仍如作者报告。

## 调用链与边界复查

已复读本 WT AGENTS、00、当前 R18 卡/进度、作者修复 diff/active report 与 144 manifest schema；沿用初审已读的 T04/T32/T35/T51、03/04/05/06/08/09、CR-R04/09、原 public_api_v2/examples、Ponytail Review 5.2。审查范围/权限未改变，仅 reviewer own report/probes/resources。

新独立 CBM narrow project `dianzi-r18-sdk-review1-fix1-20261016` 索引 fixed SDK 源：102 nodes、327 edges、0 skipped/partial/unusable。wire/CLI trace 与全调用 rg 交叉核实 `CLI main → strict input/format guards → fixed SDK POST → strict typed response → wire_json(ensure_ascii=True) → JSON stdout/uncertainty stderr/2`。图的动态调用边缺失仍由源码及原生 CLI 子进程补证，不用零入边推断没有调用。

共享 guard 只约束既有格式，没复制业务规则或建立另一套数据库真相。SDK HTTP client.py、八对象 required/extra/null/引用支持/四态/unknown 和工程 caps 保持；原 65 已亲复 JSON 重复键/非有限数/1e999、流式大小/压缩 bomb、固定 origin/path/query/port、SecretStr/env 与账户字段隔离、trust_env/SSL 配置、两 HTTP 请求 Cookie 排除、合法/畸形 Problem 含合成秘密的 repr/traceback、HTTP 200/202 union错配/204、payload cap、同键同体 fingerprint与不同体 fixture 409、POST结果未知不重发/原key、真实CLI错误3/保守2。

1MiB 同步输入/请求/响应 cap 仍是已记录工程边界；单个 huge component 可符合原 Schema但被客户端明确拒绝，不假称专用上传10MiB/10000已经实现。HTTP IO timeout 未变成已证明的全程硬截止。401/404均保持真实错误3，当前产品公开 ask/check/AuthKey 尚未接线。

## 真实测试与命令

唯一 runtime `D:/dianzi/backend/.venv/Scripts/python.exe`，限定 `PYTHONPATH=D:/wt/r18-sdk-client-review1-fix1/sdk/python`；未安装 SDK、改锁或添加根 package metadata。
版本：{"httpx": "0.28.1", "pydantic": "2.13.5", "pytest": "8.4.2", "mypy": "1.20.2", "ruff": "0.16.9", "jsonschema": "4.26.0", "mcp": "2.3.0", "tiktoken": "0.14.0"}。

亲复 **230/230 passed，0 failed/error/skip**：原 99＋原公共合同9＋原review65＋格式46＋CLI11。只执行当前 final 组合一次，不累计作者历史或重复案例，不改金标/阈值/分母/预期/skip。strict mypy4源码通过；SDK Ruff/format通过；自有 helper Ruff通过；最终源码/合同/作者材料 diff0。

counts 为 tests/passed/failed/error/skip。cwd 均 `D:/wt/r18-sdk-client-review1-fix1`；逐命令 JSON 内有完整 argv、真实 +08 start/end、exit、log路径、Python/PYTHONPATH，不用 `|| true`：

| command/receipt | start (+08) | end (+08) | exit | counts |
|---|---|---|---|---|
| [material_verify](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/material_verify.json) | 2026-10-16T09:30:34.027+08:00 | 2026-10-16T09:30:43.775+08:00 | 1 | — |
| [cbm_index](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/cbm_index.json) | 2026-10-16T09:30:34.040+08:00 | 2026-10-16T09:30:40.566+08:00 | 0 | — |
| [fix_callers](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/fix_callers.json) | 2026-10-16T09:30:34.050+08:00 | 2026-10-16T09:30:34.091+08:00 | 0 | — |
| [material_verify_fixed](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/material_verify_fixed.json) | 2026-10-16T09:31:22.583+08:00 | 2026-10-16T09:31:32.799+08:00 | 0 | — |
| [frozen230](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/frozen230.json) | 2026-10-16T09:31:22.621+08:00 | 2026-10-16T09:31:38.316+08:00 | 0 | 230/230/0/0/0 |
| [strict_mypy](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/strict_mypy.json) | 2026-10-16T09:31:22.655+08:00 | 2026-10-16T09:31:26.887+08:00 | 0 | — |
| [source_ruff](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/source_ruff.json) | 2026-10-16T09:31:22.659+08:00 | 2026-10-16T09:31:23.000+08:00 | 0 | — |
| [source_format](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/source_format.json) | 2026-10-16T09:31:22.675+08:00 | 2026-10-16T09:31:22.997+08:00 | 0 | — |
| [cbm_cli](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/cbm_cli.json) | 2026-10-16T09:31:41.720+08:00 | 2026-10-16T09:31:47.094+08:00 | 0 | — |
| [cbm_wire](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/cbm_wire.json) | 2026-10-16T09:31:41.755+08:00 | 2026-10-16T09:31:47.095+08:00 | 0 | — |
| [source_contract_diff](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/source_contract_diff.json) | 2026-10-16T09:31:41.767+08:00 | 2026-10-16T09:31:41.843+08:00 | 0 | — |
| [fixed_cli_raw](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/fixed_cli_raw.json) | 2026-10-16T09:32:34.725+08:00 | 2026-10-16T09:32:39.618+08:00 | 0 | — |
| [own_helper_format](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/own_helper_format.json) | 2026-10-16T09:32:42.364+08:00 | 2026-10-16T09:32:42.528+08:00 | 0 | — |
| [final_worktree_diff](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/final_worktree_diff.json) | 2026-10-16T09:32:45.917+08:00 | 2026-10-16T09:32:46.009+08:00 | 0 | — |
| [diff_check](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/diff_check.json) | 2026-10-16T09:32:45.951+08:00 | 2026-10-16T09:32:46.064+08:00 | 0 | — |
| [own_helper_ruff](../../runs/recovery_r18_sdk_cli_review1_fix1_20261016/own_helper_ruff.json) | 2026-10-16T09:32:45.955+08:00 | 2026-10-16T09:32:46.186+08:00 | 0 | — |

`frozen230_network.json` 实测临时自有 loopback 24 请求、12.44659 秒；独立六项 raw 复验再6请求，总30≤授权45，总各进程≤60秒/100请求。服务器只在前台探针内运行并shutdown/join停止，返回 identity 编码；零外网/产品/模型/PG/测绘/付费调用。这些是合成 HTTP/实际CLI网络fixture，不是产品 integration/live、官方效果或性能通过。

六项 stdout/stderr.raw 与 `fixed_cli_raw_observations.json` 完整保存；其中 ASCII 问答输入、服务 payload 与原失败完全相同。不是只看 `main()` 函数返回值。

## 材料字节证据与控制流历史

active144 manifest原 raw SHA256 `33c4f94a47e771408f5bf724d67135810a72a09857b89722502ae2118b78ff81`，Git LF SHA256 `86f2ef7091b87f3173a80c85797f66ba95e4dc082596954a92aed54562e3a189`。本次亲读其 `files/path/sha256/git_byte_mode` schema，逐成员核对71 `exact_raw`原始字节、73 `LF` Git正规化文本；material Git blob均与prior fresh proof一致。prior clean proof raw SHA256 `9d7db9b1996596ee96fc414aa5d23c4f1a0b9b3e9b7dfcd39de5b5555fb34c92` 已亲核，不只引用作者绿字。

作者原110原始成员在其冻结WT逐raw hash均未变；旧作者86 manifest `c381854c…`＋旧review83 manifest `03ff1575…` 共169个原raw成员逐项保护，原review report SHA `b3d9c3cf…` 不变。fresh文本checkout与历史原raw不同者如实区分，未改本WT `.gitattributes` 或重新renormalize。

自有材料仪器首轮 exit1 保留 `material_verify.json/log` 与 `independent_material_proof_initial.json`：错误使用 `raw` 而实际模式为 `exact_raw`，并把fresh CRLF文本误当历史原raw/三份raw同一。只修 reviewer 自有核验器，改为按manifest模式核验、历史raw回到冻结原WT校验、copied65 separately证明原raw一致与freshLF一致；复验 `material_verify_fixed` exit0。该红不冒充作者业务失败，也没有任何失败后commit。

作者两次材料检查失败后误继续本地 commit（旧1a/f1）、第一次 proof同名覆盖、31文件CRLF修复、57path受控renormalize/c5checkpoint的事实沿用active报告明确记录；本次fresh 144证明最终交付 bytes 可验证，不将历史改成“首次绿”。本 reviewer 未重跑历史会修改原材料的 helper，未修改旧logs/XML/raw/attrs，未提交或push。

本轮只新增本报告和 `reports/runs/recovery_r18_sdk_cli_review1_fix1_20261016/`。最终原源码/合同/进度/作者整个run/report的工作树diff为0。报告/所有新raw材料由本reviewer独立manifest封存；manifest自身及末收据排除避免自引用。

## 未检查、限制和交接

Not checked: 完整六SDK方法、正式公开REST/AuthKey发放撤销/租户ACL、RiskSummary/CLI0/1、MCP两transport/六工具/8k预算、安装wheel/发布/许可/CI、三插件沙箱/标准导出、PG真实backend/真实模型/source/FOFA/live、Codex/Claude实际客户端和人工验收。零产品秘密/holdout/vault读取，0真实凭据取得；只检查明确合成sentinel与own工件边界，没有声称全生产secret scan。

未读取或审作者MCP WIP；f17原models缺陷传播仍未取得新组合验证，不能引用本230来签MCP通过。后续如集成应在另批准组合快照按原MCP回归/新格式与raw协议实跑，再交独立review。

本有限Ship提供R18:T04/T35客户端合同修复与A1/E1/X1工程证据；不改变原R18/T04/T32/T35/T51/G-E的全部验收。建议root登记原两个Must的本次关闭与固定SHA，按剩余明确切片继续；本定向复核到此停止。
