"""记录原候选游标的内部历史截止适配，保持默认行为与评分合同。"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
path = ROOT / "docs/decisions/CR-R16_immutable_revalidation_actor_binding.md"
addition = f"""

## 分页兼容补充 · {started}

原候选fingerprint包含评估历史，写一页新历史后会使下一页cursor失效。批准唯一R16作者为内部CandidateDiscoveryService增加可选assessment_created_before：默认None保持原候选与旧cursor合同；使用时必须aware，取服务端持久parent时点，签入游标/query fingerprint且筛选assessment.created_at<=截止。新重算追加历史不改变这份历史候选集合；资产、权限、epoch或规则真实变化仍必须拒绝旧cursor。截止值不来自HTTP自报，不能用该冻结掩盖事实/授权变化。

父任务每页发现→同事务创建幂等子任务及带冻结截止/游标的下一parent，调用和页/child预算保持可控；未消费位置必须持久化并返回partial，不把发现上限当已全部处理。无需新增平行签名游标、索引或业务表。独立复验须覆盖默认旧行为、截止边界、后写续页、真实变化拒绝、空/旧/新增候选与重放。schema与身份7列合同不变。
"""
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
path.write_text(path.read_text(encoding="utf-8").rstrip() + addition + f"\n本次补充写作结束时间：{ended}\n最后更新时间：{ended}\n", encoding="utf-8")
receipt = {"started_at": started, "ended_at": ended, "file": str(path.relative_to(ROOT)), "scope": "internal additive cursor compatibility; default unchanged; no acceptance promotion"}
Path(__file__).with_suffix(".json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=True))
