# Root · 零人工自主收敛 终局报告（批次21–22）

文档首次创建时间：2026-10-25T06:30:00+08:00
本次写作开始时间：2026-10-25T06:30:00+08:00
最后更新时间：2026-10-25T06:30:00+08:00
工作分支：codex/full-delivery-recovery；导入前 HEAD 6c9bb455c，收束 HEAD 8e69c9973（+本报告提交）。两批次均已 push（6c9bb455c..fb0b97c7a、fb0b97c7a..8e69c9973），推送均通过秘密/tsbuildinfo/holdout 门，未 force。

## 一、各批真实数字

### 批次21（C0–C7，总结 reports/tasks/Root-batch21-summary.md）

| 项 | 结果 |
| --- | --- |
| C1 单容器冒烟 | attempt7 真实 exit 0（六组断言全过）；根因=str(URL) 密码掩码（已修，三重证据） |
| C3 历史红清零 | 三份 CR（R20 136→190 / codec -2 / head 0031）；C3.4 全量 6080 passed / **0 failed** |
| C2 integration | 107 文件逐文件真实 exit+数字（run6：56 绿 / 1103 passed / 74 failed / 511 errors）；unlock_v2 6216 passed / **0 errors**（A2 解锁达成）；16 文件有据排除 |
| C4 审查 | R-A/R-B/R-C 三份独立审查，13 条 needs_changes 全部闭环 |
| C5 | R10 消费者（171+5 绿）/ producer 盘点（/tasks 缺口 OQ-4）/ R19 装配（0 gold，10+69 绿）/ R21 评测骨架（19 绿，B0 端到端绿） |
| C6 质量门 | backend 终局 6253 passed / 0 failed / 83 设计内 blocked；ruff/format/mypy 全 0；前端四门全 0 |
| C7 | 总结/handoff/task_state（R06.unit 依 R-C 建议改判 passed，整卡 needs_changes）/12 提交/1 push |

### 批次22（总结 reports/tasks/Root-batch22-summary.md）

| 项 | 结果 |
| --- | --- |
| 目标1 (d) 类 | 甄别（66/72 同源三家族）→ CR 种子对齐（9 文件，零断言值/零产品/零 legacy 改动）→ 容器 46 failed → **6 failed**（净修复 40：33 种子转绿 + 7 trace 读写分离）；宿主全量 6252 passed / 0 failed（1 例 r07 家族抖动复跑 3 passed） |
| 目标2 SourceEnricher | 触合同停止（OQ-6：三条路径全触冻结断言/公开 DTO，零代码改动） |
| 目标3 R24-A 材料 | 18 条候选清单；开工被 R22:T52/53/54+R18:T51+R21:T47/48 accepted 硬阻塞 |
| 目标4 拓扑 | 自由文件独立库实证（串扰消失）；审计族三层前置条件两层已解一层按纪律停止；pgvector 0.8.2 不可钉（pgdg main 无该版本） |
| D 类取证 | 3 例 error_code 级证据落盘（见 OQ-5 增补）——全部为产品行为/冻结 oracle 裁决项 |

## 二、离线与集成最终状态

- **离线全量（tests/unit+contract+security，宿主）：6252–6253 passed / 0 failed / 1 xfailed / 83 设计内 blocked**（对照批次21 前基线 5928 passed / 19 failed / 42 errors：failed 19→0，passed +325，errors 全为设计内 blocked 的显性化）。
- **integration（单容器逐文件）**：107 文件全部有真实 exit+数字；批次22 后 (d) 类 74→6 failed；剩余非绿四类全部有记录（见 OQ-5）。
- **smoke（单容器）**：exit 0。
- 未运行（如实）：live、6 小时采集、compose profile 宿主验证、R19 人工标注、R22 资源窗依赖项、R24-A 实做。

## 三、OQ 全量清单（progress/OPEN_QUESTIONS.md）

| OQ | 主题 | 状态 |
| --- | --- | --- |
| OQ-1 | 宿主 WSL2/Docker 虚拟交换机 | 冒烟经单容器路线解决；宿主修复归用户 |
| OQ-2 | content_read_worker 子进程导入 | 已解决（6c9bb455c，勘误标注） |
| OQ-3 | t06 54 处分类 | 已解决（批次21 C3.1 落地，136→190） |
| OQ-4 | /tasks typed-task producer 链 | 待立项评审 |
| OQ-5 | R19 人工依赖 + C2 长尾 | 详见该条（含批次22 增补：3 项评审裁决、2+1 例取证结论、pgvector、审计族预置） |
| OQ-6 | SourceEnricher UTF-8 预算 | 触合同停止，待变更单立项评审 |

## 四、遗留给用户的决定清单

1. **评审裁决三项**（OQ-5）：r05 legacy-0013 种子可读性 vs fail-closed（19 例）；r04_source_documents evidence 计数 2→4（合同演化，1 例）；公网读错误码映射 public_read_unavailable vs 冻结 not_configured（5 例，产品行为）。
2. **变更单立项评审两项**（OQ-4/OQ-6）：/tasks typed-task producer 链；SourceEnricher 行为级预算约束。
3. **R21 口径**：config_sha256 跨基线语义确认（OQ-5）。
4. **资源窗**：R19 人工标注窗（工具已就绪，1 real+20 synthetic 种子 0 gold 待标注）；R22 隔离资源窗（R24-A 硬前置）；6 小时采集窗。
5. **宿主环境**：WSL2/Docker 虚拟交换机修复（compose profile 宿主验证恢复后，compose-based 测试面与 25432 预置库路径可回归宿主）。
6. **阶段门**：G-C 及后续阶段放行（本两批全部产物为 awaiting_review，无任何 accepted）。
7. **候选池大件**：多跳问答、推荐历史与变化重判、MCP/OAuth/CLI 三插件、安全/CI/索引恢复框架——均为多日特性开发，建议逐项立项（目标/步骤/验收/不做清单）后再排批。

## 五、目标达成对照（GOAL 判据）

1. 离线全量 0 failed ✓；error 全为设计内 blocked 且在 OQ-5 有记录 ✓
2. integration 与 smoke 真实执行证据 ✓（107 文件 + attempt7 + unlock_v2 error=0）
3. 历史红三件套清零 ✓（CR+复核记录）
4. C5 及后续 backlog 每项完成或触合同记录停止 ✓（无无记录跳过）
5. 状态文件同步 ✓（timeline×2/OQ×6 条/handoff×2 条/task_state R06.unit）
6. 全部 commit ✓（工作树仅 .zcode/）；push ×2 通过门禁 ✓
7. 本终局报告 ✓

收束说明：候选池剩余大件（四、7）非人工输入阻塞，但每项为多批次规模的特性开发，须先立项评审再排批——本两批已把"可原子完成、有验收判据、不触合同"的自主项全部消化并逐项记录；继续无立项的大件开发违背仓库自身的评审节奏纪律。据此进入收束轮：以上清单即全部遗留。

本次写作结束时间：2026-10-25T06:30:00+08:00；本报告为两批有界收敛轮的证据索引与收束声明，不是阶段验收（无任何 status 被写为 accepted）。
