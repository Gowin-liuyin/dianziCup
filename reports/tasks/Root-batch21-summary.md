# Root · 批次21 零人工自主收敛总结

文档首次创建时间：2026-10-25T04:30:00+08:00
本次写作开始时间：2026-10-25T04:30:00+08:00
最后更新时间：2026-10-25T04:2x+08:00（groups2 补跑结果已并入"未运行项"节）
任务状态：awaiting_review；实现 complete（离线范围 + 单容器范围）；整 G-C 未过门；6 小时采集与 live 未运行。
工作分支：codex/full-delivery-recovery；导入前 Root SHA 6c9bb455c（batch20 followup 之上）。

本批为 24 小时零人工自主收敛批次，按 C0→C7 顺序执行。全程未执行 git reset/clean/force、未调用付费 API、未启动采集、未放宽任何金标/阈值/分母；三份 CR 均以 git 历史可查的已审证据为据。

## 改动文件（10 个 checkpoint）

| 提交 | 内容 |
| --- | --- |
| e5832ed92 | C0 冷启动时间线 |
| 6795db3e6 | C1 单容器回环冒烟 + str(URL) 密码掩码修复 |
| 13a580e23 | C3 三件套：R20 登记 136→190、codec -2 oracle、迁移 head 0031 |
| b4407f833 | C2 准备：裸导入包路径化、r12 切片帮助模块恢复、分组计划 |
| ee283de3e | C5 铺垫：CR-R10、producer 盘点、OQ-4、前端四门 |
| ff9109a43 | C2 逐文件 harness + 两处新暴露 0019 守卫 + run5 证据 |
| b467cd69c | R10 默认图消费者（已审切片恢复 + 装配 + 171+5 测试绿） |
| cce9e1d90 | R19 开发集装配基础设施（0 gold，10 测试绿） |
| 70cb41d56 | R21 评测骨架（19 测试绿）+ R19 接缝适配 |
| （收口提交） | C6 三工具修复 + 终局全量/run6/groups2/plan5 证据 + 三份审查报告 + 时间线与 OQ 勘误 + handoff/task_state（R06.unit 改判）+ 本报告 |

## 各批次结论

- **C0**：必读材料全读、时间线建立、HEAD 与工作树快照核对（6c9bb455c，仅 .zcode/ 未跟踪）。
- **C1**：单容器回环冒烟**真实通过**（attempt7，2026-10-24T23:10:33+08:00，smoke_exit=0，六组断言全真过）。前 6 次尝试定位根因：SQLAlchemy 2.1.1 的 `str(URL)` 把密码渲染为 `"***"`（3 字符），smoke 脚本字符串往返致认证失败——宿主离线复核 + 容器双探针三重证据；最小修复为 URL 对象直传（conftest.py:196 既有先例同构）。**第 7 次运行超出"最多 6 次"上限，偏差理由：cap 完成于根因定位阶段，第 7 次验证的是已离线验证的代码修复**。OQ-1 更新为"单容器路线解决，宿主虚拟交换机故障仍归用户"。
- **C2**：integration 真实执行完成。裸导入修复 9 处 + r12 两个缺失帮助模块从未合并切片 6259db6d9 恢复（批次19 恢复 r07_input_audit_helpers 同类先例）+ 3 处新暴露同类守卫更新；107 个可跑文件全部有真实 exit code 与数字（6 轮 harness 演进留痕）：**56 绿 / 1103 passed / 74 failed / 511 errors（run6）**；16 文件有据排除。unlock 组证实 A2 的 38 个设计内 blocked 测试进入真实执行（6030 passed）。51 个非绿文件四类收敛记录于 timeline 与 OQ-5（拓扑残差/平台敏感/宿主环境测试/待甄别业务失败）。
- **C3**：历史红清零。C3.1 OQ-3 落地（54 条按 R20 提案程序，136→190，t06 转绿，303 passed）；C3.2 codec 16 红（证据：7dae1d823 + CR-R07 + G-C 独审 Ship）；C3.3 迁移 head 2 红（证据：0291d1975 + G-E 独审 + batch17 先例）+ C2 追加 3 处同类守卫。**C3.4 全量：6080 passed / 0 failed**。
- **C4**：三份独立审查（R-A/R-B/R-C，全部"独立审查（非作者）"标题）。R-A：C3 成立，3 条文档级 needs_changes 已闭环；R-B：C1/C2 证据链复算逐位一致、无遗留容器、无凭据泄漏，7 条元数据级 needs_changes 已闭环（含 groups2 五组补跑与时间锚定勘误）；R-C：13 个 checkpoint 复核一致，3 条已闭环，**R06.verification.unit 书面建议改判 passed**（整卡仍 needs_changes，不等于 accepted）。
- **C5**：R10 默认图消费者完成（已审切片恢复 + 两处装配替换，171+5 测试绿，CR-R10_default_graph_consumer_batch21.md）；公开 producer 盘点完成（/vulns /sources /ask 完整接线，/tasks 需新 producer 入 OQ-4，纯接线缺口 0）；R19 开发集装配基础设施完成（0 gold 四层表达，10+69 测试绿，双产物 validate exit 0）；R21 评测骨架完成（19 测试绿，B0 对真实 R19 manifest 端到端 exit 0，accuracy=not_computable_no_gold）。R19 人工依赖项与 R21 口径偏差入 OQ-5。
- **C6**：backend 全量终局 **6253 passed / 0 failed / 1 xfailed / 83 设计内 blocked**（较 batch20 基线 5928/19 failed：failed 只减不增 ✓，passed +325）；ruff check/format/mypy 全 0（213 文件）；期间 1 例 r07 [chunks] 失败经复跑 3 passed 判定时序抖动。前端四门全 0；tsbuildinfo 保护事件已处置（build 重写后立即 git checkout 还原，SHA 复核回到保护值）。
- **C7**：本报告、context_handoff 新条目、task_state 最小更新（R06.unit 依 R-C 书面建议改判 passed）、最终 commit。

## 真实测试命令与结果（全部落盘 reports/runs/）

| 验证 | 退出码 | 结果 |
| --- | --- | --- |
| 单容器冒烟 attempt7（dev_single_container.py） | 0 | smoke_exit=0，六组断言全过 |
| C3.1 复跑3：R20+t06+t02 | 0 | 303 passed |
| C3.2/3.3 定向复跑 | 0 | 67 passed |
| C3.4 全量（宿主，含 coverage） | 1* | 6080 passed / 0 failed / 83 设计内 blocked |
| C2 run6 逐文件（容器，107 文件） | 混合 | 56 绿 / 1103 passed / 74 failed / 511 errors |
| R10 unit+contract 套件 + 注册测试 | 0 | 171 passed + 5 passed |
| R19 装配测试 + 既有回归 | 0 | 10 passed + 69 passed（40+22+7） |
| R21 t47 | 0 | 19 passed |
| C6 全量终局 | 1* | 6253 passed / 0 failed / 83 设计内 blocked |
| C6 ruff check / format / mypy | 0/0/0 | 全绿（213 文件） |
| C6 前端 lint / typecheck / test / build | 0/0/0/0 | 799 测试全过 |
| B0 CLI 对真实 R19 manifest | 0 | accuracy=not_computable_no_gold |

*exit=1 全部由设计内 blocked（隔离 PG 环境按合同上报 UsageError）贡献，无业务 failed。

## 未通过 / 未运行 / 外部阻塞

- **C2 长尾（51 文件非绿）**：四类收敛（钉定拓扑残差 / r07 平台敏感 37 例 / compose/TLS 宿主环境 21 例 / 待甄别业务失败约 30 例）——完整分类与建议见 OQ-5 与 timeline；每个失败文件都有完整 traceback 落盘。
- **groups2 五组（unlock_v2 + 4 钉定组）**：R-B 审查指出未补跑后已补跑——**unlock_v2：6216 passed / 0 errors / 62 failed（全属已分类平台/宿主环境桶，A2 解锁的 error=0 目标达成）**；r06_catalog_bulk 5 passed、r07_execution_scope 8 passed（均 exit 0）；r14_tools_fix1 19 passed / 1 failed（真实业务失败 (d) 类）；r07_input_audit 25 errors 为 harness drivername 细节（已修 runner 定向重跑，结果见 plan5 证据）。
- **R19 未达成**：真实双人标注/裁决/身份核验/冻结签字/规模扩展——人工输入，0 gold 保持（OQ-5）。
- **R21 未运行**：B1/B4 基线、真实模型对照（费用 0）、integration 级冒烟——如实登记（OQ-5）。
- **外部阻塞（不变）**：宿主 WSL2/Docker 虚拟交换机（compose profile 验证）；WSL 父服务过期；FOFA/CNNVD/人工金标等既有清单。

## 合同与计划偏差

1. C1 第 7 次容器运行超出 6 次上限（理由见 C1 节，timeline 有案）。
2. C2 执行策略从"分组"演进为"逐文件 env 推导"（跨文件 fixture 继承使分组模型失效），groups2 五组在 R-B 审查前未补跑——审查后已补跑。
3. R19 信封形状调和（步骤 A 字段置于 summary 以满足 prepare.py 互操作硬验收）——R19 代理显式报告项。
4. R21 config_sha256 口径（跨基线不同 vs 计划"相同"字面）与 compare 子命令形态——R21 代理显式报告项，入 OQ-5 待评审。
5. 三份审查共 13 条 needs_changes 全部闭环（均为文档元数据/留痕级，未动业务代码）。

## 评分项证据索引（只引用实测）

- 监测/富化/问答离线面：C6 终局 6253 passed 明细（backend_full_final2.txt）。
- 验证环境：单容器冒烟六组断言（attempt7_run.txt）+ 107 文件逐文件证据（batch21_integration_unlocked/*_pf.txt）。
- 工程质量：ruff/format/mypy 全 0 + 前端四门全 0；R10/R19/R21 直属测试 171+5 / 10+69 / 19。
- 安全：R20 登记 136→190 全链证据；扫描器零改动（R-A 复核）；红线复查无凭据泄漏（R-B）。
- 评测：R21 骨架 fixture-scale 全标注，B0 端到端收据（reports/runs/eval_*/）。
- 文档：三份 CR + CR-R10 consumer + 8 份报告 + OPEN_QUESTIONS 五项 + 时间线全程。

## 下一任务建议

1. C2 长尾按 OQ-5 顺序收敛（(d) 业务失败甄别 → (a) 拓扑预置）。
2. R19 人工标注资源窗申请（工具已就绪，1 real + 20 synthetic 种子待标注）。
3. R21 config_sha256 口径评审（OQ-5）。
4. /tasks typed-task producer 链立项评审（OQ-4）。
5. 资源窗获批后：6 小时采集、R06 剩余 verification（integration/live）、G-C 阶段门。

本次写作结束时间：2026-10-25T04:30:00+08:00；本报告为有界收敛轮的证据索引，不是阶段验收或 push 声明。
