# R19-preparation-fix1 · 三个独立审查阻断修复

状态 awaiting_review；仅候选准备切片，整 R19/T46/T01 仍 partial，真实人工标签/金标仍 0。原代码 `81b38d5`、材料 `429ea9b/a0c7680`、原报告和冻结 manifest 均保留。新代码冻结 `22d809f7803d539a2b551eb878ceae5333182d83`，分支 codex/r19-annotation-preparation，WT `D:/dianzi-r19-annotation-preparation`，无 push、无 accepted/主状态变更。

## 依据、原始复现与最小修复

已重新核对当前源码、调用者、Ponytail 5.2 full 与既有 R19/原 T46 合同。新非作者原审查报告：`D:/wt/r19-preparation-review-1/reports/reviews/recovery/G-C-R19-preparation-review-1.md`，SHA-256 `b998290edb82152bddc35b8d0275c1ef34f2665be8e8f129c1e3d9f75dd69117`。公开 synthetic probes 及输入由该 reviewer 拥有，未修改或覆盖。作者在原 a0 代码先复现，7 个必须拒绝的 CLI 全 exit 0；原输出和时间存新 run 的 before_review_reproduction.json，重放程序退出 1（检测到缺陷）。所有复现均 explicit synthetic、0 真人、没有真实 holdout。

| 原 Must / 根因 | 新代码位置与修复 | 原 → 新可观察结果 |
|---|---|---|
| 1：主家族和 alias 分别加 family:/event: 前缀，跨字段相同标识未关联 | prepare.py:122，家族/alias/document_id/URI 使用同一精确值键域；每个案例的所有标识绑定其 split | alias→另一案例主家族的 validate/export：exit0 → exit2/FAMILY_SPLIT_LEAK，输出不创建 |
| 2：只保护当前 WT 和主库，其他注册 WT 被当仓外 | prepare.py:322，逐调用读取 git worktree list --porcelain -z；全部注册根 resolve，加显式产品挂载；Git缺失/读取失败明确 REPOSITORY_WORKTREE_REGISTRY_UNAVAILABLE | 实际新建 detached/no-checkout WT 标签导出：exit0/文件存在 → exit2/HUMAN_OR_HOLDOUT_PATH_MUST_BE_EXTERNAL/无文件；Windows junction 同样拒绝 |
| 3：少于两份标签先 continue，忽略孤儿/重复裁决 | prepare.py:251–254，先检查重复/完整双标签；任何裁决/身份记录均校验当前双标签 hash、参与者和 evidence，再计算状态 | 1标签+伪造hash裁决的 validate/export/旧导出重验、1标签+重复裁决：exit0 → exit2/REVIEW_REQUIRES_TWO_CURRENT_LABELS 或 DUPLICATE_REVIEW_RECORD；不导出无效审计包 |

Must1 不需要额外 union-find：同一案例内的全部标识对应同一 split；任何已声明的等价链跨 split，必有共享精确标识连接不同 split 的相邻案例，此边在逐标识检查中被拒绝。新增测试覆盖两方向 family↔alias、四类跨字段匹配、传递/循环关联的全部顺序和同 split 正例。case ID 变更不改变这些标识。

主控已明确允许四类精确值共域作保守防泄漏。它只拒绝冲突 split 分配，不自动合并产品实体、改标签、丢候选或把普通关联当等价；quote/hash/主题/普通关系不参与。不同类型的标识偶然使用相同字符串时可能过度隔离，返回 FAMILY_SPLIT_LEAK；需人工明确家族归属并协调分配，不能静默删除案例或改变评分分母。未声明/不同字符串的语义同源仍须人工核验。

Must2 使用实际注册信息，不扫描用户目录、不缓存根清单，新增 worktree 立即纳入。路径比较解析 symlink/junction 的实际落点；新测试真实创建中文含空格的注册空 WT 和 Windows junction，标签与 holdout 4 类输出均被拒绝。所有临时 WT/文件都是作者创建的明确 synthetic 测试对象，删除前校验实际路径位于该专用临时根、内容只含 .git 和明确 synthetic 输出；原 reviewer WT、其 no-checkout probe WT 和输入保持不动。

Must3 还关闭“分歧缺裁决时跳过无效身份记录”的同根因分支。0/1 标签且没有 review 仍 awaiting_human_label；两标签分歧无裁决仍 awaiting_adjudication；合法人工链仍最多 ready_for_manual_review，gold 永远 0。人工身份声明仍不等于实际真人独立核验。

## 文件所有权与实际验证

仅改 `scripts/annotation/prepare.py`、`docs/runbooks/annotation_preparation.md`，新增直接回归 `scripts/annotation/tests/test_prepare_fix1.py`；原 schema、公开 real/dev 候选、原27测试和历史报告/manifest 均未修改。新增本报告及自有 `reports/runs/recovery_r19_preparation_fix1_20261015/`。没有 backend/frontend、公共 schema、锁、认证、迁移、状态、指标或金标改动；没有 DB/API/网络/秘密访问。

以下 cwd 均 `D:/dianzi-r19-annotation-preparation`，Python 为现有锁定 `D:/dianzi/backend/.venv/Scripts/python.exe`。逐 argv/起止时间/exit/stdout/stderr/hash 见新 run 的 final_commands.json、before/after_review_reproduction.json 和 delivery_manifest.json。

| 实际命令 | 实际北京时间 +08 起止 | 结果 |
|---|---|---|
| python reproduce_review_probes.py before | 见before_review_reproduction.json | 外层exit1；7 CLI误放行均exit0；旧无效裁决真实保留并添annotation hash、重验仍0 |
| python -m unittest discover -s scripts/annotation/tests -v | 2026-10-15T22:43:44 → 22:44:25 | exit0；原27+新增13=40 tests，0fail/0skip，含原并发排他导出 |
| python -m pytest tests/plan/test_verify_plan.py tests/plan/test_recovery_plan.py -q | 22:44:26 → 22:44:48 | exit0；47 passed，0fail/0skip |
| python -m ruff check scripts/annotation | 22:44:25 → 22:44:25 | exit0 |
| python -m ruff format --check scripts/annotation | 22:44:25 → 22:44:25 | exit0，3文件保持格式 |
| python -m mypy scripts/annotation/prepare.py --follow-imports=silent --follow-untyped-imports | 22:44:25 → 22:44:26 | exit0，1源码文件无错误 |
| python scripts/verify_plan.py | 22:44:26 → 22:44:26 | exit0；PLAN_OK仅结构 |
| python scripts/annotation/prepare.py validate --input benchmarks/manifests/r19_public_dev_candidate_v1.json | 22:44:48 → 22:44:49 | exit0；real=1、awaiting_human_label=1、gold=0 |
| python reproduce_review_probes.py after，固定22d809f | 见after_review_reproduction.json | 外层exit0；同7端点全部exit2，无错误放行，拒绝旧无效导出重验 |
| 官方 WSL CBM scripts 初索引/新SHA刷新/4函数入向trace | 见cbm各run JSON | exit0；195/798 → 217/945；rg交叉核对全部caller |

初次新增测试独立13通过，但 Ruff 的 SIM117（嵌套 with）exit1，initial_commands.json/initial_ruff.log 保留；仅合并 with 后静态通过。未删负例、降阈值、改 gold/分母或改失败为 skip。原失败与新修复日志分 run 保存。

CBM 官方 v0.11.0 独立 project=dianzi-r19-preparation-fix1，cache=/tmp/dianzi-cbm-r19-preparation-fix1-20261015，persistence=false，范围只有此 WT/scripts，排除 benchmarks/holdout/secrets。新 code SHA 22d809f 的 validate_candidates、inspect_annotations、protected_roots、require_external 入向 trace 与 rg/CLI 测试相互核对；图不代替实际行为验证。

## 交接与未完成项

准备切片的 unit/contract/security/CLI integration 在上述40行为测试范围 passed；没有把 fixture 身份/标签计为真人或正式评测。frontend/e2e/live/manual 全 not_run，正式统计分子分母 null；真实规模仍1 real/dev候选、1四字符包名字段证据、0人工、许可unknown。正式R19/T46/T01及阶段验收仍未完成。

评分证据仍仅P2/P3/A1数据准备与安全校验、D1本地可复跑材料，不提供准确率、多跳、Agent分数。按主控安排由原独立 reviewer 在新的固定 WT 对新 SHA 定向复核三Must与回归；作者不自行签 accepted。其余真实双人身份、完整题型覆盖、许可、实际镜像/索引、R07–R16能力前置和冻结签字保持待完成；扫描语义/压缩内容与hash非签名限制仍在原runbook。
