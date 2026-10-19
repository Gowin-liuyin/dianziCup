"""Authorize one shared root-cause correction without changing evidence support rules."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
text = f"""# CR-R07 · 完整候选校验后报告必要上下文缺口

首次创建时间：{started}
写作开始/结束时间：{started} / {datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')}
主控：/root；状态：awaiting_review；未实现或独立验收。

可复现问题：原合法原文 PyPI widget >=1.0,<2.0，必要 Only when tools enabled 被模型输入选择省略，同时模型伪造 fixed=99.0。共享校验先抛context_missing，owned模型层看到真实省略便改BLOCKED，掩盖另一个不被原文支持的版本边界。独立9c probe确认实际结果，原红保留。真实缺口不能为错误字段提供豁免。

本次授权仅共享根因修复：唯一实施者r07_taxonomy_and_bounded_evidence_inputs_implementation可在其独立worktree修改 enrichment/field_sources.py 的三个对应validator及 FieldEvidenceError，并在owned model_fields.py删除复制的qualifier正则。先验证所有引用位置/原文hash、值/版本boundary/目标/限制，全部通过后才报告必要context缺口。异常新增严格typed context_gaps（默认空、服务端从原文计算的revision/block/Unicode范围）；str/code原接口保留，单一错误码不变，多个错误先报告真实不支持值，不能把客户端自报范围当可信支持。

不改变source URI信任名单、正则/支持规则、维度/状态枚举、原文完整性、schema、预算、认证、评分或金标。BLOCKED只在其他值已核验且必要context实际与omitted ranges相交时使用；坏引用/坏值/格式仍FAILED，空结果PENDING。公开fact与graph必须仍拒绝未支持值。

调用者范围：field_candidates、model_fields、publication、R10 evidence_graph及它们全部源/测试调用由CBM+rg重新核实，不以此列作完整性保证。原catch只用安全code的路径兼容默认空gap；不得对前端或日志回显私有原文/完整URL。图与发布shared回归和四类字段正负例必须复跑，新修复仍由原独立reviewer定向复核，root不自签。

迁移：仅代码，数据库/已有原始收据无回填，不重新解释或覆盖历史。现已冻运行与审查候选保持旧SHA；本次另冻新SHA/材料后才集成，不给旧窗口拼新算法。

回滚：回退本共享校验与owned缺口状态判断作为一个行为单元；只退共享部分会恢复掩坏值的问题。没有数据删除。尚未生产迁移。

验收：原URI/YAML两Must与合法/非法未见span、混合badcandidate、false boundary+omittedcontext原探针原输入不变；四字段/图/出版相关测试与真实PG位置/ACL需重测。复用既有validator保证只有一套必要context定位，无新库或通用框架。对应R07/T20和R10读取安全；所有限界与未完成live保留。
"""
(ROOT / "docs/decisions/CR-R07_context_validation_seam.md").write_text(text, encoding="utf-8", newline="\n")
print(started)
