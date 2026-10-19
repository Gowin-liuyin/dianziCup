"""Register reviewed internal slices while retaining full R06 and original T acceptance scope."""

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


state_path = root / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_fields)
original_tasks = json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
task = state["recovery_tasks"]["R06"]
assert task["status"] == "in_progress" and task["implementation"] == "partial"
refs = [
    "reports/tasks/R06.md",
    "reports/reviews/recovery/G-C-R06-catalog-combined-review-1.md",
    "reports/reviews/recovery/G-C-R06-document-api-review-1.md",
    "reports/reviews/recovery/G-C-R06-feed-parsers-review-1-recheck2.md",
    "reports/reviews/recovery/G-C-R06-repository-community-review-1-recheck.md",
]
for reference in refs:
    assert (root / reference).is_file()
    if reference not in task["evidence"]:
        task["evidence"].append(reference)
task["history"].append({
    "recorded_at": at, "prior_status": task["status"],
    "prior_implementation": task["implementation"],
    "event": "Integrated independently reviewed internal catalog/legacy migration/source parsers/document GET slices at f1db487; full R06 remains partial with worker/browser/coverage live pending",
})
task["verification_scope_notes"] = {
    "recorded_at": at,
    "current": "内部公共保存/旧35升级/A-B适配/新资料GET已分别独立Ship并集成f1db487；新7源worker与实际资料浏览器尚未接通，整卡八层not_run保持，组件结果见R06报告与独立意见。源wrapper86e1fd5仅自检1703/74.41%，未整合/独立review；不得视为R06或G-C通过。",
}
state["updated_at"] = at
state["updated_by_task"] = "R06 reviewed internal integration; G-C remains in progress"
assert json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True) == original_tasks
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

stage_path = root / "reports/stages/recovery/G-C.md"
stage = stage_path.read_text(encoding="utf-8-sig")
first_created = "文档首次创建时间：2026-10-15T19:18:55+08:00"
assert first_created in stage
headers = {
    "本次写作开始时间：": at,
    "本次写作结束时间：": at + "（集成后的内部证据更新；阶段未结束）",
    "最后更新时间：": at,
    "本报告证据截止时间：": at,
    "已测代码SHA：": "公共库8430197、GET49ee33、A10c81f0/B84faff9；已合入f1db487，合并后回归尚未运行",
    "已审代码SHA：": "8430197公共组合、49ee33资料GET、A10c81f0/B84faff9；UI0a8仍待原reviewer最终封存",
    "提交/推送结果：": "G-C尚未阶段push；G-B c229已于19:28:36+08远端核对，真实push超时收据见台账",
}
stage = "\n".join(next((prefix + value for prefix, value in headers.items() if line.startswith(prefix)), line) for line in stage.splitlines()) + "\n"
marker = "## 2. 当前真实状态与修改\n"
current = f"\n当前权威更新 {at}：main集成f1db487。公共库8430197新独立35+21+1450/73.90%及11探针/8种子检查限定Ship；资料GET49ee33新独立1687/74.74%、20原PG/API+31扩展PG限定Ship；A/B原专项Must均独立关闭。上述组件已集成，合并后回归待运行，整阶段不能过门。资料UI0a8的305unit/8永久Edge与独立修正5Edge已报告通过，待最终独立封存后合入；新7源worker由独立实现Agent并行。下列19:18:55文字为初始状态历史，不覆盖本段；各原始红例保留。完整当前范围、资源和依赖见[当前R06报告](../../tasks/R06.md)。\n"
stage = stage.replace(marker, marker + current, 1)
stage += f"\n{at} /root修订：登记独立内部意见、代码合并f1db487、G-B真实远端收据，原T与R06整卡状态/原门槛保持。政策末条正文丢失红例与main-content修复、来源JSON节点有界扩展86e1fd5尚待新独立审查；不使未接线模块或probe冒充产品live。\n"
assert first_created in stage
stage_path.write_text(stage, encoding="utf-8")
print(json.dumps({"recorded_at": at, "original_T_tasks_unchanged": True, "R06_status": task["status"]}))
