"""Append real document integration evidence without changing whole-card acceptance."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


live = root / "reports/runs/recovery_r06_document_live_20261015"
browser = json.loads((live / "browser_command.json").read_text(encoding="utf-8-sig"))
collected = json.loads((live / "collection_receipt.json").read_text(encoding="utf-8-sig"))
assert browser["exit_code"] == 0
assert collected["code_sha"] == "0a45185ae3ffb73a6d186b98421e26a52f78bfc6"
state_path = root / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_fields)
original_tasks = json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
task = state["recovery_tasks"]["R06"]
assert task["status"] == "in_progress" and task["implementation"] == "partial"
for reference in [
    "reports/reviews/recovery/G-C-R06-document-workspace-review-1-recheck2.md",
    "reports/runs/recovery_r06_document_live_20261015/collection_receipt.json",
    "reports/runs/recovery_r06_document_live_20261015/browser_command.json",
]:
    assert (root / reference).is_file()
    if reference not in task["evidence"]:
        task["evidence"].append(reference)
task["history"].append({"recorded_at": at, "prior_status": task["status"], "prior_implementation": task["implementation"], "event": "Integrated independently reviewed document UI at 0a45185; actual 30-source-documents/143-evidence API and 3 real Edge tests passed; whole R06 remains partial"})
task["verification_scope_notes"] = {"recorded_at": at, "current": "公共库/A-B解析/资料GET/UI分别独立Ship并合入0a45185。独立专库真实两源30文档/143证据，2任务均因max_pages1诚实partial；实际Edge桌面/390/打开原文3pass。新7源worker、新9源管理UI仍独立实现/awaiting_review；整R06八层not_run保持，不能把组件与实测相加为阶段验收。"}
state["updated_at"] = at
state["updated_by_task"] = "R06 actual document API/browser integration; G-C in progress"
assert json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True) == original_tasks
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

snapshot = f"""## 当前权威快照 · {at}

主控codex/full-delivery-recovery，HEAD 0a45185ae3ffb73a6d186b98421e26a52f78bfc6；远端最后核对G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7（19:28:36+08）。G-A/G-B限定accepted，G-C/R06 in_progress/partial，原T整卡与全部映射条件未改变；G-C未push。

公共库8430197、A10c81/B84faff9、资料API49ee33/72eb1c及资料UI2f5/0a8已分别独立限定Ship并合入main。资料UI第三Must权限竞态已独立关闭，最终review4081154b...；305unit/8永久Edge与独立44unit/6原Edge/6修正Edge通过。主控正在0a45185运行合并后pure和41PG回归，session55322/13665，run recovery_r06_integration_20261015；未完成不能先登记通过。

同0a45185固定WT D:/wt/r06-document-live-0a45185，专库test_dianzi_r06_documents_live_20261015/0015、Redis13、API28011、UI25174。21:01:51启动，硬截止21:21:51；21:02:31至46实际认证/CSRF采集NVD20+vendor10，30events/docs/revisions、143evidence、2真实HTTP；两任务因max_pages1均partial/source_page_limit_reached。21:05:16至25实际Edge3pass8.8s，桌面1366/390、列表20+10、详情/固定历史/证据hash/退出权限、原文popup均无拦截/0模型调用。覆盖unknown诚实显示。截图document-visible-1366.png/390.png在run recovery_r06_document_live_20261015。首次可视截图仪器未在检索清选后重新选资料，TimeoutError保留initial脚本/log；只修capture脚本重选后21:14:57Z已标UTC的capture成功，产品未改、原3test分母不变。主控已写stop.request请求结束此短段，runtime_end待确认，不能拼成6小时。

4槽滚动：root独占合同/schema/迁移/锁/状态/集成/Git；r06_legacy_migration_fixture_repair独占D:/wt/r06-worker-wiring source_jobs/source_routes与新测试，基线86e1fd5，新7worker1760pure/74.42%及33PG+25API PG已报过，仍待冻结和全新review；r06_document_workspace独占D:/wt/r06-source-admin-ui的source-contracts/来源UI及直接tests，基线0a45185，新339unit/8Edge已报过待冻结/新review；全新native_cpu_guard_independent_review只审D:/wt/native-cpu-guard冻结代码36884c7/材料994c381，无业务修改。宿主硬4槽，不能实际启6–10。

root来源包装代码f0924a0、包含精确fixture86e1fd5、报告最终38496017e63fa5bd98352cc6065a1817c6d02cb0在D:/wt/r06-source-wiring，awaiting_review未合入。真实AVID tree/NIST48页/CAC完整24条仅probe，不计worker成功；1703pure/74.41%/Ruff/mypy92。后续必须与新worker整体冻结给全新reviewer，审所有共享strict_json_object调用者。CR-R06_source_collection_catalog已在main0a45185冻结9keys/同POST合同，独立核对尚待。

原1927固定6小时服务仍独立：19:45:24至次日01:45:24，API28010/Redis12；21:15:12四服务alive/36source jobs38attempts/93.65625CPU/peak457506816B。既有148事件149修订520证据为历史回补，不声称及时/无漏采。MinIO19:45:17至次日02:15:17，WSL8440/8461，29400；Docker总deadline2026-10-17T21:49:15。旧G-B库不迁移，新工作均独立专库。

真实模型累计8次/fee unknown，本轮0新增；缺双人独立标注/裁决与FOFA授权资产范围，PPT用户后置。R07–R10、资产/多跳/Agent/推荐/协议/正式评测/最终材料继续，当前不得称完整系统。下一步新normalizer+worker与9源UI分别新review→合入→九源实际API/worker/UI有界live→G-C其余卡；CPU独立review后集成原门槛修复。R24-A→R23→R24-B保持。

"""
snapshot = snapshot.replace("21:14:57Z已标UTC", "13:14:57Z已标UTC")
for name in ["context_handoff.md", "recovery_workstreams.md"]:
    path = root / "progress" / name
    path.write_text(snapshot + path.read_text(encoding="utf-8-sig"), encoding="utf-8")

update = f"""\n## 资料真实链路更新 · {at}

资料UI源码2f5/冻结0a8已由原独立reviewer复核限定Ship，报告G-C-R06-document-workspace-review-1-recheck2.md，三个权限/导航Must关闭；现合入main0a45185。主控真实专库与同SHA固定WT在21:02:31至46采集30文档/143证据，2任务均因单页预算partial；21:05:16至25真实Edge3pass8.8s，无路由拦截，包含1366/390、30条分页、当前/固定历史/证据hash/未知覆盖/退出和来源popup，reduced-motion通过。原始collection_receipt/browser_command/browser_report及两viewport截图见recovery_r06_document_live_20261015；0模型调用、不是正式评测。

可视截图脚本首次检索后未重新选中资料，等待已被正常清除的inspector超时；原脚本/log封存initial，修正截图导航后实际两viewport成功，产品代码未变、原3测试不覆盖。短段已请求owned stop，实际结束以runtime_end为准。合并后pure/PG回归正在运行，不预填通过。

九源管理UI新批339unit/8Edge、worker1760pure/74.42%及33+25PG为作者当前自检，冻结/独立审查未完成；来源包装384960仍awaiting_review。全新CPU reviewer审36884/994c。阶段与整R06仍in_progress/partial，八层not_run保留。
"""
task_path = root / "reports/tasks/R06.md"
task_path.write_text(task_path.read_text(encoding="utf-8-sig") + update, encoding="utf-8")
stage_path = root / "reports/stages/recovery/G-C.md"
stage = stage_path.read_text(encoding="utf-8-sig")
headers = {"本次写作开始时间：": at, "本次写作结束时间：": at + "（更新真实资料证据；阶段未结束）", "最后更新时间：": at, "本报告证据截止时间：": at, "已测代码SHA：": "0a45185实际资料API/Edge3pass；合并后pure/PG运行中；组件原SHA见专项报告", "已审代码SHA：": "8430197公共库、49ee33资料GET、A10c81f0/B84faff9、2f5/0a8资料UI；整阶段未审"}
stage = "\n".join(next((prefix + value for prefix, value in headers.items() if line.startswith(prefix)), line) for line in stage.splitlines()) + "\n"
stage = stage.replace("## 2. 当前真实状态与修改\n", "## 2. 当前真实状态与修改\n" + update + "\n下列早期时间段均为历史，不能覆盖本段。\n", 1)
stage += f"\n{at} /root修订：资料UI独立Ship合入与真实PG/Edge证据更新；截图仪器错误保留；没有变更原门槛、原T整卡或阶段状态。\n"
stage_path.write_text(stage, encoding="utf-8")
print(json.dumps({"recorded_at": at, "original_T_unchanged": True, "R06": task["status"]}))
