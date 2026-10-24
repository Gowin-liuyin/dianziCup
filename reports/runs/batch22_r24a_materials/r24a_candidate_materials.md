# R24-A 候选材料清单（批次22 目标3 · 只整理不实现）

- 文档首次创建时间：2026-10-25T04:54:16+08:00
- 最后更新时间：2026-10-25T04:54:16+08:00
- 任务编号：批次22 目标3（材料整理员，单文件产出）
- 任务状态：完成（整理完成；不含任何实现动作，未运行 pytest，未修改任何业务文件）
- 授权依据：`reports/tasks/Root-batch22-plan.md:12`（"R24-A 候选材料整理：只整理（候选清单、依赖、验收差距文档化），不越过 R24-A→R23→R24-B 顺序，不实现"）、`reports/tasks/Root-batch22-plan.md:25`（验收"R24-A 材料文档存在且只含整理内容"）
- 产出文件：`reports/runs/batch22_r24a_materials/r24a_candidate_materials.md`（本文件，唯一新写文件）
- 检查时 Git 状态：分支 `codex/full-delivery-recovery`，工作树仅 `progress/OPEN_QUESTIONS.md` 有既有未提交修改、`.zcode/`、`reports/runs/batch22_source_enricher_research/`（均非本批产出；本批未触碰）

## 0. 对交接约束的一处澄清（重要发现）

`progress/context_handoff.md:27` 等多处记载的顺序约束是 "R24-A→R23→R24-B"。本批按指示先找 R24-A 任务卡定义，结论：

- **R24 不是"修复验证/回归验证"卡。** 权威定义在 `docs/plan/12_recovery_task_cards_20261014.md:262-270`：R24 = 报告、答辩、视频与交接冻结（原任务 T55、T56、T59 切片）。全仓库 grep "修复验证/回归验证" 命中的是 `docs/decisions/CR-R12_default_projection_runtime.md:26`（R12 修复复核叙述）与历史 `progress/history/task_state_pre_recovery_8e265dc.json.txt:51`（T01 修复验收叙述），均与 R24 无关。
- 与"复现/复核"最接近的面在 **R23**（独立审查、干净环境复现与逐分审计，`docs/plan/12_recovery_task_cards_20261014.md:253-260`：核验①从干净环境启动、③原文/数据/制品 hash 对应、未复跑不得签通过）与 **R24-B**（处理 R23 审查结论后修订冻结，`contracts/task_manifest.json` recovery.work_packages["R24-B"]）。
- 因此本清单按任务卡实际口径整理：R24-A = 候选报告/演示/视频/提交包材料；"修复验证/回归验证"不构成 R24-A 的验收面。

## 1. 任务卡与相互顺序约束摘录

### 1.1 权威来源与顺序

- 主线顺序：`docs/plan/12_recovery_task_cards_20261014.md:17`（`... R22 → R24-A → R23 → R24-B`）；`docs/plan/00_execution_map.md:146`、`docs/plan/00_execution_map.md:156`（G-G：`R22 → R24-A → R23 → R24-B`）。
- 拆分理由：`docs/plan/12_recovery_task_cards_20261014.md:19`（"R24-A先产出供审查的报告、演示和候选提交包；R23独立复现并审查；R24-B再做最终冻结。两步属于同一张R24卡，A完成时R24保持partial/in_progress，不能提前验收整卡"）。
- 互锁规避条款：`docs/plan/00_execution_map.md:162`（"T55/T56完整候选材料和原验收在R24-A，新文档reviewer先试部署；R23再整体干净复现。T59需A候选清单+B最终冻结；复现后实质材料修改须复核新版本，避免T57前置T55/T56与B依赖R23互锁"）；`docs/plan/00_execution_map.md:176`（"R24提前材料仅partial，不越过R24-A→R23→R24-B"）。
- 独立准备（已解锁的骨架提前量）：`docs/plan/12_recovery_task_cards_20261014.md:21`（"R24 文档骨架从 R00 后建立"）；`contracts/task_manifest.json` recovery.independent_preparation 节点 `R24-document-skeleton`：after=[R00]，requires_slices=[R00:T00, R00:T01]，allows="报告/演示/交付清单骨架与许可清单，不填尚未取得的结果"，final_gate="R22→R24-A→R23→R24-B"。

### 1.2 R24-A 工作包合同（`contracts/task_manifest.json` recovery.work_packages["R24-A"]）

- 标题：候选报告、演示、视频与提交包；requirements=[D1,D2,X1,R2]；stage=G-G。
- depends_on=[R22]；requires_slices=[R22:T52, R22:T53, R22:T54, R18:T51, R21:T47, R21:T48]。
- output_slices=[R24-A:T55, R24-A:T56, R24-A:T59]；output_artifacts=[R24-A:candidate_delivery_manifest]。
- dependency_reason："需要正式评测和实际运行证据形成候选报告/演示/清单；候选材料为R23输入，不能声称整张R24/T55/T56/T59完成。 本片须完整满足T55/T56原检查并独立核验；候选制品清单为准备artifact，不提前完成T59。"

### 1.3 R23 / R24-B 对 A 的消费约束

- R23：depends_on=[R22, R24-A]，requires_slices 含 [R24-A:T55, R24-A:T56, R24-A:T59]，requires_artifacts=[R24-A:candidate_delivery_manifest]（同文件 recovery.work_packages["R23"]）。卡片前置："R22与R24-A候选材料通过所需检查；独立审查者已明确，不能由实施者自签"（`docs/plan/12_recovery_task_cards_20261014.md:256`）。
- R24-B：depends_on=[R23]，requires_slices 含 [R23:T57, R23:T58, R24-A:T55, R24-A:T56, R24-A:T59]，output_slices=[R24-B:T59]；"若R23后实质修改T55/T56材料，记录新版本与相关复核，撤回旧签字适用性"（同文件 recovery.work_packages["R24-B"]）。

### 1.4 三张能力切片的验收合同（capability_slices）

- `R24-A:T55`："完整候选Word/PDF/报告与原T55-C01–06；新独立文档试部署先完成，为R23整体复现输入。" 验收合同=`docs/tasks/T55_technical_report.md`。
- `R24-A:T56`："候选匿名PPT/PDF/真实视频与原T56-C01–06全部检查，为R23输入；最终交付清单尚待。" 验收合同=`docs/tasks/T56_demo_and_slides.md`。
- `R24-A:T59`："候选交付清单/材料hash与审查证据索引；不提前最终冻结、push收尾或外部提交。" 验收合同=`docs/tasks/T59_release_handoff.md`。
- `R24-B:T59`："R23独立复现后修订/复验、最终冻结/交接/收尾push核对与原T59全部验收。"

### 1.5 R24 整卡条款（`docs/plan/12_recovery_task_cards_20261014.md:262-270`）

- 原任务：T55、T56、T59（切片，非整卡完成）；D1/D2/R2/X1。
- 前置：骨架可早建；R24-A 正式候选材料引用 R22 并交 R23 审查，R24-B 最终冻结依赖 R23（`:264`）。
- 输入→输出：实际实现、指标和演示素材 → 技术报告Word/PDF、架构与实验图、匿名PPT/PDF、视频、接入与复现手册、提交清单（`:265`）。
- 改动边界：`docs/report/`、`docs/runbooks/`、演示素材和交付清单；不把密钥/内部账号/金标答案打包（`:266`）。
- 实施：R24-A 按官方初/决赛分别组织候选报告/PPT/视频/手册，落实主办模板并完成检查供 R23 复现；演示真实案例与显式demo两条轨；无CVE合成公告不显示伪造EPSS/KEV；备用录像注明彩排；预置问答不能改写评测结果（`:267`）。
- 核验：①Word/PDF渲染与内容一致；②PPT匿名/模板/字体/溢出；③视频与代码版本相符；④所有数字可回到原始日志；⑤安装、SDK、MCP与插件示例可复跑；⑥提交包秘密扫描、许可证与来源记录完整（`:268`）。
- 完成证据：实际文件和最终检查单；材料缺模板/人工信息明确阻塞（`:269`）。

### 1.6 原任务卡验收条款（切片级，全部保留）

- T55（`docs/tasks/T55_technical_report.md`）：目标产物 docs/report/、scripts/documents/、reports/acceptance/document_review.md、reports/tasks/T55.md，检查位置 reports/acceptance/t55_checklist.md（§3，T55_technical_report.md:23-31）；最低验收 T55-C01（报告章节与官方条款无遗漏且有对应证据）–C06（复用/外部参考注明）六例（§5，:52-60）；恢复附录"最终需要：R24-A:T55"（:78）。
- T56（`docs/tasks/T56_demo_and_slides.md`）：目标产物 docs/demo/、scripts/demo/、reports/acceptance/demo.md、reports/tasks/T56.md，检查位置 reports/acceptance/t56_checklist.md（§3，:23-31）；最低验收 T56-C01（现场改资产版本结果由真实规则改变）–C06（评委追问能打开run_id/配置/样本）六例（§5，:52-60）；实施4"模板未取得先准备内容纲要，不假称符合未拿到模板"（§4.4，:41）；恢复附录"最终需要：R24-A:T56"（:78）。
- T59（`docs/tasks/T59_release_handoff.md`）：目标产物 reports/acceptance/release_checklist.md、progress/final_handoff.md、reports/tasks/T59.md，检查位置 reports/acceptance/t59_checklist.md（§3，:23-31）；最低验收 T59-C01（制品hash核对且绑定实际版本）–C06（交接完成）六例（§5，:52-60）；恢复附录"最终需要：R24-A:T59、R24-B:T59"（:78）。

### 1.7 官方提交要求（R2/D1/D2 落点）

- `docs/plan/09_operations_delivery.md:62`："初赛：技术报告Word/PDF、操作视频、讲解PPT的PDF。决赛：技术报告Word/PDF、视频、按主办方模板制作的匿名答辩PPT。原始PDF第2—3页注明源码审阅方式与匿名要求。"
- `contracts/requirements.json` requirements 节：D1（技术文档质量，初15/终10分）、D2（演示与答辩，终10分，模板由主办单位提供）、R2（提交物、自部署与匿名，无独立分值但为硬性提交约束）、X1（终5分）。

### 1.8 当前状态（`progress/task_state.json`）

- R24 整卡：in_progress / partial（`:7269` 起附近 recovery_tasks.R24，切片 A in_progress/partial、B pending/not_started）。
- 切片级：R24-A:T55 / R24-A:T56 / R24-A:T59 全部 pending、evidence=[]（tasks.T55/T56/T59 的 slice_acceptance，task_state.json:3776-4001）。
- R24-A 的全部前置切片 pending：R22:T52/T53/T54、R18:T51、R21:T47、R21:T48 均 pending/evidence=[]（tasks.T52/T53/T54/T51/T47/T48 slice_acceptance；R22/R23 recovery_tasks 均 pending/not_started）。
- R00:T00、R00:T01 已 accepted（tasks.T00/T01 slice_acceptance，evidence 含 reports/tasks/R00.md、reports/reviews/recovery/G-A-R00-review-1-recheck.md）→ 独立准备节点 R24-document-skeleton 的前置已满足。

## 2. 候选材料清单

逐项格式：名称 / 现状（file:line） / 对应验收条款 / 前置依赖 / 缺口 / 能否零人工推进。

判定口径："能"=不依赖人工输入、人工资源窗、外部模板或未完成的正式评测即可开工的整理/构建动作；"部分"=可做其中不依赖缺口的部分；"否"=被人工/外部/前置硬阻塞。

### 2.1 R24-A:T55 技术报告面（D1/R2/X1）

| # | 名称 | 现状 | 验收条款 | 前置依赖 | 缺口 | 零人工 |
|---|---|---|---|---|---|---|
| C1 | 报告章节骨架（docs/report/） | **不存在**：docs/report/ 目录不存在（ls 实测）；骨架允许提前建（12_recovery_task_cards_20261014.md:21、:264"骨架可早建"） | T55 §4.1（前1—2页核心预览，架构/Agent/三模块/选型/流程/实现/核心代码/效果/测试/创新）；manifest independent_preparation allows | R00:T00/T01 accepted（已满足）；其余无 | 目录与全部章节未建；不得预填 T53/T54 未产出的数值（T55 §4.3"结果只引用真实run_id；未完成正式评测保持待补与缺口"） | 能（只建骨架+待补标记，不填结果） |
| C2 | 架构/ER/流程/时序图 | **无任何成品图**：docs/ 无 .png/.svg，全 docs/ 仅 `docs/plan/11_full_delivery_recovery_20261014.md` 含 mermaid 一处；可用素材存在：README.md:3-30（进程表/启动事实）、docs/design/recovery_hacker_workbench.md:1-74、docs/decisions/CR-R01.md…CR-R20_secret_registry_extension_batch21.md（22+ 变更单）、docs/runbooks/*.md 3 份 | T55-C02（图中组件/接口与实际仓库一致）、T55 §4.2（不存在的组件不画成已实现） | 无（对照实际代码自绘） | 零图；绘制工作未开始 | 能 |
| C3 | 真实 run_id 结果与"效果"章节数字素材 | **部分存在（非正式评测口径）**：reports/runs/ 共 365 个真实运行目录；可引用例：reports/runs/batch21_single_container_smoke/attempt7_run.txt:1-4（主路径冒烟 exit 0、迁移/夹具/评估/幂等/健康六断言全过，PROVENANCE.md 同目录）、reports/runs/story_fixture_20261023/（story-result.txt、verify_story.py 输出）、reports/runs/batch21_integration_unlocked/*_pf.txt（107 文件真实 exit code）；正式评测（R22）0 条 | T55-C03（没有实验结果显示未测，不写预期为实测）；R24 核验④（所有数字可回到原始日志） | R22:T52/T53/T54（正式评测/验收/运行报告，均 pending） | 正式指标全缺；现有素材只支撑"已完成工程与真实运行记录"叙述，不能支撑准确率/召回率/6小时时效结论（README.md:6-8 已有同口径声明可沿用） | 部分（现有 run 证据可整理成索引；正式数字必须待 R22，且 T55-C03 要求显式标"未测"） |
| C4 | Word/PDF 可复现生成路径（scripts/documents/） | **不存在**：scripts/documents/ 目录不存在（ls 实测） | T55 §4.5（Markdown→Word/PDF 方案选定并锁定，渲染检查分页/表格/字体/图引用）；T55-C04 | 无（工具链选型可离线做；渲染执行需工具环境） | 全缺 | 部分（选型+脚本骨架能离线做；实际渲染验证需环境与真实内容） |
| C5 | reports/acceptance/t55_checklist.md | **不存在**（reports/acceptance/ 仅 t00/t01_checklist.md 与 devkit_materialization.md） | T55 §3"这是需要本任务创建并实际执行的位置" | 随 A:T55 实施创建 | 全缺 | 能（按 C01–C06 建检查表，执行状态如实 not_run/partial） |
| C6 | reports/acceptance/document_review.md（独立文档试部署记录） | **不存在** | T55 §4.6（由未开发模块的人员/审查Agent依文档试部署，记录不足）；manifest R24-A:T55 描述"新独立文档试部署先完成" | 报告候选成稿 + 独立审查者 | 全缺；此为 R23 前置动作之一 | 否（依赖独立试部署者，非实施者自签） |
| C7 | reports/tasks/T55.md 任务报告 | **不存在**（reports/tasks/ 现有 T00–T23 与 R 卡，无 T55.md） | T55 §7 | A:T55 实施 | 全缺 | 部分（框架可建，证据栏随实施填） |

### 2.2 R24-A:T56 演示面（D2/R2/X1）

| # | 名称 | 现状 | 验收条款 | 前置依赖 | 缺口 | 零人工 |
|---|---|---|---|---|---|---|
| C8 | 演示脚本/连续用户故事（docs/demo/、scripts/demo/） | **不存在**：docs/demo/、scripts/demo/ 目录不存在；可复用素材：scripts/load_main_path_story.py（主路径夹具故事）、scripts/smoke_main_path.py（0/1/2 退出码合同）、scripts/dev_single_container.py（OQ-1 单容器回环路线） | T56 §4.1–4.3（覆盖来源/富化/问答/推荐/Agent/更新/性能/工程/文档；现场可改输入走真实后端；区分实时/回放/fixture/缓存/离线） | 产品可运行状态（批次21 单容器冒烟已证 attempt7 exit 0，见 C3）；正式评测不阻塞脚本编写但阻塞"效果展示"口径 | 全缺；"现场改资产版本"演示依赖真实规则引擎可用路径 | 部分（脚本与模式标识可写；真实后端联排需运行环境） |
| C9 | 主办方 PPT 模板 | **未取得**：T56 §2"需要主办模板"；R2 条款"模板由主办单位提供"（contracts/requirements.json R2）；交接记载"PPT用户后置"（progress/context_handoff.md:23 等） | T56 §4.4（模板未取得先准备内容纲要，不假称符合）；R24 完成证据"材料缺模板/人工信息明确阻塞"（:269） | 外部：主办方提供模板 + 用户解除后置 | 模板缺席是显式阻塞，不得伪造符合性 | 否（模板）；内容纲要部分可做（能） |
| C10 | PPT 内容纲要与匿名副本流程 | **不存在** | T56-C04（正文/备注/截图/metadata 无识别信息）；T56 §4.5 | C9 模板（匿名检查需真实模板字段）或先做纲要 | 全缺 | 部分（纲要能；匿名扫描工具与终检不能） |
| C11 | 演示视频 | **不存在** | T56-C05（真实软件操作且文件可播放）；T56 §4.6；R24 实施"备用录像注明彩排"（:267） | 录屏环境 + 人工演练 + 产品可运行 | 全缺；录屏与演练本质人工 | 否 |
| C12 | reports/acceptance/t56_checklist.md、reports/acceptance/demo.md、reports/tasks/T56.md | **均不存在** | T56 §3、§7 | 随 A:T56 实施 | 全缺 | 能（建表，状态如实） |

### 2.3 R24-A:T59 候选交付清单面（E1/D1/D2/X1/R2）

| # | 名称 | 现状 | 验收条款 | 前置依赖 | 缺口 | 零人工 |
|---|---|---|---|---|---|---|
| C13 | candidate_delivery_manifest（R24-A 输出 artifact） | **不存在**：manifest 声明为 R24-A 唯一 output_artifact；R23 requires_artifacts 消费它 | manifest work_packages["R24-A"].output_artifacts；R24-A:T59 切片描述"候选交付清单/材料hash与审查证据索引" | A:T55/A:T56 候选实际成稿 | 全缺 | 否（本体依赖候选材料先存在；清单 schema 可先起草——部分能） |
| C14 | 制品 hash 清单 | **不存在** | T59-C01（hash可核对且绑定实际代码/结果版本）；T59 §4.1 | 候选制品集合 | 全缺；机制（sha256 清单脚本）可离线建 | 部分 |
| C15 | 提交包秘密扫描 | **机制已在仓库**：scripts/security_scan.py、backend/tests/security/test_r20_secret_provenance.py（R20 冻结登记 136→190 条，OQ-3/OQ-6 记录于 progress/OPEN_QUESTIONS.md）；扫描对象（提交包）不存在 | T59-C03（包中秘密或holdout答案阻止发布）；R24 核验⑥ | 候选提交包本体 | 包不存在；对包的扫描 not_run | 部分（对现有仓库面可复跑登记内机制；对提交包须待包） |
| C16 | 许可证与来源记录 | **部分存在**：依赖锁文件（backend pyproject/uv.lock 等）、README.md:91-94 结尾限制声明、docs/decisions/ 22+ 变更单可作来源记录底稿 | T59 §4.4；R24 核验⑥ | 无 | 未做提交包口径的许可盘点 | 能 |
| C17 | reports/acceptance/t59_checklist.md、release_checklist.md、progress/final_handoff.md、reports/tasks/T59.md | **均不存在** | T59 §3、§7 | 随 A:T59（清单候选部分）与 B:T59（最终冻结）分阶段 | 全缺 | 部分（t59_checklist 骨架能建；final_handoff 属最终冻结，归 B） |

### 2.4 跨切片支撑材料（R24 核验⑤ 复现手册面）

| # | 名称 | 现状 | 验收条款 | 前置依赖 | 缺口 | 零人工 |
|---|---|---|---|---|---|---|
| C18 | 接入与复现手册（docs/runbooks/ 扩充） | **部分存在**：docs/runbooks/recovery_backup_restore.md:1-51、docs/runbooks/source_polling.md:1-15、docs/runbooks/annotation_preparation.md:1-74；安装/SDK/MCP/插件复跑手册无 | R24 核验⑤（安装、SDK、MCP与插件示例可复跑）；T55-C05（按文档干净部署命令与实际行为一致） | 产品默认装配可用（批次21 冒烟证据在案）；SDK/MCP/插件端到端受 OQ-4（公开 /tasks producer 链未立项）等影响 | 安装类手册素材足；SDK/MCP/插件复跑章节受公开面未闭环影响，只能如实标边界 | 部分 |

## 3. 缺失项与前置依赖链汇总

R24-A 正式开工（以官方口径产生可交 R23 的候选材料）的依赖链，全部在 `contracts/task_manifest.json` recovery.work_packages 与 `progress/task_state.json` 可核验：

1. R22:T52/T53/T54（正式评测、端到端验收、真实运行）→ pending/not_run。R22 又依赖 R19 冻结（人工双人标注/裁决，OPEN_QUESTIONS.md OQ-5"0 gold 如实保持"）与 R20/R21 通过。
2. R18:T51、R21:T47/T48（工程切片）→ pending/not_run。
3. 上述全部 accepted 后，R24-A 的 requires_slices 才闭合，才能"引用 R22 证据"产出候选报告/PPT/视频/手册。
4. R23 消费 R24-A:T55/T56/T59 + candidate_delivery_manifest；R24-B 消费 R23:T57/T58 后冻结。

不受该链阻塞、已解锁且仍未做的独立准备：R24-document-skeleton（after R00，requires R00:T00/T01 均已 accepted）——即本清单 C1/C2/C5/C7 类骨架与 C16 许可盘点。这是当前唯一"合法提前量"，且尚未动工（docs/report/ 不存在）。

外部/人工阻塞项（不得伪装在线或自动达成）：C9 主办模板（外部）、C11 视频录屏与演练（人工）、C6 独立试部署（非实施者）、R19 人工金标（间接经 R22 阻塞正式数字）。

## 4. 本批边界与 R24-A 真正开工的第一步建议

本批只整理，不实现：未创建 docs/report/、未写任何脚本、未运行 pytest、未改任何业务文件、未升级任何任务状态（R24-A:T55/T56/T59 维持 pending，R24 维持 in_progress/partial）。

R24-A 真正开工时的第一步建议（按序）：

1. **确认前置**：核验 R22:T52/T53/T54、R18:T51、R21:T47/T48 已 accepted 且 candidate 证据（正式评测原始结果）可被报告引用——这是 manifest requires_slices 的硬条件；此前只允许做骨架层（independent_preparation allows 范围内）。
2. **先建骨架与图**：创建 docs/report/ 章节骨架与 t55_checklist.md，从实际代码绘制架构/ER/流程/时序图（C1/C2/C5），正式评测数字位全部显式"待补/未测"，不得预填（T55 §4.3、T55-C03）。
3. **锁定渲染工具链**：scripts/documents/ 选定并锁定 Markdown→Word/PDF 方案（T55 §4.5），在真实内容就位前用占位文档验证渲染器本身。
4. **演示面并行最小化**：写 docs/demo/ 脚本与模式标识（实时/回放/fixture/离线），PPT 模板缺席按 T56 §4.4 只做内容纲要并登记阻塞，不伪造模板符合性（C8/C9/C10）。
5. **清单 schema 先行**：起草 candidate_delivery_manifest 的 schema（hash 字段、审查证据索引、来源记录），候选制品落盘后即可填充（C13/C14）。
6. **全程纪律**：R24-A 完成≠R24 完成（保持 partial/in_progress）；候选材料交 R23 前须有非作者独立文档试部署记录（C6）；秘密扫描、匿名检查在候选包冻结前必须真实执行并留证据（R24 核验⑥）。

## 5. 引用文件清单（全部为只读核验对象）

- 合同与计划：contracts/task_manifest.json、contracts/requirements.json、docs/plan/00_execution_map.md、docs/plan/11_full_delivery_recovery_20261014.md、docs/plan/12_recovery_task_cards_20261014.md、docs/plan/09_operations_delivery.md
- 任务卡：docs/tasks/T55_technical_report.md、docs/tasks/T56_demo_and_slides.md、docs/tasks/T59_release_handoff.md
- 状态与交接：progress/task_state.json、progress/context_handoff.md、progress/recovery_workstreams.md、progress/OPEN_QUESTIONS.md
- 批次上下文：reports/tasks/Root-batch22-plan.md、reports/runs/batch22_timeline.md
- 证据样例：reports/runs/batch21_single_container_smoke/（attempt7_run.txt、PROVENANCE.md）、reports/runs/story_fixture_20261023/、reports/runs/batch21_integration_unlocked/
- 既有可复用素材：README.md、docs/design/recovery_hacker_workbench.md、docs/runbooks/*.md、docs/decisions/CR-*.md、scripts/verify_plan.py、scripts/security_scan.py、backend/tests/security/test_r20_secret_provenance.py

（本文件由批次22 目标3 材料整理员创建；全部结论可按上述 file:line 复核。）
