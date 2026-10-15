# R09 · 公开知识卡与共享预派发超时修复组合候选

记录时间：2026-10-16T02:50:56+08:00。组合作者：
`/root/r09_shared_timeout_combination_preparation`。
本组合切片状态为 **awaiting_review**；组合实现 complete 仅指冻结叠加及所列本地验证。
没有登记 accepted，没有替原 reviewer 签通过；整 R09 仍 partial，
R09/T09/T14/T15/T22/G-C 的最终验收不由本报告判定。

## 输入、输出与精确范围

工作树 `D:/wt/r09-combo-fix`，本地分支 `codex/r09-shared-timeout-combination`。
输入 R09 作者材料基线 `ed217564e9cf3571b430d0fe7caa4d3999c7320b`，
其原业务冻结 `02bea007dec5046458c7f2f1c969f0080ef03889`；
仅 cherry-pick 共享代码提交 `47c47bc2b5d537166ee47a01c2ab14c035466e3d`。
没有冲突。共享修复曾获独立限定 Ship，该意见不能替代本 R09 组合复核。

组合代码 SHA：`dd36cf78c3d15138683d09c12ea867c0055b9674`。
组合代码 tree：`f0ba5dbe822d828ffaa642ce1f0f047a1b725f27`。
相对 R09 基线的业务/测试 diff 只有两文件，146 additions / 2 deletions：

- `backend/src/ai_intel/infrastructure/models/generation.py`
- `backend/tests/unit/test_r05_generation_predispatch_timeout.py`

二者组合 Git blob 均与源 47c47bc 完全相同。
R09 原七个业务/测试文件、CR-R09_verification_labels、作者报告和全部原材料的
Git blob 均原样保留。新增材料只有本报告、
`reports/runs/recovery_r09_shared_timeout_combination_20261016/` 及四条精确 `.gitattributes`
规则：仅本 run 保留 raw 字节并排除日志与原 red JUnit 的 diff 展示，保留 trailing-space/space-before-tab
检查；没有全局配置或检查忽略。完整材料文件名、大小及 hash 见本 run 的 manifest。

已读 AGENTS、00 执行索引、R09 恢复卡、T18/T20/T22、03/05/06、相关引用资料、
固定基线 task_state/交接、CR-R09_verification_labels 和原独立 reviewer 报告。
Ponytail 5.2.0 用于追踪全部调用者并在共享处修复；本地经验检索没有足够相似的
超时归一化证据，未引入额外抽象。未改主 checkout、progress、公共合同、schema、
锁文件、迁移、认证、金标、阈值或计分分母，未 push 或启动服务。

## 唯一 Must 的根因与组合行为

原 reviewer 报告的 P2 是合法整次预算在并发槽申请前耗尽：
`deadline.remaining_seconds()` 在原共享 try 之外抛裸 `NetworkTimeoutError`，
越过卡入口只捕获 `GenerationFailure` 的固定失败合同。
本组合保留卡源码和原捕获路径，只在共享槽申请边界将该类型转为
`GenerationFailure("model_network_timeout")`，attempts 空。
槽申请返回 False 仍为 `model_concurrency_timeout`，不释放未取得的槽；
取得槽之后的失败仍释放一次。没有重试、吞并任意 Exception 或模板回退。

精确卡探针固定 monotonic 为 100→103、合法 1 秒预算，断言异常实际类型为
`CardExtractionFailure`、code 精确等于 `model_network_timeout`、attempts 为 `()`、
gateway 调用为 0。卡没有成功返回，真实模型调用为 0。
共享新 17 项还覆盖四种 provider、边界时间、未取得槽不释放、后续槽可用、
取得槽后释放一次及 grounded answer 的自然包装。

## 实际命令、结果与重复计数

专属 `D:/wt/r09-combo-fix/backend/.venv` 使用原锁执行
`uv sync --frozen --offline --python D:/dianzi/backend/.venv/Scripts/python.exe`，exit 0。
Python 3.12.13；仅本项目包的本地构建，未下载依赖或模型。
runner 使用标准运行环境字段白名单及 `DATA_MODE=fixture`，不读取任何秘密值；
PYTHONPATH 固定为本 worktree 的 src/tests。
`scope_audit.json` 的实际模块路径和 sys.prefix 断言证明使用本组合源码与独有环境。

pytest cwd 均为 `D:/wt/r09-combo-fix/backend`，使用
`--no-cov -q -p no:cacheprovider`；每次 basetemp 位于专属 D:/tmp 路径，
JUnit 位于本 run。所有 argv、cwd、实际 +08 开始/结束、退出码及原始 stdout/stderr
保存在同名 `.command.json`/`.stdout.log`/`.stderr.log`；
[command_index.json](../runs/recovery_r09_shared_timeout_combination_20261016/command_index.json)
汇总原始回执和 JUnit 数量。没有覆盖率、性能、准确率或持续运行声明。

| 标签 | child exit | 实际 JUnit | 代码版本 |
|---|---:|---|---|
| baseline_independent_17 | 1 | 16 passed / 1 failed，0 error/skip | 原 ed217564 |
| combination_independent_17 | 0 | 17 passed，0 error/skip | 组合 dd36cf78 |
| exact_card_timeout | 0 | 1 passed，0 error/skip | 组合 |
| focused_66 | 0 | 66 passed，0 error/skip | 组合 |
| unit_regression_268 | 0 | 268 passed，0 error/skip | 组合 |
| contract_regression_76 | 0 | 76 passed，0 error/skip | 组合 |
| security_regression_36 | 0 | 36 passed，0 error/skip | 组合 |
| original_t22_6 | 0 | 6 passed，0 error/skip | 组合 |
| shared_predispatch_17 | 0 | 17 passed，0 error/skip | 组合 |

原 17 探针没有改字节或放宽断言。baseline 在
02:45:56.929507→02:46:00.363855+08:00 真实独跑，唯一失败为
`test_expired_client_deadline_is_error_with_one_attempt` 的裸超时。
组合在 02:46:45.074477→02:46:49.638191+08:00 真实独跑转绿。
原日志保留，未改失败为 skip。

相关回归经 JUnit case 身份去重为 380；focused 66 与原 T22 六例均包含于 380，
不能相加为额外独立案例。原 reviewer 17、精确新卡探针 1、共享新 17 另列。
本次基线红例只用于确定性复现，不能计为组合通过。

`ruff_check`/`ruff_format` 对原 R09 七文件加共享两文件均 exit 0；
`mypy` 对 generation/card_extraction/knowledge_cards 三 source 文件 exit 0。
`code_diff_check` exit 0。新增作者材料脚本单独运行 Ruff/format；
复制的原 reviewer 探针不自动格式化，以保留原 hash。

材料检查的原失败全部留存：`scope_audit` exit 1 是作者审计脚本初次要求所有 raw
checkout 与原作者工作树逐字节相同，发现六文件仅 LF/CRLF 不同。
逐项证明 base/组合 Git blob 相同，修正为同时核验 raw 与固定 Git blob，
不改或清洗原材料；`scope_audit_recheck` exit 0。
`material_ruff_initial` exit 1 为一长行及一嵌套 with，修正材料脚本后复检 exit 0。
一次手工 `HEAD^{tree}` 查询因 PowerShell 花括号解析得到 git fatal，命令组退出 0；
后续 `code_tree` 用实际 argv 正确查询 exit 0。这些不计业务测试失败或通过。
首次 `freeze_staged_diff_check` exit 2 来自原 red JUnit 错误诊断的一行尾空白；
原 XML 完整保留，对该单文件增加精确 raw diff 属性再复检，不清洗日志或降低源码检查。
首次 seal 的本体与 sidecar 另存 freeze_initial_manifest，保留其原 hash 回执；最终新 seal
取代候选清单，未覆盖原失败记录。

## 调用链、CBM 与固定材料

按官方 portable CBM 实际 help/schema 使用 WSL Ubuntu-22.04 root：
`cli --json index_repository --repo-path /mnt/d/wt/r09-combo-fix/backend/src
--name r09-shared-timeout-combo-dd36cf7-20261016 --mode fast`。
专用缓存 `/tmp/dianzi-cbm-r09-combo-fix-20261016` 位于仓外；只索引 src，
没有 secrets、holdout 或全仓资料索引。实际成功 1314 nodes / 6550 edges，
0 not-indexed/partial/unusable；默认排除 assets 与 parser 缓存目录。
`cbm_schema`、generation/card/grounding 三条 qualified trace 均 exit 0；
全 src/tests 的 rg 核对在 `rg_callers_baseline/combination` 原输出。

真实已有调用链为 question route→GroundedQuestionService.ask→
generate_grounded_answer→GenerationClient.generate；新卡 extract→同一共享 generate。
CBM 卡生产 caller 为 0，rg 也只找到卡入口和直接 tests；
本组合不把未接线的卡称为完整产品。

原 reviewer 17 探针 raw SHA-256：
`76ca4d4064f65bfd08846a6e57a2c4fde087a10d6422d563094b412890058bbf`。
原 reviewer manifest 本体 raw SHA-256：
`d8eb2e34edf1199224778c58b31a13622715854014907b59ea315e9fc8631fba`；
原 manifest 121 项逐项 raw hash 核验通过。
原作者 manifest 本体 raw SHA-256：
`816eaf1ae985e07c35c1fee5753576d6e7ca43f6bd526cbe756dbc7914fb790f`，
组合 checkout manifest/sidecar 与原作者逐字节相同。
原作者 90 项均固定 Git blob 相同；84 项 raw 相同，6 项只差 LF/CRLF，
两套 hash 和每项证据保存于 `scope_audit.json`。

新 `artifact_manifest.json` 列本报告、精确属性及新 run 文件原始字节，
本体 hash 位于 `artifact_manifest.sha256`。自身、sidecar 与 freeze 命令回执不进入
自身清单，防止循环；封存/封存后核验回执及先前 seal 独立保存。代码 SHA/tree、原始材料 hash、
模块路径及精确变动文件列表可用于原 reviewer 定向复核。
材料提交 SHA 和最终提交 tree 由交接返回，不能自引用写进该提交内的 hash 材料。

## 验证层、评分证据与下一步

| 层 | 本组合状态 | 实际边界 |
|---|---|---|
| unit | passed | 原相关 268、新共享 17、原 reviewer 17 及精确卡探针；fixture |
| contract | passed | 76 相关及原 T22 六例；fixture schema/SQL 合同 |
| security | passed | 36 相关；原 reviewer 嵌套注入/公开 ACL fixture 保留 |
| integration | not_run | 0 PostgreSQL/worker/真实 API 运行；SQLite fixture 不计 PG |
| frontend/e2e | not_run | 0 browser 与 R09 产品流程 |
| live | not_run | 0来源外网、0真实模型、0真实机制案例 |
| manual | not_run | 0人工金标、0团队复现、0法规适用裁决 |

F2/F3/R1 证据限于既有候选引用、固定修订、未知/冲突及共享错误合同。
未增加真实来源覆盖、富化准确率、问答指标或团队复现得分。
合同与计划没有业务偏差；仅提供既有切片组合，授权边界内未改 card 捕获。
原 R09 真实三类正文与三机制目录、PG 候选/审核账本、文献语义关系、
正确时点检索问答和界面仍待后续接线及独立验收。

下一步请主控把本组合 code SHA、材料 SHA/tree 和 manifest 交原 R09 reviewer，
定向复核唯一 P2 的自然包装、原 17 字节和相关回归。原 reviewer 可以审查新的 freeze，
但本报告不赋予整 R09/T22/G-C 通过状态。

未检查真实 PG、来源/模型、browser、真实负载性能和人工标注；核心限制是卡入口
仍没有生产调用方，不能凭 fixture 转绿验收整 R09。
