# G-C / R06 · 原生进程快照新独立初审

首次报告落盘 **2026-10-17T06:20:19.1147291+08:00**（真实文件CreationTime）；审查结果 **needs_changes / partial**。审查者 `/root/r06_native_snapshot_first_independent_review` 未参与此候选实现。采用 [Ponytail 5.3.1 review](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.3.1/skills/ponytail-review/SKILL.md)，另派只读调用链子审；本报告以亲跑结果为准，不自行写 accepted，不提交或 push。

这次变更以 Windows Toolhelp32、GetProcessTimes、QueryFullProcessImageName 取代共享 process_tree 的整机 CIM，并让停止名称选择消费同一份快照。未知 birth 的行保留；终止仍使用绑定出生时间和 Job 的 held handle。正常原生7例及真实三代关闭通过，但本轮新增合同负例证实：**已绑定未知 birth 的行，在父 PID 仍存在时可能被跳过，返回成功；另外两条未知解析抛错类型不符合批准合同。** 当前 c8/fdb 候选不能安装放行。

## 1. 固定范围与依据

材料 Git `a70e653a92771b6c077bbda8a8263721f83a55a5`；CORE `c8e94650b921a258e1df4050521d8abee88059ef`；OPS `fdb40bd56bf06d716f6a6b00b941ce0e03ce06b9`；Product `912d8b381eaab9260ead30d68f49b88fa8078384`。真实新工作树：`D:/wt/r06-native-review1/codex/r06-native-review1`，以 `git worktree add --detach <该路径> a70e653a...` 建立；初始 tracked status/diff 为空，最终业务 tracked diff 仍为空。作者 `D:/wt/r06-native-snapshot/codex/r06-native-snapshot` 保持只读。

已读 AGENTS、执行图、R06 恢复卡、03 数据与05运行合同、材料 progress/task_state/context_handoff、作者 `R06-native-process-snapshot.md`、Root 尚未提交的 `D:/dianzi/docs/decisions/CR-R06_native_process_snapshot.md`（包含 **05:54:41.512+08:00** 定向关闭授权）、旧 failed-bootstrap CR、真实 CIM 诊断报告与相关调用源码。材料进度索引 R06 为 in_progress/partial；作者限定切片 awaiting_review，不据静态索引补签。

本轮修改仅本报告和 `reports/runs/r06_native_snapshot_review1_20261017/` 自有仪器、4个新合同用例、raw 收据和20文件公开 CBM 副本。没有改控制源码、原74/60/38 oracle、阈值、依赖、产品、状态、金标或评分分母。没有读取 Root installed/private/binding、秘密、holdout 或Source数据库，没有启动Source/PG/Redis/MinIO/WSL服务，付费请求0，wire/cost unknown。Root实际 ledger42/450、累计CPU19.15625和7flags没有读取或修改。

`fixed_verification` 与 `fixed_verification_after` 亲核23份候选源码和217份Product实际原字节；均 exit0。source_manifest raw SHA256 **`4d93914833883466dcf728e03c24ab394046a05cf8aab1e5a52e25bff3fae41c`** 精确匹配。新38中的freeze亲核四条变化路径（controlled_supervise、configuration、windows_actor、stop_owned）和另外十六份原控制字节；所有23候选源码与各固定 Git blob/raw SHA匹配。Product217的 raw 与 Git 字节各有独立清单，本次实际raw全匹配；217 raw≠Git是该冻结清单已有换行字节事实，不转为git字节或重新规范化。

pending RuntimeHash **`1a65d235d4774a528153c0199112b54ee01b497d3dbb8059341cfd9b92c82b19`** 匹配；其ready及七门全false、DB OID/COMMENT hash null、ledger offset42。这是待审公共清单，**不是实际安装binding**，不构成Root新审计/安装/七门证据。

## 2. 必须修复

1. **[P1] 父PID仍在快照时，已绑定未知birth能产生成功关闭证明**（`candidate/core/windows_actor.py:291–315`；`candidate/core/stop_controller.py:101`）。
   - 职责：终止后检查每个剩余行，只有完整Job名单在两时点证明不属于本Job、且与已绑定代次无关的未知孤儿才可略过。
   - 问题：remaining中的actor PID11为 `created=None,parent=7`，且PID7仍存在时，293行不进入孤儿分支，314行因 `pid==self.pid`直接continue；从未查询Job名单，kill_owned_tree正常返回。已知descendant22先绑定在generations后，其未知行的当前parent7存在但不在generations，也在314行跳过。stop_controller随后把 `owned_descendants_exited=True` 写入结果。异常闭锁链不会触发，因为这里没有抛错。
   - 最小修复：在每个remaining行入口，先独立拒绝 `created is None` 且 `pid in generations` 或整数 `parent in generations`，再执行已批准的窄foreign orphan排除；保持完整Job查询、双时点稳定、signals和全部原门不变。新增parent存在的actor/descendant负例，不能只保留parent999缺失的原bound_pid用例。
   - 若不修：报告可给出未完成身份核查的后代关闭成功，随后进入producer ACK/observer终态链。新快照在OpenProcess/GetTimes/Image失败时确实允许这种nullable行；本轮在显式fake-kernel边界亲复此结果，**未宣称实际原生发生该race、PID复用或Source误关闭**。held旧actor ACK只证明其绑定对象退出，不能把remaining未知行认作foreign。

2. **[P2] 两条未知birth解析没有使用批准的OwnershipError**（`windows_actor.py:230/256`；launcher未知解析同类在209行）。
   - 职责：未知创建时间必须按身份未知拒绝；05:54:41明确要求bound actor/known descendant未知birth一律OwnershipError。
   - 问题：bind_descendant及首次kill快照的actor `created=None` 进入 `_snapshot_ticks(str(None))`，实际抛ValueError。新38的既有fixture还预期ValueError/TypeError；不能据此宣称符合批准的异常合同。现真实调用者统一Exception捕获，使这两条路径仍闭锁；这一事实不修复条款差异，也不保护发现1的成功返回路径。
   - 最小修复：在绑定身份解析入口显式检查nullable birth并抛OwnershipError，保留PID/birth/Job/ancestry其他判断。Root已明确要求作者小修统一类型，不能口头改CR迁就实现；新pin/raw清单及必要freeze相应重新固定。
   - 若不修：身份未知被归入格式解析错误，批准合同与实现/测试互相矛盾。本轮两条严格异常负例都亲复失败；未对旧oracle放宽期望。

4个自有新用例实跑 **0 passed / 4 failed / 0 error/skip**：前两条为ValueError而非OwnershipError；后两条为 `DID NOT RAISE OwnershipError`。触发代码在 `test_review_unknown_bound_birth.py`，失败原文/JUnit分别在 `unknown_bound_contract.stdout.log/.xml`。fixture显式只模拟 held birth/exit 与快照边界；不是live测试，不替代Root内核审计。

## 3. 原freeze兼容及亲跑结果

所有实际长命令均由本run的成熟 `run_owned.py` 执行；base为 `C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe`，工具shell为实际存在的 bundled pwsh、login=false。执行器加入自有KILL_ON_CLOSE Job并查询：active10、512MiB/process、1GiB/Job、24CPU×rate833（1.9992核上界）。离线内部deadline50秒，native内部15秒；完整Windows控制 ancestry纳入计数。以下+08时间、外层wall/exit都来自本轮raw `*.command.json`，完整argv/cwd与stdout/stderr SHA也在其中。

| label / 实际目标 | +08真实起止 / wall | 退出码与数量 | 完整Windows峰 |
|---|---|---|---|
| offline_new38 / 作者三新文件 |06:12:15.401760–20.453272 /5.062s|exit0，38pass|7/10|
| offline_original74 / 原七oracle文件 |06:12:25.383881–33.847229 /8.469s|exit1，71pass/3原bytes red|7/10|
| offline_prior60 / 原bootstrap/startup/audit/freeze四文件 |06:12:38.155545–55.234031 /17.079s|exit1，59pass/1原bytes red|7/10|
| unknown_bound_contract / 自有4严格合同用例 |06:17:14.911926–16.286580 /1.375s|exit1，4failed|5/10|
| fixed_verification / 23+217raw及pending |06:15:50.195939–50.404683 /0.218s|exit0，全部匹配|5/10|
| fixed_verification_after / native后同边界 |06:18:26.328042–26.535028 /0.203s|exit0，全部匹配|5/10|

实际pytest命令均为 `BASE -B OWN/run_owned.py LABEL -m pytest <下列文件> -q -o addopts= --junitxml=OWN/LABEL.xml`，OWN即本工作树的 `reports/runs/r06_native_snapshot_review1_20261017`；原封完整命令不经shell模板执行，见同名command收据：

- new38：`reports/runs/r06_native_process_snapshot_20261017/test_native_snapshot_offline.py`、`test_stop_names_offline.py`、`test_native_candidate_freeze.py`。
- original74：`reports/runs/recovery_r06_activation_prep_20261016/test_activation_preparation.py`，以及`reports/runs/recovery_r06_activation_database_fix5_20261017/`下`test_candidate_binding.py`、`test_database_marker.py`、`test_lifecycle_fix2.py`、`test_native_boundaries.py`、`test_product_binding.py`、`test_database_binding.py`。
- prior60：`reports/runs/recovery_r06_bootstrap_recovery_fix1_20261017/`下`test_bootstrap_recovery.py`、`test_startup_diagnostics.py`、`test_audit_proof.py`、`test_candidate_freeze.py`。
- unknown_bound_contract：本run的 `test_review_unknown_bound_birth.py`。

本轮176个不同pytest case为 **168passed/8failed/0errors/skips**（74+60+38+4；手工native另计）。没有coverage工具或百分比，coverage为定向行为覆盖：38覆盖未知保留、权限/Image/birth race、枚举/close/deadline、完整Job名单/重复/截断/变化、unknownowned/bound orphan、停止names与原freeze；新4补出parent仍在时漏判及严格异常类型。新38通过不覆盖新4红。

原74三红分别是 `test_core_only_approved_constants_change_and_ten_original_guards_are_exact`、`test_ops_controller_observers_and_authorization_guards_remain_original`、`test_control_logic_is_exact_fix3_outside_approved_product_and_core_pins`。原60唯一红是 `test_fixed_twenty_three_sources_are_exact_git_blobs_and_only_two_controls_differ`。旧oracle只允许更早的常量或两处生命周期字节，因此无法接受此CR明示的四改十六不变；新增精确raw/Git/ASTfreeze补充而不洗掉旧红。原正常判断、阈值和旧断言均未动。

作者最终原74的 **70pass/4fail（3bytes+ACKTrue）** 与其随后孤立2ACK通过全部保留；本轮完整74的ACKTrue/False均通过，因此本轮为71/3，**不把作者整组4红改写成通过**。原ACK fixture MAXIMUM .08、SHUTDOWN .12、producer sleep .13不改；一次完整重跑不能证明时序稳定或归因。旧60作者59/1，本轮也59/1。

## 4. 真实原生7例与三代关闭

Root明确批准两个各自独立≤20秒native窗，先7再多代，每窗交回资源；资源红后又仅批准自有dummy `DETACHED_PROCESS0x8`、原cap10和birth/Job/held门不变的一次独立≤20秒重试。授权原文记录在本run的review控制记录。未运行actual停止入口授权链、Source或安装。

精确stdio限制：原7作者probe和本轮三dummy一直为stdout/stderr DEVNULL。重试仅改dummy flags，保留其真实Popen/held身份；Root第二次ACK含“保持PIPE”，本仪器没有新建PIPE。因此本轮**PIPE场景not_run**，未宣称证明带PIPE的Source进程关闭；该措辞与实际stdio差异已主动交Root，不混写为PIPE通过。

| 实际命令 `BASE -B OWN/run_owned.py LABEL OWN/SCRIPT.py` | +08起止 / outer wall | 结果 |
|---|---|---|
| native_original7 / native_probe |06:14:27.925013–29.902404 /1.969s|outerexit0，原7手工case全pass，峰7/10|
| native_multigeneration / 初自有native_multigeneration |06:14:37.012865–38.157515 /1.140s|outerexit1，峰11>10，立即终止probe；业务kill尚not_run|
| native_multigeneration_detached / 自有native_multigeneration |06:16:28.099505–29.265583 /1.172s|outerexit0，真实三代kill+3heldACK pass，峰8/10|

原7为wrongbirth、foreignJob、wrong ancestry拒绝且dummy仍alive；正确parent；同快照names+只读livebirth；owned tree真实exit70/heldACK；真实exit23/heldACK、快照缺席及停止拒绝。inner1.657秒，逐case起止/PID/birth见 `native_incremental_fix1.json`。这只是harmless控制边界，不计来源live。

多代成功inner0.984秒，probe47320的直接root **32848**（birth134366625882360591），child **23492**（parent32848，birth134366625882995839），grandchild **56956**（parent23492，birth134366625885794152）。三个对象先held birth与完整快照的birth/parent匹配、同一ownedJob，再调用固定c8的kill_owned_tree；三者均真实exit70、held Wait ACKtrue、held birth未变，post快照三PID缺席，innerJob终态active1仅执行器。没有给非自有PID发信号。结果在 `native_multigeneration_detached.json`，raw脚本仍使用真实Popen且父子均绑定，未借pythonw或放宽数量。

## 5. 资源红与限定缺测

初多代的CREATE_NO_WINDOW给每dummy创建conhost，完整收据为shell+conhost+outer+probe+conhost五进程，再三dummy及各conhost六进程，共峰11；仪器按cap10立即闭锁。原脚本保存在 `native_multigeneration_first.py`，原stdout/stderr为空、真实exit1与失败码 `full_windows_process_cap_exceeded` 留存。业务关闭当时未执行，不计业务通过。Root批准后只改自有三dummy创建flags并另存新收据，控制源码未改、cap/CPU/内存/超时未改。这一仪器红不归为c8业务缺陷，也不从记录删除。

所有本轮命令的held外层子ACKtrue、remaining_owned0、sampling errors0、结束usage active1；Linux自有启动0。各命令内存峰均≤168206336字节，CPU/限额原始值在收据；CPU均值不作为瞬时限流证明。初峰11是明确资源门failed，其余峰≤8。每个native窗结束均向Root报告资源释放，没有跨窗后台循环或扩大扫描器。

fresh CBM scope仅复制当前20份公开CORE/OPS原字节，已先rg调用者；私有binding、holdout、秘密不进入scope。source-only scope及独立cache计划记为 **prepared_not_indexed / partial**。本c8已出现可复现Must fix，没有启动新CBM索引窗或造新图；旧303nodes/1420edges不算新native图。可在新修复pin后由Root另排≤60秒、Windows+guest完整合16窗，使用成熟fullguest工具；本轮新graph/schema/trace与resource coverage均not_run。

本轮未运行完整类型、ruff/format、产品pytest/PG integration/frontend/e2e、安全全门或coverage；作者原stop_owned五项ruff红不予继承为绿。已执行candidate tracked `git diff --check` exit0且diff空，新增Python AST/自有diff检查另见review终态记录。探索性rg误传PowerShell字面wildcard和一次收据汇总foreach管道ParserError均属静态仪器定位/读命令错误，已纠正；没有在该错误命令中执行业务测试或文件修改，不计业务红。

## 6. 调用链、评分与下一步

真实callers已读取：configuration950在归档前消费完整PID/parent快照，拒绝旧PID和直接后代；guardian76注册source，失败走Job终止和held launcher ACK；controlled_supervise342注册worker/beat，stop_controller85/90执行tree关闭，554捕获拒绝、581终止自有Job；stop_owned143取共享tree，158复用values做names，原positive identity/livebirth判断和发布stop.request顺序保持。observer需要两producer的ACK、actual exit和descendant成功字段，不能由静态finally替代真实关闭。发现1正因无异常而能到101的成功字段，所以现Exception闭锁不能兜住它。

完整Job名单的assigned/listed、buffer/returned bytes、重复/非法PID与查询失败闭锁已核，和[Microsoft Job PID list](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list)区分完整/截断的字段语义一致。双相同PID set只证明两查询时点的membership，不能声称原子排除ABA或永久foreign；同步Win32调用不能被Pythondeadline中断，三秒检查只拒绝晚结果。原生构造字段与[PROCESSENTRY32W](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/ns-tlhelp32-processentry32w)吻合；自有DETACHED创建方式依据[Microsoft creation flags](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags)，实测同Job，没有BREAKAWAY。

评分只给E1控制身份/关闭的限定真实工程证据；不计F1/P1来源覆盖、首轮采集或六小时运行。Root17实际closure audit、实际安装、fresh七门、Source/PG/MinIO/worker readiness、新Source启动、首轮采集、6h同版本持续观测和最终资源审计仍需新的真实证据，本报告没有署为通过。

**Verdict：先修复1和2，当前候选needs_changes。** 下一任务建议：作者在Root精确记录范围内做最小bound未知入口修复与OwnershipError统一，提交新CORE/OPS/raw/pending清单，原红保留；本reviewer仅定向复核新源码差异与本4负例及受影响回归，之后才进入Root新审计/安装/七门。R06/G-C保持partial，整卡和阶段均不accepted/push。
