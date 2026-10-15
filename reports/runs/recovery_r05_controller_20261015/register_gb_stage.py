"""Register the independently reviewed G-B slice without changing original T acceptance."""

import copy
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
SHA = "1927eeb00a7e0c1335f76340b0382f46102f08f2"
REVIEW = "reports/reviews/recovery/G-B-checkpoint-review-1.md"
RUN = "reports/runs/recovery_gb_checkpoint_review_1_20261015"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, value: str) -> None:
    (ROOT / path).write_text(value, encoding="utf-8", newline="\n")


report = read(REVIEW)
assert SHA in report and "最终阶段意见：Ship" in report
state_path = "progress/task_state.json"
state = json.loads(read(state_path))
original_tasks = copy.deepcopy(state["tasks"])
scope = (
    "仅G-B R04/R05批准切片，依据未参与实现的新阶段reviewer固定1927 Ship；"
    "1419纯组合/73.71%原60门、56计划、真实PG权限与事务、254前端/17隔离浏览器通过。"
    "live仅历史已测版本两固定真实源与dc014真实引用回答，由reviewer只读核验PG434span/MinIO114对象；"
    "1927新增来源HTTP行为由真实PG证明，未重新付费live。完整问答10212.6966ms不达5秒；"
    "manual=not_run。原T合并验收、R12/R17完整范围、正式评测与容器验收不提升。"
)
for task_id in ("R04", "R05"):
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({
        "recorded_at": NOW,
        "event": "Register independent G-B Ship for approved recovery slice only",
        "prior_status": task["status"],
        "prior_implementation": task["implementation"],
        "prior_verification": copy.deepcopy(task["verification"]),
        "prior_verification_scope_notes": copy.deepcopy(task.get("verification_scope_notes")),
        "review_ref": REVIEW,
        "reviewed_code_sha": SHA,
    })
    task["status"] = "accepted"
    task["implementation"] = "complete"
    task["verification"] = {key: "not_run" if key == "manual" else "passed" for key in task["verification"]}
    task["review_ref"] = REVIEW
    for evidence in (REVIEW, f"{RUN}/final_metadata.json", "reports/stages/recovery/G-B.md"):
        if evidence not in task["evidence"]:
            task["evidence"].append(evidence)
    task["verification_scope_notes"] = {"recorded_at": NOW, "current": scope, "reviewed_code_sha": SHA}
r06 = state["recovery_tasks"]["R06"]
r06.setdefault("history", []).append({"recorded_at": NOW, "prior_status": r06["status"], "prior_implementation": r06["implementation"], "event": "Register existing independently prepared source slices and unintegrated root persistence draft; no acceptance"})
r06["status"] = "in_progress"
r06["implementation"] = "partial"
r06["verification_scope_notes"] = {"recorded_at": NOW, "current": "来源准备已独立限定Ship；两parser/社区适配器初审Must修复后待原reviewer复核。root D:/wt/r06-integration草稿真实PG8、unit1019通过，未冻结未审未装配；不能计R06/live通过。"}
state["recovery_stage"] = "G-C"
state["updated_at"] = NOW
state["updated_by_task"] = "R04/R05 independent checkpoint registration; R06 continued implementation"
assert state["tasks"] == original_tasks
write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")

stage_path = "reports/stages/recovery/G-B.md"
stage = read(stage_path)
replacements = {
    "本次写作开始时间：": NOW,
    "本次写作结束时间：": NOW + "（本次独立意见登记）",
    "最后更新时间：": NOW,
    "本报告证据截止时间：": "2026-10-15T19:01:00+08:00（独立报告封存）；本次状态登记见写作时间",
    "阶段实际开始/结束时间：": "历史未单独记录开始；首个来源GET观测2026-10-15T11:53:40+08:00不是阶段起点 / 2026-10-15T19:01:00+08:00独立阶段门封存，不是连续服务时长",
    "独立审查Agent与报告：": "/root/g_b_checkpoint_review；" + REVIEW + "；固定1927最终Ship，三Must关闭；登记文档待同reviewer差异核对",
    "阶段状态：": "accepted（仅批准的R04/R05阶段切片，依据新非作者限定Ship；登记文档复核中）",
    "各层验证状态：": "unit/contract/integration/security/frontend/e2e passed仅本文与独立报告限定范围；live passed仅已测分段真实来源/模型/页面及独立溯源，非1927整版本新增外部复跑；manual not_run。正式指标未验收",
    "已测代码SHA：": SHA + "独立干净环境综合/PG/前端；dc014c960f19605c20e0d8e98a93e7c217f94cc6真实模型/API/页面；各早前分段不可拼同版本时长",
    "已审代码SHA：": SHA + "；独立报告最终Ship，文档登记提交SHA待冻结后复核",
}
lines = stage.splitlines()
for index, line in enumerate(lines):
    for prefix, value in replacements.items():
        if line.startswith(prefix):
            lines[index] = prefix + value
            break
stage = "\n".join(lines) + "\n"
stage += f"""
## 独立阶段意见登记 · {NOW}

本次写作起止均为上列真实脚本执行时点；首次创建时间保持。新非作者/root/g_b_checkpoint_review在第三个全新WT D:/wt/gb-stage-final固定{SHA}复跑并于2026-10-15T19:01:00+08:00封存限定Ship，主控据此登记accepted，仅R04/R05本阶段切片。旧段落与红日志是按时间保留的历史，当前结论以本节及顶部为准。未修改原T任务状态、金标、阈值、分母或盲测；后段原T合并验收仍全部存在。

### 范围、独立验证和版本

两固定源→受控网关→MinIO/PG不可变原文/永久证据→PG任务/游标/outbox→认证列表/详情→浏览器；单事件当前公开证据→真实E5/pgvector/重排→两轮生成/核验→认证/epoch/owner CAS→PG答案与固定引文。新来源HTTP键与认证锁仅1927真实PG复验，不把dc014旧live冒称1927外部复跑。

最终1419纯unit/contract/security组合0fail/skip（10真实PG另测），5196/7049行=73.71258%，原60%门不变；56原计划检查；真实PG套件49、25、41、35、8、1以及来源原3负例、正式11和7合法撤权/锁顺序探针均exit0；套件重叠不可相加。前端254、type/lint/build及17浏览器fixture通过。全部cwd/命令/秒级起止/退出码/数据版本见独立报告第3/8节与{RUN}/command_summary.json、final_metadata.json。初次浏览器缺缓存17失败是环境仪器错误，修正外部cache后同例17通过，原失败未删。真实模型未由reviewer重新付费，而是亲读核对434证据span/114对象/保存答案trace与原始浏览器结果，费用累计8次调用unknown。

### 问题台账增补与关闭

| 问题 | 输入、根因与影响 | 修复/复验与状态 |
|---|---|---|
| GB-HTTP-KEY | 两固定源POST缺key仍202；跨管理员同key折叠，跨来源碰撞；裸key幂等域缺主体/来源 | 1927认证后必需ASCII键、canonical actor/source域、事务认证锁。作者原8fail/3pass→11pass；独立原3负例与11正式、7撤权/PG锁探针通过。19:01:00+08:00审查封存关闭 |
| GB-FORMAT | fresh frozen无date-time可选实现，原无时区负例被接受，计划55pass/1fail | 1927官方jsonschema[format-nongpl] dev extra/锁；独立新环境原56pass。封存关闭，无改样本 |
| GB-BYTES | clean checkout autocrlf改变精确夹具hash/span，1418pass/1fail | 8c及1927精确路径保留原bytes；51分类及51source-origin独立通过，原manifest/regex/ignore未改；最终1419pass。封存关闭 |
| GB-RFC850 | 完整未来50年边界误只看年份，例2076误blocked，1红保留 | 非阻断保守可用性债务，未提前重试，R06来源可用性继续修；未解决，负责人/root |
| GC-CPU-LIMIT | 原R05 busy child 1 CPU秒，受并行负载时偶发8墙钟秒timeout，同参数可过 | 原红原样保留；新独立native_cpu_limit_diagnosis在1927诊断，尚未证明根因；不抬timeout/skip，不计G-B固定复跑失败 |

### 当前效果、剩余与下一步

暗色青绿/低亮动态拓扑背景、390宽度与reduced-motion已有真实截图；不是完整R17。真实修复版单问完整10212.6966ms，非≤5秒、非P50/P95、无金标准确率。R12多轮多跳、R06广来源、九维、图谱、资产、推荐/重判、Agent/MCP/插件与正式评测仍后段，未签。双人金标/裁决与授权资产范围仍缺，PPT用户后置。semantic extra/容量/受控出网的容器部署待R20；Windows成功不能代替Linux容器。

阶段无新增重大决策；三实现补充CR及兼容/前向迁移/停止入口回滚记录由新阶段reviewer与源码核对。历史raw-key job保留按job_id读，无法猜actor迁移；旧无lease pending人工恢复，不能自动重付费。源代码未因登记变化；本次只登记文档/状态/报告归档。G-B实际push尚未发生，正常push并核对远端后收据追加reports/push/recovery_push_log.jsonl随下一阶段提交。

G-C继续：两来源实现包修复后原reviewer定向复核；root独占共享catalog/document元数据版本迁移与装配，文档持久化草稿8真实PG/1019unit通过但未审且未接产品入口。不同版本/中断不拼稳定时长。MinIO段3实际18:57:02结束、段4 18:57:49开始，47秒中断，截止20:57:49；全部产品API/worker/beat当前已到期停，无持续采集声称。文档修订记录：{NOW} /root依据新独立报告登记阶段意见并保留全部历史。
"""
write(stage_path, stage)

for task_id in ("R04", "R05"):
    path = f"reports/tasks/{task_id}.md"
    write(path, read(path) + f"\n## 独立阶段登记 · {NOW}\n\n状态accepted、实现complete仅本卡G-B批准切片；依据{REVIEW}固定{SHA}最终Ship。{scope}\n\n各层范围/命令/计数/起止/失败保留与兼容迁移详见reports/stages/recovery/G-B.md和该独立报告。复用和必要新增仍按原报告，无新平行框架。旧状态段落为历史；未改变原T整卡验收。阶段push写作时尚未发生，实际台账另记。\n")

for path in ("docs/decisions/CR-R04-R04_source_commit.md", "docs/decisions/CR-R04-R05_question_commit.md", "docs/decisions/CR-R04_schema_format_checks.md"):
    content = read(path)
    write(path, content + f"\n## 独立核对登记 · {NOW}\n\n当前状态accepted，仅本记录对既有授权的实现落实；前述awaiting_review为保留历史。新非作者/root/g_b_checkpoint_review固定{SHA}已核对合同/兼容/迁移/回滚并独立复跑，见{REVIEW}最终Ship；未新增重大决策、未削减评分/原任务。登记文档待同reviewer核对差异，业务代码未改。\n")

snapshot = f"""## 当前权威快照 · {NOW}

集成codex/full-delivery-recovery，已测/已审代码{SHA}；G-A accepted已push，远端最后核对fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4；G-B依据新/root/g_b_checkpoint_review 19:01:00+08最终限定Ship登记accepted，仅R04/R05切片，文档差异待同reviewer复核，G-B尚未push。当前G-C，原T整卡状态/全部映射验收不变。最后独立1419/73.71%原60门、56计划、254前端/17浏览器及各真实PG套件通过；真实问答dc014完整10212.6966ms不达5秒，累计供应商8次fee unknown，无金标/正式评测。

并行4槽：root独占公共schema/迁移/锁/状态/集成/Git，D:/wt/r06-integration@1ff独立草稿catalog/persistence0015（8PG/1019unit，未审未接线，尚未合1927）；r06_feed_parsers D:/wt/r06-feeds修3初审Must冻结6b7dd7e881bb822e83b55f8302f7aefe565f4940、1170pass，补证据后结束待原reviewer；r06_repository_community_adapters D:/wt/r06-repos修OSV7显式null，1250pass待冻结及原reviewer；新native_cpu_limit_diagnosis只读诊断原WindowsCPU子进程偶发8s timeout，1927独立WT，不改业务/门槛。来源准备e4f已独立有限Ship，不计R06产品live。新包只有复核后才集成，不能只把函数写成accepted。

API/Vite/worker/beat段均到期结束；MinIO段3 18:57:02结束，段4 18:57:49启动、47秒间断，20:57:49硬截止，工具session31426，日志reports/runs/recovery_r04_minio_segment4_20261015/；Docker总截止2026-10-17T21:49:15+08。只有有界服务运行，无会话外后台承诺。秘密/缓存/连接仓外；双人金标/裁决与FOFA授权资产范围缺，PPT用户后置；容器semantic/容量/固定出网待R20，RFC850非阻断误blocked债务待修。下一步文档freeze/review/正常push核对→R06真实入口及持续采集→R07–R10；R24-A→R23→R24-B不变。

"""
for path in ("progress/context_handoff.md", "progress/recovery_workstreams.md", "progress/blockers.md"):
    write(path, snapshot + read(path))

write("reports/runs/recovery_r05_controller_20261015/gb_registration_receipt.json", json.dumps({"recorded_at": NOW, "reviewed_code_sha": SHA, "review_ref": REVIEW, "original_T_tasks_unchanged": state["tasks"] == original_tasks, "push": "not_yet_performed"}, indent=2) + "\n")
print(json.dumps({"registered_at": NOW, "reviewed_code_sha": SHA, "original_T_tasks_unchanged": True}))
