"""Write the independent initial opinion with actual local timestamps."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from run_commands import OUTPUT

started = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
report = r'''# G-A · R00 独立初审 1

首次创建、本次写作开始/结束、最后更新、证据截止：TIMESTAMP（Asia/Shanghai，+08:00）。
运行计时起点：2026-10-14T21:27:35+08:00；此前只读阅读没有另行计时，不虚构开始时刻。
任务：R00/G-A 独立初审；审查状态：**needs_changes**。审查工作已完成；R00准确落实暂不能生效。
审查者：`/root/r00_independent_review`，未参与本批实现，未修改业务源码/合同/状态/锁文件，未提交或push，也未签任何原T卡accepted。

## 这个变更做什么

R00将用户已经批准的九项建设决策写为正式CR，保留原60任务最终合同，新增110能力切片和26恢复执行节点；同时保留旧原字节、纠正历史accepted，并增加严格JSON与公共v2合同检查。它解决的是计划、状态与接口约束，不是R01–R03运行底座，更不证明整个G-A通过。

本次固定审查候选 **d752fe0c8f14dd4c35b39863cfba0d1c902fffae**，tree **e9be906a97f1c00cedaac36aab76499a1b60354a**；父基线 **b8199ce5dd0a7920ce5770e4f580fe23e0fe9f6b**。审查目录为 `C:\Users\yinha\.codex\worktrees\recovery-r00-review\dianzi`；开始及21:35:53再次核对HEAD均精确匹配，`git status --short`为空。`D:\dianzi`仅作证据落盘、必要字节比较和调用已有uv运行环境；没有依据正在变化的集成checkout签通过。

## 必须修复

1. **RV-01 / P1：干净Windows工作树无法通过本批冻结基线**（候选 `.gitattributes:1`、`contracts/baselines/plan_baseline_recovery_r00.json` 的source_hashes、`scripts/verify_plan.py:768`）。

   - 触发与实际结果：在本独立managed worktree，`core.autocrlf=true`，运行 `python scripts/verify_plan.py --baseline contracts/baselines/plan_baseline_recovery_r00.json` 退出1，报 `BASELINE_SOURCE_HASH_CHANGED`，唯一失败路径为 `fixtures/synthetic/pilot_cases.json`。
   - 根因与影响：冻结值及Git blob/集成原字节SHA-256是 `8686ba8db7793e5ac59cab339e61ea8b0bfd4e85ecd65e9f657c2d4ade0b990d`；正常checkout后的CRLF字节值为 `1907ff5308b9d6fbf143e173e2ac7df50f1dcf5622a23c3d9fab4a39c5120228`，仅LF归一化就恢复冻结值。新增gitattributes保护了历史、NVD和日志，却遗漏被按原字节冻结的fixture；因此同一正确提交在陌生环境被当作合同篡改。不能通过重新写baseline掩盖它。
   - 最小修复：精确保护当前按字节冻结的三份source_hash输入，兼顾requirements/manifest的原始换行与fixture；保留旧baseline、案例值、分母与阈值。不要全局关闭换行或校验。
   - 复验：在新的冻结修复SHA干净checkout中，分别检查Windows autocrlf与Linux/WSL取出的三个原字节哈希，指定baseline命令须0，再跑原49项相关回归。当前证据在 `plan_baseline.json/stdout.log` 与 `independent_probes.json`，原失败日志不覆盖。

2. **RV-02 / P1：accepted恢复节点没有核对实际能力切片前置**（候选 `scripts/verify_plan.py:712`–`730`；`contracts/task_manifest.json:1134`）。

   - 触发与实际结果：独立临时副本把authority与R00/R01/R02登记为accepted、complete，提供存在的项目内evidence/review路径，八层状态均passed，但保留全部110个原T `slice_acceptance` 为pending。CLI实际退出0并打印PLAN_OK；其中R02声明需要的 `R01:T02`、`R01:T03`、`R01:T06`、`R00:T04`均未独立验收。
   - 根因与影响：该循环只检查依赖R包状态和authority，没有读取 `requires_slices` 的实际 `tasks[original_task].slice_acceptance[slice_id]`。存在性/所有权在manifest检查中已验证，但不存在“能力已满足”的状态检查。这样可以用R卡绿色绕过尚缺的前置能力，与用户要求“缺失的前置能力仍然阻断相应工作”相冲突；未来主控误登记时校验器不能发现它。
   - 最小修复：在accepted恢复节点校验里核对每个requires_slices的独立accepted、证据和review；同时避免accepted节点与其output_slices尚pending的矛盾。只核对能力切片，不新增整张原T必须先accepted的要求，不反锁早期实现。
   - 复验：重跑 `accepted_r02_missing_slices` 应非零并给切片编号；增加“整T仍pending、所需切片已独立accepted”的正例，保持T06 R01部分误签整卡仍失败。证据为 `accepted_r02_missing_slices.json/stdout.log`、临时副本及 `review_probes.py`。

没有另外制造风格循环或未经复现的阻断项。两项均为合同/验收行为问题，不是当前Docker或模型尚未接通造成的环境失败。

## 九项授权与迁移记录核对

逐份读取CR-R01–CR-R09及用户提示词、恢复11/12、00–06；九单都有原条款、新合同、影响、兼容、迁移/验证、回滚和独立生效记录。记录未把已授权建设目标当作产品实测，仍为awaiting_review。

| 决策 | 本次核对结论与限制 |
|---|---|
| CR-R01 | 九职责与确定性节点、旧graph按版本恢复、四角色B2/九角色B2b/动态B3对照保留；记录准确，实际Agent与跨进程恢复留R14/R21 |
| CR-R02 | PG唯一事实/任务/ACL权威，pgvector唯一语义向量、OpenSearch BM25、Neo4j可重建投影、MinIO、单Celery队列和脱敏追踪；增量迁移/备份/前向修复说明合理，不虚构版本或已迁移 |
| CR-R03 | 八类与九通道分开、单源不重复计数、原始时间/漏采/无时间均保留；不改官方评分分母；逐源live留后卡 |
| CR-R04 | 稳定ID与内部ACL/版本证据、异步联合、四态、200同步与10MiB/10000独立上传、RFC9457与兼容路由；静态正负合同通过，实际适配器/协议接线留R18 |
| CR-R05 | 来源断言/冲突/撤回分别保留，不按等级压平或盲目并集；新增版本更正与索引重建回滚合理；PG发布/乱序实测留R02/R07/R16 |
| CR-R06 | Hunter/Quake公网聚合与FOFA授权资产双链同时保留；明细网关即丢弃、失败不变0、观察时间独立；实际字段/权限/live仍待接通 |
| CR-R07 | R24-A→R23→R24-B、原卡最终前置和六验收、同阶段切片推进、每批/阶段新独立review及授权分支push；文档准确，但RV-01/RV-02使机器可核验部分尚不完整 |
| CR-R08 | 原评测规模/门槛/分母不缩减，双人标签/裁决、holdout隔离、关键事实逐条校验和显式demo保留；原20合成案例仍是fixture，未算人工金标 |
| CR-R09 | 浏览器cookie与API Key共享认证、hash/轮换/撤销、两种MCP transport、六只读工具+本人订阅、受限容器插件；OAuth按选定客户端要求验证，公开部署/发包另授权，边界准确 |

九决策的文本落实可以认可。正式**整体生效仍须先修RV-01/RV-02并冻结复核**，本报告不提前把authority或CR登记为accepted。

## 原任务、切片与八层纠偏

独立比较父基线与候选：原manifest的 `tasks/stages/execution_order`内容完全相同；全部60原卡原正文完整保留，仅追加恢复合并说明，60卡均保留C01–C06和原最终前置。110切片唯一归属60T，26执行节点覆盖13要求/U01–U14；逐卡映射与比较明细在 `independent_probes.json`。保留原正文也保留了原实施步骤，不把切片数量当实现完成度。

关键合并语义成立：T06需R01/R02/R20，T40需R01/R04/R17；T20需R05/R07，T30/T31需R05/R12；T35需R12/R14/R18；T39需R15/R16；T51需R18/R20且原T48前置仍保留。T55/T56的完整候选原卡检查归R24-A，T57/R23据候选材料复现；T59需A+B，B消费R23意见并复核实质材料变更，避免循环。R24-A仅就绪时整R24仍partial/in_progress，不能签整R24。

R19工具/候选统一在R04真实闭环独立通过后可提前准备，final_gate仍要求R07–R16完整覆盖+双人复核/裁决/hash冻结；R05模型阻塞不能把G-B签通过，亦不阻碍安全独立的来源/候选准备。R20基础从R01、R22观测从首真实链分版本、R24仅早建骨架，规则一致。

当前原T状态为24项needs_changes、36项pending、**0 accepted**；60条均完整登记八层，110切片当前均pending。T09/T10 contract=failed、T06/T40 security=failed、真实PG相关integration=blocked或not_run；T16/T21内存测试只记unit，不计PG集成。旧accepted和重复note均保留历史。存在的旧文件不证明其内容真实或review独立，结构脚本不能替代独立复跑。

旧状态归档与 `8e265dc:progress/task_state.json` **逐字节相同**，SHA-256 `fcd665b8ab8039fda5920494eb24be1beadaddd445e30d471552e4efe738b780`；它在集成目录、审查worktree及Git blob均相同。NVD原响应三处均为 `1bc5449375788cf417662cf3187bcd11c1484ed0b15026d4cf71760edd352c1f`。新旧baseline的schema_version、purpose、thresholds、六invariants、frozen_case_ids全部相同；没有修改金标、失败分母或困难题ID。fixture仅checkout换行漂移，恰为RV-01。

| R00切片/检查 | 独立意见 |
|---|---|
| R00:T00 | 现状/资源/授权台账与重开原则可认可为文档切片；真实账号权限/产品live未认证，不签整T00 |
| R00:T01 | 分值/要求/全部映射/历史保留可认可；冻结可复跑与能力前置状态检查受RV-01/RV-02阻断，切片尚不可整体accepted；R19余片仍未实现 |
| R00:T04 | 本卡公共v2静态合同与规定正负边界可认可；R02领域持久化、R18适配/客户端等余片未实现，不签整T04 |
| R00六项验收 | C01分值、C02要求/U、C03覆盖、C04公共合同、C06授权类别具备计划证据；C05/指定冻结复跑须先修两项缺陷 |

这些局部意见不修改state，也不批准剩余107切片、任何整T卡或整个G-A。

## 实际复跑与调用链证据

完整argv、真实cwd、开始/结束到秒、退出码与stdout/stderr保存在同run目录的逐命令JSON；不是复制作者的通过记录。计划/负例cwd均为独立冻结worktree。Ruff/format/mypy从 `D:\dianzi\backend` 的已有uv环境调用，目标是冻结worktree绝对路径，使用 `uv run --locked --offline --no-sync`；未运行安装或改变锁文件。两环境pyproject/uv.lock的Git内容一致，工作树换行差异单独记录。

| 命令/检查 | 退出码与真实结果 |
|---|---|
| `python -m unittest discover -s tests/plan -v` | 0，49 tests，49通过/0失败/0skip（40计划+9公共合同，不重复相加为unit与contract各49） |
| `python scripts/verify_plan.py --baseline contracts/baselines/plan_baseline_recovery_r00.json` | **1**，1项fixture字节哈希漂移，见RV-01 |
| `git diff --check b8199ce… d752fe0…` | 0，diff检查通过 |
| `uv run --locked --offline --no-sync ruff check <冻结verify_plan.py> <冻结tests/plan>` | 0，实际4文件通过 |
| 同环境 `ruff format --check` | 0，4 files already formatted |
| 同环境 `mypy --follow-imports=skip <冻结verify_plan.py>` | 0，1源文件无诊断 |
| 五个独立CLI负例 | 深层数组对象重复键=2；R01部分误签T06=1；passed无证据=1；R24逆序=1，均正确拒绝。accepted R02缺能力切片=**0**，错误通过，见RV-02 |
| 五个独立schema观察 | no_match+clean=false；no_match+确定排除=false；no_match+insufficient_evidence=true；source_fact空support_ids=false。仅填未知UUID且无citations仍格式有效，说明schema不证明引用支持/ACL，须R18运行时核验；未将该观察算产品通过 |
| 冻结API/记录输入探针 | 脚本执行0，但实际业务仍有失败：默认只两个health路由、auth/me404、ready503；PDF unparseable；NVD原形报wrapper错、人工包裹仍丢9.6评分；callback持久化失败后游标仍advanced；真实三模型接口不存在；前端仍未接后端 |

jsonschema在本机system Python可用，49项实际加载并执行；未安装依赖。产品探针用已有 `D:\dianzi\backend\.venv\Scripts\python.exe`，显式sys.path指向冻结源，无DB/外部请求，读取的NVD是公开留档响应，**不是本次live**。这些既有产品缺陷留R01–R05修复，不当作本卡实施不存在，也不当作环境修复后自然通过。

实际使用官方portable `codebase-memory-mcp 0.11.0`，CLI/help已读取。新cache `/tmp/dianzi-cbm-r00-review1-20261014`；两个独立name为 `dianzi-r00-review1-scripts-d752fe0` 和 `dianzi-r00-review1-backend-d752fe0`，仅索引该worktree的scripts与backend/src，不含秘密、holdout、附件。脚本图82节点/248边，生产源图516节点/1920边，均无未索引/部分解析；文件hash及SHA/tree绑定在 `integrity_snapshot.json`。

`trace_path`证实 `load_json ← run_all_checks ← main ← CLI入口`，另取architecture和graph schema；源码/rg核对requirements/manifest/pilot_cases/state/可选baseline共用严格loader，`run_all_checks`实际调用两恢复检查。生产源图的create_application含条件式auth注册；源码的默认app不注入auth，TestClient复跑404/503交叉核实。图有边不当作已装配，有图亦不当作业务通过。

## 未检查、评分证据与下一步

本轮unit/contract复跑passed；产品integration/security/frontend/e2e/live/manual均**not_run**，没有运行会清库/降级/重启常规数据库的旧DB测试。权限、事务、并发、PG/Celery真实链、模型/测绘live、客户端互通、正式holdout评测、人工标签、连续运行与材料渲染都未在本卡验收；其未实现/资源阻塞不能被49项计划测试补足。没有读取密钥值或秘密库、没有访问holdout答案、没有付费调用、没有向其他用户聊天/邮件发送消息。

本意见为E1/D1/X1提供可追溯计划/状态完整性和缺陷证据；F1/F2/F3/P1/P2/P3/A1/R1/R2仅确认建设与验收映射，没有新的正式分数、准确率、时延或稳定运行结果。

**结论：先修RV-01、RV-02。d752fe0的R00准确落实暂不能整体生效；G-A未审通过。** 修复后主控冻结新SHA，由本非作者reviewer定向复跑上述复现、完整计划测试、基线与切片合法正例，再登记R00决定。R00生效后可继续R01/R02/R03，G-A仍须另一个未参与实施的阶段reviewer验证真实运行链。本初审不随集成checkout变化自动变为通过。
'''
report = report.replace("TIMESTAMP", started)
path = Path(r"D:\dianzi\reports\reviews\recovery\G-A-R00-review-1.md")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(report, encoding="utf-8")
records = []
for record_path in OUTPUT.glob("*.json"):
    value = json.loads(record_path.read_text(encoding="utf-8"))
    if isinstance(value, dict) and "argv" in value:
        records.append(value)
(OUTPUT / "commands.json").write_text(json.dumps(sorted(records, key=lambda value: value["started_at"]), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"report": str(path), "created_at": started, "finished_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"), "command_records": len(records)}))
