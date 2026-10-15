"""平台修复的实际证据，不将组件复测当作整R04验收。"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
run = Path(__file__).resolve().parent
now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
totals = json.loads((run / "full_unit_2.coverage.json").read_text())["totals"]
receipt = json.loads((run / "full_unit_2.receipt.json").read_text(encoding="utf-8-sig"))
report = f"""# R04 · PDF子进程跨平台类型兼容修复

首次创建/本次写作开始/结束/最后更新时间：{now}。
状态awaiting_review；root；G-B独立准备，未签G-A/B或整R04/T09。

API实现者在Linux全unit真实复现：既有pdf_text.py访问subprocess.CREATE_NO_WINDOW，Linux typeshed没有此Windows专属属性，原T02 mypy质量恢复用例失败。Windows同版不复现；不是缺模型或业务fixture失败，原作者Linux失败保留于其R04-knowledge-api报告/日志。

最小修复只把专属属性改为命名整数WINDOWS_CREATE_NO_WINDOW=0x08000000，仍仅os.name=nt传该值，Linux传0。复用既有subprocess与全部PDF资源限制，无新库、无OCR替换、不改parser/normalizer版本或既有文档。依据[Win32官方进程标志](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags)。回滚这行会恢复Linux类型检查失败；无需数据迁移，应前向修复。

实际验证：早先固定a7 Linux PDF33/33通过（linux_2.*），但这不足以证明完整工程入口。新修复root工作区全Linux unit于{receipt['start']}–{receipt['end']}，396通过、0失败/skip，包含T02类型恢复测试；原始coverage={totals['covered_lines']}/{totals['num_statements']}={totals['percent_covered']}%，保持60门。每次独立venv+PYTHONPATH+独立COVERAGE_FILE，full_unit_2.*可查。full_unit_1曾与Windows同checkout默认coverage文件并发，其396行为结果保留但覆盖率不作门证据；修正隔离缓存后第二轮通过，不删除首轮日志。环境使用原官方锁68包，另建/tmp/dianzi-r04-linux-check-20261015/venv，不改Windows.venv。

root Windows后续440相关unit/PG/source回归通过（来源任务reviewed_fixes_4_isolated_coverage），含另批尚待独立审查的网络POST；不能把它写成此小修复固定SHA已独立通过。修复将单独冻结，阶段新reviewer或原PDF独立reviewer须核对真实新代码；新API、来源worker/浏览器、live模型及正式指标仍未因本修复完成。unit/integration仅上述范围，security/frontend/e2e/live/manual整卡not_run。
"""
(root / "reports/tasks/R04-PDF-linux-compatibility.md").write_text(report, encoding="utf-8")
print(now)
