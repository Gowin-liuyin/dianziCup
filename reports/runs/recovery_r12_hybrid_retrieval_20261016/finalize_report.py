"""Update the report from captured final receipts, without synthesizing measurements."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/tasks/R12-hybrid-retrieval.md"
CODE = "f316a7aa432d6f730fa49189814c2559be8b6db4"

content = REPORT.read_text(encoding="utf-8")
content = content.replace("405fb57033bd0ec5f34f2a9f0903292b7a089586", CODE)
content = content.replace("本地提交 fb8b5dc + 405fb57", "本地提交 fb8b5dc + 405fb57 + f316a7a")
for name in ("fixture", "integration", "mypy", "ruff", "format"):
    content = content.replace("frozen_" + name, "final_classified_" + name)
content = content.replace(
    "63 passed、0 failed/error/skip；29 新", "64 passed、0 failed/error/skip；30 新"
)
receipt = json.loads(
    (RUN / "final_classified_integration.command.json").read_text(encoding="utf-8")
)
assert receipt["code_sha"] == CODE and receipt["exit_code"] == 0
old_time = "2026-10-16 05:33:27.202785–05:34:14.562078+08；命令墙钟 47.3588s，pytest 45.58s"
content = content.replace(
    old_time,
    (
        receipt["started_at"]
        + "–"
        + receipt["ended_at"]
        + f"；命令墙钟 {receipt['elapsed_seconds']:.4f}s，pytest 44.10s"
    ),
)
content = content.replace("frozen_cbm_*", "final_cbm_*")
content = content.replace("1533 nodes/7973 edges", "1533 nodes/7973 edges（最终刷新7975 edges）")
for old, new in (
    ("4.8237s / 4.7189s", "4.2140s / 4.3281s"),
    ("0.0168/0.3105s", "0.0237/0.0357s"),
    ("2.5241/2.0365s", "1.8853/1.9847s"),
    ("2.1963/2.3015s", "2.1601/2.2562s"),
    ("freeze + 63/22", "freeze + 64/22"),
    ("复跑冻结405fb57", "复跑冻结f316a7a"),
):
    content = content.replace(old, new)
content = content.replace(
    "以及 bulk 更新未先 refresh 就 delete-by-query 可能碰版本冲突；实际失败和修复回归保留。",
    "以及 bulk 更新未先 refresh 就 delete-by-query 返回固定 unavailable。"
    "原 HTTP 状态/响应体未保留，"
    "旧可见版本导致版本冲突是推断；增加 refresh 后该路径通过，不能把推断写成已记录响应事实。"
    "实际失败和修复回归保留。",
)
content += (
    "\n\n封存前补了一处明确错误分类：HTTP401/403 → opensearch_permission_denied，"
    "timeout → opensearch_timeout，其余HTTP状态为固定安全码；检索partial区分bm25权限/超时。"
    "新增403/timeout合同断言不回显响应/请求秘密；f316a7a全部64/22与静态检查再次通过。\n"
)
REPORT.write_text(content, encoding="utf-8")
print("report reflects final captured receipts")
