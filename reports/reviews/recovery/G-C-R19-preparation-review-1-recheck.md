# G-C-R19-preparation-review-1-recheck

What this change does: 修复候选准备工具的跨字段 split 身份检查、其他注册 Git worktree 的隔离，以及待标注分支中的孤儿/过期裁决校验。公开材料仍只有 1 个 real/dev 候选、4 字符包名证据、0 真人标签；完整标注链也最多进入 ready_for_manual_review，金标数恒为 0。

**Verdict: Ship（仅 R19 工具候选准备切片）。** 原审查的 Must fix 1、2、3 在本固定版本关闭，未发现新的已证实阻断。整 R19 仍 partial / awaiting_human_label；不签整 R19、T46、T01、阶段门或正式冻结，不自行登记 accepted。

## 固定对象与边界

- 实际开始：2026-10-15T23:28:20+08:00；本报告记录时间：2026-10-15T23:38:00+08:00。命令收据均保存实际北京时间秒级 +08:00，没有模拟时钟。
- 原固定对象：`a0c76800202a9869c4e24918b84893ebcec52a61`；原代码 `81b38d5559219d5818e6169da32cd7b98e33d392`。
- 新代码：`22d809f7803d539a2b551eb878ceae5333182d83`；材料与本次 HEAD：`10c16a5cda132269be7d906bb902d222a41c690b`。
- 新独立工作树 `D:/wt/r19-preparation-review-fix1`，分支 `codex/r19-preparation-review-fix1`，从材料提交新建；未审作者动态目录。沿用未参与实现的 reviewer 身份，未修改业务、共享 progress、合同、fixtures 期待、标签、指标阈值或分母，无提交/push。
- 重读最新 Ponytail 5.2 review、实际 AGENTS、执行索引、R19 恢复卡、03 数据合同、06 评测合同、原 T01/T46、恢复 manifest/状态/交接、作者 fix1 报告和原独立报告。原报告 SHA256 `b998290edb82152bddc35b8d0275c1ef34f2665be8e8f129c1e3d9f75dd69117` 未改。
- fix1 只改 prepare.py/runbook，新增 test_prepare_fix1.py；原 schema、公开候选、原 27 测试均未改。全部标签/裁决/身份负例都是显式 synthetic，仓外临时目录，0 真人。未读真实 holdout 答案、秘密、DPAPI，未连接网络/模型/DB/API。

## 三个 Must 的定向关闭

| 原项 | 固定源码与实际复验 | 结论 |
|---|---|---|
| 1：family 和 alias 不同前缀造成跨字段关联漏检 | `prepare.py:122–124,146` 以原精确值共同检查 family/alias/document/URI。原 alias→family 的 validate/export 均 exit2/FAMILY_SPLIT_LEAK；独立新增 4×4=16 个跨字段组合全部拒绝。作者两方向、传递/循环及排列测试通过。 | 关闭 |
| 2：其他注册 worktree 被当仓外 | `prepare.py:321–350` 每次调用读取 `git worktree list --porcelain -z`，根路径 resolve，加显式产品挂载，Git不可用非零拒绝。原另一 registered WT 标签输出及带 annotations 输入均 exit2/HUMAN_OR_HOLDOUT_PATH_MUST_BE_EXTERNAL；输出用新文件名。独立新建中文含空格 no-checkout WT，直接路径和 Windows junction 的 labels/holdout 四种落点全部拒绝且无文件。 | 关闭 |
| 3：不足双标签先 continue 导致裁决未验先导出 | `prepare.py:246–284` 在 readiness 分流前拒绝重复、无当前双标签、旧 hash、自我裁决/身份及不明 evidence。原孤儿裁决 validate/export、原无效旧导出重验、重复裁决均 exit2（REVIEW_REQUIRES_TWO_CURRENT_LABELS / DUPLICATE_REVIEW_RECORD）；导出不创建。 | 关闭 |

补验了当前标签修订：在合法双人合成链追加 revision2 后，旧裁决 hash 返回 ADJUDICATION_INVALID_OR_STALE；裁决 hash 更新但身份 hash 尚旧时返回 IDENTITY_ATTESTATION_INVALID_OR_STALE；全部绑定当前两份记录后可 export→validate，保留 3 条标签历史，ready_for_manual_review=1，human_gold_count=0，正式分子分母仍 null。作者还补齐零/单标签孤儿身份/裁决、分歧待裁决但身份无效、Git不可用和正常待标注回归。

四类精确值共同检查只控制 split，不合并产品实体、删除案例或把 quote/hash/主题/普通关系当家族。相同 split 的已声明关联保持两个案例；无共同精确 ID 的相同 quote 在不同 split 仍可保留。精确字段偶然同值可能保守过度隔离，这是主控已批准的局部策略与作者报告公开限制；未声明或不同字符串的语义关联仍要人工核验。无需新增 DSU 架构或改变公共合同。

## 实际命令、数量与失败记录

以下 cwd 均 `D:/wt/r19-preparation-review-fix1`，Windows Python 为锁定 `D:/dianzi/backend/.venv/Scripts/python.exe`。完整 argv、起止、exit 和 stdout/stderr/log hash 在 raw 目录收据，未降低任何原门。

| 实际命令/检查 | 北京时间 +08:00 | 实际结果 |
|---|---|---|
| `python -m unittest discover -s scripts/annotation/tests -v` | 23:29:42 → 23:30:26 | exit0；原27+新增13=40 tests，0 fail/0 skip；包含真实双进程排他写入和 Windows junction |
| `python -m pytest tests/plan/test_verify_plan.py tests/plan/test_recovery_plan.py -q` | 23:29:42 → 23:30:15 | exit0；47 passed，0 fail/0 skip |
| `python -m ruff check scripts/annotation` | 23:29:42 → 23:29:42 | exit0 |
| `python -m ruff format --check scripts/annotation` | 23:29:42 → 23:29:43 | exit0；3 files unchanged |
| `python -m mypy scripts/annotation/prepare.py --follow-imports=silent --follow-untyped-imports` | 23:29:43 → 23:29:45 | exit0；1 source file |
| `python scripts/verify_plan.py` | 23:29:45 → 23:29:45 | exit0；仅结构检查 |
| 公开 real/dev 候选 validate | 23:29:45 → 23:29:46 | exit0；real1 / awaiting_human_label1 / gold0 |
| `git diff --check a0c7680… 22d809f…` | 23:29:46 → 23:29:46 | exit0 |
| 原 reviewer 36 个 CLI 探针保持原 expected_exit 重放 | 23:33:31 → 23:34:09 | 外层exit0；36/36符合原期待，重要负例还核对明确错误码 |
| 独立新增 28 个 CLI 正/负例 | 23:36:50 → 23:37:24 | 外层exit0；28/28符合，拒绝输出均不存在；正常标签链完整保留 |
| WSL 冻结原函数符号链接检查 | 23:35:59 → 23:35:59 | exit0；3函数级检查通过，不算 Linux CLI 或真人验证 |

正常 import→validate→prompt export、输出覆盖拒绝、candidate/annotation 旧 hash、公开字节泄漏、参考路径穿越、未知许可、缺项计数、声明不同 human 字符串仍 gold0，都在原 36 和作者 40 回归中重新执行。没有把候选数当金标数，也没有移除待标注案例来改善分母。

两次 reviewer 重放脚本问题已保留，均不冒充业务失败：

1. 首轮 36 重放外层exit1、仅 clean_scan 不符合期待，因为上轮同一 public 树已放入泄漏文件。工具正确返回 HOLDOUT_LEAK_FOUND。保留 `original_36_replay_initial.json` 和脚本初版；新建与原时点相同内容的干净合成树，然后按原顺序放入泄漏文本，所有 expected_exit 不变，最终36通过。
2. 新增探针首轮外层exit1，清理 no-checkout WT 时未加 force，Git将未checkout文件视为变化，触发 cleanup assertion；CLI记录未写完，不计该轮通过。保留初版脚本与 `initial_extra_cleanup_recovery.json`。确认解析目标仅在自建专用临时根、目录只含 `.git` 后移除该测试 WT；仅改 reviewer 的清理命令，完整重跑28并保存全部真实收据。未删除用户文件或作者/原 reviewer WT。

Windows 原生 os.symlink 再次返回 WinError1314，记环境 blocked，不算通过/skip。实际 Windows junction 导出边界已通过。WSL 用固定源码函数 AST 原样执行，root/nested symlink 扫描与 resolve 后指向仓库路径均正确拒绝；系统 jsonschema3.2 无 Draft202012Validator，因此没有声称 WSL CLI 全链路通过。

## 冻结材料、调用图与精确证据

raw：`reports/runs/recovery_r19_preparation_review_1_recheck_20261015/`。

- `commands.json`：40/47及静态、公开候选、diff、rg、版本命令。
- `original_36_replay.json`：36条完整原期待重放，沿用原合成输入；旧无效导出作为固定原件复读，不用缺文件来替代该负例。
- `extra_probes.json`：28条新增 CLI、每个错误码/输出存在性、正常链状态、原生 symlink 环境阻塞。
- `frozen_binding.json`：6个源文件与28个材料 canonical Git blob，共34项全部匹配；源码在材料tip未变、独立checkout CRLF归一后吻合，作者 observed hash 可由 LF/CRLF解释。原 reviewer 公开报告/合成输入的10个hash也全部匹配。没有现场重读作者动态目录。
- `cbm_commands.json` 与 `cbm_*.log`：官方 CBM v0.11 CLI，独立 project `r19-preparation-review-fix1-scripts` 217 nodes/945 edges，`r19-preparation-review-fix1-src` 1206/5910；cache `/tmp/dianzi-cbm-r19-preparation-review-fix1-20261015` 在仓外，persistence=false。只索引此 WT/scripts 与 backend/src，不索引 benchmark/标签/holdout/秘密。
- 五函数 validate_candidates、inspect_annotations、protected_roots、require_external、scan_leaks 的入向 trace 与 `rg_callers.log`、源码及真实 CLI 相互核对：main 是入口，inspect_annotations 经 summarize，protected_roots/require_external/scan 在 main 真实调用。图只作定位，不作通过依据。
- `supplementary_commands.json`、`wsl_symlink_probes.json`：WSL函数级检查及实际退出码。
- 最终 `review_evidence_manifest.json` 只列正式报告/脚本/日志/JSON与显式仓外 synthetic 输入hash，排除 pyc、__pycache__、工具缓存；报告hash和精确文件清单由它绑定。

最短独立复验入口（不覆盖原证据）：

```powershell
$reviewPython = 'D:/dianzi/backend/.venv/Scripts/python.exe'
& $reviewPython -m unittest discover -s scripts/annotation/tests -v
& $reviewPython -m pytest tests/plan/test_verify_plan.py tests/plan/test_recovery_plan.py -q
& $reviewPython reports/runs/recovery_r19_preparation_review_1_recheck_20261015/replay_original_36.py
& $reviewPython reports/runs/recovery_r19_preparation_review_1_recheck_20261015/probe_fix1_extra.py
```

## 缺口与交接

原三个风险路径已有真实回归，不再列明确缺测。Windows 原生符号链接 CLI 因权限不足未测，Linux仅函数级；实际产品镜像/索引、隐藏语义/编码或压缩内容泄漏未审，不以字节扫描替代原T46-C04最终验收。未发现有触发输入的新 Must，不以风格、行数或推测制造缺陷。

整 R19 仍待 R07–R16 全覆盖、完整题型规模、真人独立身份/提交、许可核验、裁决和最终冻结签字；DB/API/前端/e2e/live/manual、准确率、多跳、性能、连续运行均 not_run。当前1 real/dev、0真人标签/金标、许可unknown，formal_evaluation 分子分母null保持。评分证据只限 P2/P3/A1 数据准备校验和 D1 工具/文档；不能据此给正式分数。

下一步由主控据本固定版本报告登记准备切片的限定通过；正式 R19/T46/T01 和阶段门继续保持未完成。任何后续实质改动须重新冻结复核。

**Not checked:** 真实 holdout 答案、真人核验、来源网络、实际产品镜像/索引、Windows原生符号链接CLI和正式评测；均没有计通过。
