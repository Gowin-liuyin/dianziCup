# R19-preparation · 候选标注工具与公开短证据包

状态：awaiting_review。准备切片实现 complete；整 R19/T46/T01 仍 partial，未进入正式冻结或 accepted。代码冻结 `81b38d5559219d5818e6169da32cd7b98e33d392`，分支 `codex/r19-annotation-preparation`，独立 WT `D:/dianzi-r19-annotation-preparation`，基线 `0a45185ae3ffb73a6d186b98421e26a52f78bfc6`。无 push；主库用户修改、进度状态和既有报告均未改动。

## 范围与前置独立性

读取实际 AGENTS、执行索引、R19 恢复卡、progress/task_state/context_handoff、T46/T01、原数据/评测合同。恢复合同明确 R04 真实闭环后可准备工具与候选；现有 G-B/R04 只在已批准切片独立限定通过。当前 G-C 来源修复不改变本候选保存的固定公开文档/修订。准备切片不依赖后续富化、资产、问答、变化、推荐和 Agent 的实际结果，因此可安全独立开展；正式 R19 冻结仍依赖 R07–R16 与双人独立人工，不能因此越过阶段。

修改仅为 5 个新源码/资料文件：`benchmarks/schemas/candidate_case_v1.json`、`benchmarks/manifests/r19_public_dev_candidate_v1.json`、`scripts/annotation/prepare.py`、`scripts/annotation/tests/test_prepare.py`、`docs/runbooks/annotation_preparation.md`，以及本报告与本切片 run 目录。没有改 backend/frontend、公共合同、数据库迁移、认证、依赖锁、全局配置、指标阈值/分母、原金标或进度。

先固定输入输出与原 C01–C06 边界，再实施单文件 CLI 和显式 synthetic fixture 测试。复用 verify_plan.load_json 的重复键拒绝和现有 jsonschema Draft202012Validator；stdlib 处理 hash/时间/路径/CLI/独占写入。新增必要性：仓库尚无 candidate-case schema 或可运行标注导入/校验/导出入口；没有建立通用标注平台、新服务、新依赖或第二套产品事实库。

## 实际行为与数量

CLI 支持 import/validate/export/scan，实际子进程闭环可运行。保留原 case/family/data_kind/split/source_refs/source_snapshot_time/input_refs/license 字段；候选不含 expected_*。家族、稳定 alias、文档 ID 和来源 URI 跨 split 校验；重复 JSON 键/ID、路径穿越、错误 quote/hash/offset/locator、来源关联错误均拒绝。candidate hash 绑定导入/导出的候选版本。

人工记录置于仓外，绑定候选 cases hash。两份独立 ID 的标签不一致进入 awaiting_adjudication；无身份记录仍 awaiting_identity_verification，不把不同字符串当真实人员证明。裁决绑定当前两份完整记录 hash、第三人和理由；修订保留先前记录 hash、revision、原因、影响案例与复测引用。annotation 导出保存全部历史及 annotation hash，拒绝导入/导出到仓内或显式产品挂载，也拒绝任何标签导出 prompt/index/image/fixture。identity_checks 只是待独立审查的人工声明；工具最多 ready_for_manual_review，human_gold_count 永远 0。

holdout 输入/输出必须受控仓外；非 annotation 导出拒绝。扫描操作者选定的公开 prompt/镜像输入清单/index 树，检测 holdout 家族/URI/短证据及显式给定标签的论断文本；错误只打印固定码，不打印答案。独占新建防覆写和并发重复导出。统计真实计数，各种候选和状态分开；正式指标明确 numerator=null、denominator=null、status=not_run，没有标签不计分。

实际资料只读取主库 `reports/runs/recovery_r06_document_live_20261015/collection_receipt.json` 授权的 first_document/first_detail/first_history。选用第二个完整短字段证据：vLLM 公告 `GHSA-6cxc-2vcg-w5qc` 的 `/vulnerabilities/0/package/name`，精确 quote 为 4 个字符，原 quote hash、span/block、固定文档修订和 URI 均保留。标题/字段含义供人工回看；不从此证据推断完整漏洞、受影响版本、修复版本或条件金标。

当前真实规模：real/dev 1 候选、1 短字段证据、0 人工标签、0 人工金标、0 正式指标。license=unknown、redistribution=unverified，不代表转载授权。源发布时间保留原 UTC 精度，观察/准备/报告时间使用真实北京时间秒级 +08；原观察毫秒值另存构建收据，未用准备时间替代来源发布时间。没有复制整个未知许可正文，没有读取真实 holdout、答案、DPAPI、cookie/session、数据库或服务；外部调用为 0。

## 六类原合同断言

| 原 ID | 实际测试断言 |
|---|---|
| T46-C01 | 同家族的译文/修订/派生题同 split 可导入，跨 split 报 FAMILY_SPLIT_LEAK；改变 family ID 不能绕过同 URI/document/alias |
| T46-C02 | synthetic 双填表分歧→awaiting_adjudication；追加第三人裁决→awaiting_identity_verification；显式 fixture 身份记录→ready_for_manual_review，仍 gold=0 |
| T46-C03 | synthetic 与 public real 候选来源分开、计数分别为 1；fixture 来源改 real 被拒绝 |
| T46-C04 | holdout 的 prompt/image/index 导出及对应公开树泄漏非零；只有答案论断文本泄漏也非零且 stdout 不打印答案 |
| T46-C05 | 缺来源/许可/快照失败；明确 unknown 许可可通过但不得许可转载；证据 hash/offset/locator 错误被拒绝 |
| T46-C06 | 无标注 awaiting_human_label=1、human_gold_count=0、formal_evaluation=not_run、分子分母均 null |

## 真实命令与结果

cwd 均为 `D:/dianzi-r19-annotation-preparation`，Python 使用主库已锁安装 runtime `D:/dianzi/backend/.venv/Scripts/python.exe`。精确 argv、开始/结束、退出码见 `final3_commands.json`、`final2_commands.json` 和 CBM 各 run 收据，日志均位于 `reports/runs/recovery_r19_preparation_20261015/`。

| 命令 | 开始 / 结束 +08 | exit | 结果 / 日志 |
|---|---|---:|---|
| WSL 官方 CBM v0.11.0 scripts fast、persistence=false | 22:02:36 / 22:02:40 | 0 | 初索引124节点425边；cbm_before.json/run |
| python build_public_candidate.py | 22:12:02 / 22:12:02 | 0 | 真实1候选0标签；public_candidate_build.json |
| python -m unittest discover -s scripts/annotation/tests -v | 22:16:57 / 22:17:27 | 0 | 27 tests，0 fail、0 skip；final3_annotation_tests.log |
| python -m ruff check scripts/annotation | 22:17:27 / 22:17:27 | 0 | final3_ruff.log |
| python -m ruff format --check scripts/annotation | 22:17:27 / 22:17:27 | 0 | 2 files unchanged；final3_format.log |
| python -m mypy scripts/annotation/prepare.py --follow-imports=silent --follow-untyped-imports | 22:17:27 / 22:17:27 | 0 | 1源码文件无错误；final3_mypy.log |
| python scripts/annotation/prepare.py validate --input benchmarks/manifests/r19_public_dev_candidate_v1.json | 22:17:27 / 22:17:28 | 0 | real=1、awaiting_human_label=1、gold=0；final3_real_candidate.log |
| python -m pytest tests/plan/test_verify_plan.py tests/plan/test_recovery_plan.py -q | 见final2_commands.json | 0 | 47 passed，0 fail、0 skip；final2_plan_regression.log |
| python scripts/verify_plan.py | 见final2_commands.json | 0 | PLAN_OK，仅结构；final2_verify_plan.log |
| WSL CBM scripts 最终刷新及 validate_candidates inbound depth2 | 见cbm_final_run/cbm_trace_run.json | 0 | 195节点798边；main及模块入口两调用者，rg交叉核实 |

unit/contract/security/CLI integration 在上述 27 个本地行为测试范围内 passed，不表示数据库/产品全链路 integration 或真实标注 passed。既有计划回归47通过。frontend/e2e/live/manual 均 not_run，未连接真人、模型或来源网络；未开展正式准确率、性能、持续运行或实际容器/索引审计。

历史失败不删：首轮 24 行为测试通过；直接 mypy 起初提示缺 types-jsonschema（环境类型存根缺失，不是业务失败）。随后以实际库源码进行 follow-untyped-imports 类型检查，发现 next() 参数为 Iterable 的真实类型错误，改为 iter()。捕获的 initial_commands.json 记录 22:10:55–22:10:58：Ruff/format/mypy各 exit1；原始 initial_*.log 留存。修正导入排序、set 推导、显式 check=False、格式及上述 next() 后，final 全部 exit0；加版本绑定/标签导出审计为26，再加答案文本泄漏为27，final3全部通过。没有删难例、改阈值、改金标或把失败变skip。

CBM 官方 portable 路径 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`，独立项目 dianzi-r19-preparation、cache `/tmp/dianzi-cbm-r19-preparation-20261015` 在仓外，仅索引此 WT/scripts，排除 benchmarks/holdout/secret。图入边与 rg/真实 CLI 调用交叉核实，图不是测试通过依据。

## 合同差异、缺口和交接

新增 schema 是 R19 本地候选准备格式，未改冻结公共合同。原 T46/T01 最终范围、原前置与全部验收保留；没有正式评测配置、正式盲测冻结或 accepted 登记。candidate_origins 明示模型辅助整理；实际人工标签尚无，模型不充当唯一出题与裁判。

缺口：真实双人身份/独立提交、版本/条件/资产/问答/变化/配对安全全覆盖、分歧裁决、许可核验、实际镜像/索引输入检查和最终冻结签字。工具 hash 不是签名，外部操作者必须保留不可变旧包；扫描只检查显式公开树中的原文本，不解压压缩镜像、不识别隐藏语义关联或变换后的泄漏，短状态答案仍需人工检查。

评分证据限定：P2/P3/A1 为数据准备/边界校验能力，没有准确率/多跳/Agent分数；D1 为可复跑 CLI、schema、runbook 和真实命令收据。下一步建议：主控委派全新非作者复跑冻结包；通过后只接受此准备切片，再扩充真实候选与人工核验安排，完整 R19 继续等待能力前置和正式冻结条件。主状态由主控协调，不在此 WT 擅改。
