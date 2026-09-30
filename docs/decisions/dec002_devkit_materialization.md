# DEC-002 · 开发包物化（决策落实记录）

决策来源：项目负责人 2026-09-30 指令（T01 续执行提示词 §5）。执行明细与逐文件清单见 `reports/acceptance/devkit_materialization.md` 与 `reports/runs/t01_materialization_inventory.json`。

## 决策内容

1. 开发包由单文件拼接阅读版物化为独立文件，落入 `D:\dianzi` 内包声明的相对路径；根目录完整阅读版、首次执行提示词、官方 PDF 原件、AGENTS.md 均保留不动。
2. 原 ZIP（`赛题九_Agent工程开发包_20260930.zip`）未在项目目录出现 → 按允许路径仅从完整阅读版拆分（99 分节），并记录 ZIP 缺失的影响：无法复用其原始 `contracts/*.json` 结构与初始 progress 模板，T01 生成的 JSON 结构与 ZIP 存在字段差异风险，ZIP 补入后须先比对结构再合并。
3. 落地规则执行结果：98 创建、1 跳过（`AGENTS.md` 仅换行差异，保留现有文件）、0 冲突；13 个非 Markdown 文件剥除展示围栏；Markdown 内部围栏保留；PDF 副本 `docs/references/competition_brief.pdf` 与原件 SHA-256 一致。
4. `progress/`、`reports/`、`docs/decisions/` 既有内容未被模板重置；T00 状态与证据原样保留。

## 后续约束

- `.bootstrap/`（暂存目录 + `split_devkit.py`）为本轮核验用临时内容，不得进入版本库、不得当作产品代码。
- 物化文件属开发包文档；与既有文件的任何未来差异处理仍遵守“不同则报告冲突、不自行选择”。
