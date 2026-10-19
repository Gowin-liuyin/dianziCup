# G-C / R06 · 六小时重启部署守卫独立审查 1

What this change does: 本切片为固定产品 `e310f7735bd499c4d9fbcefe8a644e2309a16a62` 的有界来源运行增加部署入口 gate、来源 producer 的 PostgreSQL 预停 fence、实际 worker/beat 停止确认与 Windows OwnedJob 资源约束。它只准备新采集段；没有完成来源 live、连续六小时、R06/R20 整卡或 G-C 最终验收。

最终审查对象 `44c94151840213d9e5ab7c653778d4ae3219c630`，基线 `b08824f738ca185776916ae02689d8507f956c5c`；原对象 `bae3138d103427d659d7fdc0a8a195088dd42f2e` 的红证据全部保留。独立 WT `D:/wt/r06-live-restart-review1` 初始分支 `codex/r06-live-restart-review1` / clean，最终只读 checkout 为 detached 44c9415，自有报告/run 为唯一未提交项。R06 重启准备切片原 `awaiting_review`，本审查完成并限定 **Ship**；整 R06/R20/G-C、live 及六小时状态未提升。审查者不是本切片作者；没有改产品、原测试、observer、合同、limits、金标、progress 或 accepted，没有提交、push、启动 live/source/model/provider，也没有 spawn。

已读 AGENTS、执行地图、恢复 R06/R20/R22 卡、T16/T49、04/06/09 引用合同、CR-R06 及自动轮询合同、状态/交接和作者报告；按 ponytail-review 5.2.0 追踪实际调用。产品独立 WT `D:/wt/r06-live-e310-20261016` 的 HEAD 和空 status 已核实。131 秒真实产品 API 正负例 → consume_job 组合验证由独立报告 `D:/wt/gc-e310-regression/reports/reviews/recovery/G-C-integrated-e310-validation.md` 提供；本报告不重复计为自己执行的检查。

## 原 Must 与独立复验（已关闭）

下面保留 bae 的具体触发、影响和最小修复要求。最终44c9415把后代OpenProcess无法确认变为OwnershipError，取消主actor已退出的early return，并使stop_actor正常有/无ACK结束分支均执行后代核验；两条已用原探针独立复验关闭，没有未解决Must。

1. **后代访问拒绝被当作成功停止**（冻结 `windows_actor.py:L94–98`，`stop_controller.py:L76–80`，`controlled_supervise.py:L341–364`）
   - What this is: 守卫先停止实际解释器，再核对后代的创建时间并按内核句柄结束后代；上层只有收到停止错误才触发整个自有 Job 的 fail closed。
   - Problem: `OpenProcess` 返回空句柄时直接 `continue`，没有区分已结束、访问拒绝和未知。独立本机真实 Python 树中，仅对已验证自有后代注入 error 5；主解释器 PID 10384 已退出，三个预持有后代句柄（45640、45144、15704）仍为未退出，`kill_owned_tree` 却无异常，因而不会走 whole-job fail closed。后代本次只 sleep，未做外部调用；这是停止确认失效的实证，不是假设已经发生来源请求。
   - Fix: 在可验证的句柄上确认退出；不能取得或确认身份/退出的后代抛 `OwnershipError`，由现有自有 Job fail closed 接管。不能以 PID 消失推定成功，也不能按数字 PID 盲杀。给此分支增加有真实后代句柄存活断言的回归，再由独立探针复验。
   - If we skip it: 观察器会在后代尚存活时收到“producers stopped”的终态请求，无法证明来源 actor 及全部后代已停止。证据 `permission_denied_descendant.json`；自有预持有句柄已用于清理并确认退出。

2. **主解释器已退出便跳过全部后代确认**（冻结 `windows_actor.py:L78–80`、`stop_controller.py:L67–68`）
   - What this is: 正常/竞态停止路径会在主解释器的持有句柄确认退出后返回结束收据。
   - Problem: `kill_owned_tree` 对已退出 actor 直接返回，`stop_actor` 的 exited 分支也不会核对后代。独立第二个真实 Python 树中先用已验证主 actor 句柄结束 PID 22812 并 wait 确认，再调用该函数；后代 29848、34004、8892 的预持有句柄仍未退出，函数仍成功返回。`already_exited_actor_recheck.json` 保存全部事实。
   - Fix: 让主 actor 已退出/正常 warm exit 路径也确认其自有后代结束；不确定则进入原 whole-job fail closed。复验必须持有真实后代句柄，单断言 launcher 或 main PID 退出不够。
   - If we skip it: 主 actor 的退出仍会被误当作整个 producer 树结束，修复第 1 条的 OpenProcess 分支也不能覆盖此提前返回。

## 真实复跑与边界

所有合成进程都属于本审查创建的 Windows Job，沿用 20% host CPU、512 MiB/process、2 GiB aggregate 及 kill-on-close；没有打开端口或碰共享/global 服务、WSL 服务或 IAB。仅 CBM 官方 CLI 读取本审查/产品源码树；没有启动新服务。自有 kernel handles 用于实际 PID、创建时间、终止与 wait 验证；未打印其它机器进程信息。

| 检查 | 实际结果与时间（Asia/Shanghai） |
|---|---|
| 冻结两份 guard unittest | 2026-10-16 05:56:09.538–05:56:17.219，命令 wall 7.687 秒；unittest 29/29、5.761 秒、0 skip、exit 0。原测试不包含上述两处活后代确认断言。 |
| 缺 gate 完整 entry / supervisor CLI | 同一复制的冻结 9 脚本，本审查目录内运行；exit 1 / 1；supervisor 仅写 started=false、details=withheld 收据，无产品环境访问、PG 或服务启动。 |
| 六个独立负例 | false gate、缺 gate 的环境拒绝哨兵、错误 frozen product、无效 stop 合同、含 URL/secret 的 PG 异常、stop-before-PG-claim 均阻断；false/missing gate subprocess 0，PG 异常 WorkerShutdown 70 且原 URL/secret 未落 receipt，stop-before-claim PG connect 0。 |
| 两个 task `.run` 实际部署接线 | 显式 in-process fixture，绕过gate仅供mocked产品imports；运行冻结deploy入口绑定两个任务后逐个调用，均抛WorkerShutdown 0、原consume/poll调用0、PG connect0。不是产品live/模型或broker测试。 |
| 实际 worker/beat ACK | 05:58:45.441–05:58:48.509，两个真实合成解释器；worker 29984 / creation 134365751255435356，beat 43848 / creation 134365751255479145；ACK 相符、持有句柄确认 exit、launcher exit 0；停止 0.110 / 0.047 秒。无 broker 或 source consumer。 |
| 后代 OpenProcess 拒绝 | 实际 actor 与后代树，访问拒绝只注入到事先确认身份并持有句柄的自有后代。上述第 1 条复现，0 source/model/provider。 |
| 已退出 actor | 06:03:54.822–06:03:56.123 的纠正仪器复跑 exit 0，第 2 条仍复现；首探针 06:03:33–34 cleanup 因 descendant launcher 自然退出竞态出现 AssertionError / exit 1，保留原 JSON，外层 OwnedJob 随进程结束 fail closed。修正仅自己仪器：Terminate 返回 false 时，必须真实 wait 确认退出，不能盲当成功。 |
| 最终冻结两文件 unittest | 06:07:39.088–06:07:50.976，wall 11.891 秒；31/31、unittest 10.753 秒、0skip、exit0。保持原29并新增两个真实后代回归，访问拒绝参数化覆盖主actor先/后exit。 |
| 最终两个缺 gate CLI / 六负例 | 06:07:50.988–06:07:51.260，CLI exit1/1；同六负例重新通过。两task `.run` 的显式fixture也复跑，原函数/PG调用0；0环境产品读取/服务/wire。 |
| 最终原访问拒绝探针 | actual actor39196退出、预持后代16432/33204/42680仍alive时，正确抛 `owned descendant exit could not be confirmed`；bug_reproduced=false，交由wholeJob接管，后续仅自有句柄清理。 |
| 最终原已退出 actor 探针 | 06:07:59.564–06:08:02.305，actor2900先exit，后代40832/25996/45884全部由预持有handle确认exit；bug_reproduced=false，exit0。 |
| 最终实际 ACK | worker24556 / creation134365756751538536、beat37628 / creation134365756751601692，PID+creation匹配，实际handle/launcher均exit；0.828/0.672秒 stop（含后代核验）。 |
| 真实 whole-job fail closed | 06:08:58.137–06:08:59.526，1.391秒；在可丢弃嵌套OwnedJob中执行冻结supervisor exact AST finally分支，显式注入OwnershipError。actual21412及三个自有后代预持handle全部exit，launcher70；官方failure receipt actual_stop_confirmed=false / observer_terminal_guaranteed=false；collector_stop.request没有生成。是失败分支fixture+真实kernel效果，不是完整supervisor部署。 |

命令、cwd、退出码、墙钟、raw SHA 见本审查 run 下 `commands.json` / `cbm_commands.json` / `cbm_trace_commands.json` 与对应日志。主要命令为 `D:/dianzi-runtime-cache/r06-live-restart-20261016/runtime_env/.venv/Scripts/python.exe -B -m unittest test_runtime_controls.py test_windows_actor.py -v`，cwd 是本 WT 的冻结准备目录；其它自有探针脚本及实际参数随 run 保存。原作者 28→26、28→27 及 mypy Celery-stub 限制均留原材料，未抹成新通过。

## fence、预算和租约核对

源码与实际装配读取确认：`deploy_runtime_entry.py` 将 `ai_intel.jobs.execute` 和 `ai_intel.sources.poll_due` 的 `.run` 分别包装为 `require_producer_slot` → 原 `consume_job(job_id)` / 原 `poll_due_public_sources()`。原 consume 的 PG `execute_job`/`claim_job` 和 poll 的 `Session` 事务均在 fence 之后；stop 时抛 `WorkerShutdown`，没有返回 SUCCESS。实际安装 Celery 5.6.3 `synloop` 在 `maybe_shutdown` 的 `finally` 仍调用 `_loop_cycle` / `drain_events`，因此单独设置 should_stop 不能证明不会再开始任务；两个 source-producing 函数前置 stop fence 是必要的部署差异。

PostgreSQL `job_runs` 全部 `collect_public_source_page` 行数是唯一预算计数；不以 Celery result、历史 snapshot、fetch_attempts 或 response receipt 充当计数。count < 410 且 max(max_attempts) ≤ 3 才准入，原单 poll 事务遍历九固定源最多增九 root，单 page 最多增一 successor；在唯一 solo producer、无另一个 worker/REST submitter的合同前提下，最大409+9=418，下一入口拒绝，450 是包含旧11的 total cap。辅助 snapshot/ACK 37 行 race 估计不是最终预算证明。

e310 九源周期为 vLLM 1800 秒、其余八源 3600 秒，原 beat 60 秒/每轮最多5页。任意六小时起点保守根轮次 `8×7+13=69`，最多345新 page；声明的旧11和旧 pending 的14最大successor合计370，低于410预停。实际 PG 旧库存来自作者只读 inventory；本轮 gate 缺失，按授权不连接 PG，未把报告声明冒充本轮 PG 重测。

原 source GET 与 POST 重定向为0，source每attempt最多2 fetch，PG max_attempts 3；DoH 对 A/AAAA 各一次、默认最多6 wire hop；HTTP transport 固定首地址且无重试。故78 HTTPS/job、450×78=35100保守上界有源码依据。实际wire没有collector，仍 unknown；source费用 unknown，模型/付费provider预算0，root 最终预算/授权 gate仍缺失。raw容量宽上界约13.18 GiB，normalized容量/可用磁盘与 namespace/old PID/owned MinIO/daemon健康必须在启动前另核。

60 秒 PG lease、25软/30硬声明均未修改；当前新段 running 的实际 lease+5 是监督停止边界，不把65秒写成产品 hard timeout已证。35秒旧硬判断已取消；旧 running lease/历史只保留并由默认 PG 恢复。缺lease、异常长度、未来start或两当前running均fail closed。正常 ack给当前work有限完成，CPU/log/cap/未知 ownership应立即走硬失败；最终两个停止缺口已修复，kernel失败分支实证不代替实际服务运行。

## 冻结材料、CBM 与未验证项

三个原 observer 字节独立等于 `1c4cce9770bfa29d08728a0131f7fc7fe714f9bc`：observe SHA256 `11f23cd75c5e7ab0960e51b9e40099e3c5d1fe133b61956068489db0e797a698`，observation_log `33a38f98721d8abc74fdade6b7c74b4c408e42f632d8b37e4687d798b05124d1`，pg_snapshot `abaacb3a54e9f2c973f81f36e384557c7d19a3dcb3d8b63754632df866978596`。没有继续或拼接原131秒/47秒段。

bae 的作者 artifact_manifest 68 entries 中46条声明 raw hash 不匹配干净 checkout；checkout raw 与 frozen Git blob匹配68/68。初步人工清点曾误报47，完整逐blob审计纠正为46，明细保留在 `material_audit_bae.json`。最终44c9415的88 entries声明raw SHA/bytes及Git blob全部匹配，mismatch0；作者manifest SHA256 `39514c9e28397e2b9518b403c512c0442f3cf26164a6a5d932e9e174da1afda3`。原bae材料失败仍保留，不用LF等价强行通过；另外三个excluded freeze输出仍逐blob核对，只排除临时Ruff cache不充当证据。作者exact semantic diff（036fea→44c9415，5个具名文件）独立重建18840 bytes一致，SHA256 `ab511f52a1314b24849b658b6db5f8c263606a612410576ab08d980d3d840a71`。

官方 CBM 0.11.0 CLI 对本 review WT 执行 root fast index：首次因独立 ACK 证据在扫描时创建而 aborted_previous_preserved / exit1；冻结自有文件后重试107.140秒 exit0，108853nodes/153799edges，0skip/0unusable但21个旧报告 parse_partial，故不声称全图无缺口。排除 docs/fixtures 等21目录、256文件；仓外 secrets、工具cache和正式holdout未作为index输入。XDG变量未改变工具回报的默认仓外cache位置，实际log在 `/home/ubuntu/.cache/codebase-memory-mcp/`；未写repo持久化artifact。首次短名deploy trace ambiguous / poll qualified name不存在的红结果保留；按返回的exact qualified name后deploy/fence trace成功。

另独立索引clean e310 `backend/src`，避免把b088工具WT中的产品代码当e310；1458nodes/7535edges，0skip/partial/unusable，排除ai_intel/assets。exact poll/consume trace与rg交叉确认入口→source poll/enqueue/outbox及consume→execute_job/claim。工具目录graph对内嵌closure漏边且有不相关heuristic候选（如frontend text）；这些未当接线证明，接线由冻结源码和显式fixture实际调用核对。图是静态辅助证据，不代表部署/真实IO成功；新版变动再按exact文件rg及冻结diff核对。

本轮 source HTTP、model/provider、产品PG connection、服务启动均0。真实产品部署集成、provider auth live、MinIO对象写入、source覆盖、真实queue/finalizer运行、实际lease超时、六小时窗口、严格CPU四旧红复测、完整安全/工程/阶段/manual均 not_run。原 e310 独立报告保留 1CPU严格CPU边界约1.03125秒失败；本轮未改timeout、CPU阈值、ready/wall口径或误称四红已过。

评分证据只支持 E1 受控准备/停止检查及 F1/P1 的有限调度预算设计，不新增来源覆盖、时效、准确率、连续时长或分数。无公共合同/业务计划变更；两个已有停止合同的实现缺陷已修复复验。改动仅本报告和具名自有run，其精确文件列表、raw SHA/bytes及源码Git证明见 `review_artifact_manifest.json` / `scoped_diff_identity.json` / `source_git_proof.json`。最终Ruff check/format（项目config，10守卫/测试文件）exit0；类型检查只覆盖authorization/runtime_controls，不冒称Celery类型或完整产品门通过。下项建议由root核实际预算/磁盘/namespace/旧PID/owned MinIO/daemon健康，签新的有限gate后再开始独立live段，正式六小时必须按实际新窗口统计。

Verdict: **Ship，仅44c9415的R06重启部署守卫准备切片；bae原红关闭。root live gate缺失，不启动。**

Not checked: 真实服务/来源/model/provider/六小时、完整R06/R20/G-C、严格CPU四红与最后预算/启动前环境条件；不能凭本准备审查授予这些验收。
