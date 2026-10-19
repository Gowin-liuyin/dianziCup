"""Synchronize approved integrity guards and reviewed schema digests using actual time."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
STAMP = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
guard = ROOT / "docs/decisions/CR-recovery_0023_0026_integrity_guards.md"
assert not guard.exists()
guard.write_text(f"""# CR · 恢复0023–0026完整性加强

文档首次创建时间：{STAMP}
本次写作开始时间：{STAMP}
状态：approved_for_implementation；迁移代码16484eac已独立有限Ship，本文补充仍须该reviewer核对。
授权：本次有界批处理和已批准CR-R02/CR-R07/CR-R09；落细PG权威、不可变历史、未知与权限边界，不改变评分、盲测、阈值或范围。主控先前派发的精确guard指令已在作者approved_guards材料保留，本正式记录晚于实现，不能冒称提前创建。

0023沿用冻结五statement提案与nullable新列，增加DELETE guard仅拒绝删除已有input_audit_payload的冻结收据，不阻止无审计旧step正常生命周期。其余audit一次写入及completed/model trace/workflow identity约束不改。

0024完整qa_conversation_turns只追加，UPDATE/DELETE拒绝；qa_conversations active slot/version/revoke与grounded_answers pending→terminal正常更新仍允许。保留deferred跨owner/tenant约束，NULLtenant使用IS DISTINCT FROM；查询型trigger函数固定创建时search_path。当前与作者1e210090 metadata guard已对齐；应用读旧损坏历史仍独立验证hash，不能拿新trigger掩盖历史负例。

0025 graph_projection_batches只追加，UPDATE/DELETE拒绝，PG对实际bytea核SHA256而不只看hash格式；graph_projection_state仍正常可更新。这些是可丢弃的派生投影，不成为事实或任务真相。应用metadata的同等完整性尚须核对接入，不能因迁移通过推断default graph producer已接。

0026保持已冻结APIkey owner/resource/scopes/expiry/rate metadata，真实令牌仅一次返回、PG只hash；限流必须在外部IO前，与新job幂等/预算同事务一次消费。此迁移不改变旧cookie管理接口，也不自动给read-only key管理权限；HTTP、async ActorRef与current-auth接线另片仍必须完成。

兼容/迁移：顺序0022→23→24→25→26，旧表逐列raw/hash保留，0023旧行保持NULL，其他新增表不重写旧事实。因保留历史本批downward拒绝；应用回滚关闭新增入口、保留PG历史，修复采用前向migration。只在明确隔离测试库检查失败事务回滚，禁止开发/正式库downgrade或清理。

任务/测试影响：R07/R10/R12/R18/R20及其全部原T映射；正负immutable/nullable/owner/NULLtenant/DST/并发slot、schema影子、0026失败事务、恢复与旧fact快照必要。独立review60+6真实PG和18+7+5合同通过；旧head0019五项4pass/1fail原红保留。本记录未修原oracle，须另正式回归CR及统一复跑。材料raw whitespace red与首轮子日志复用缺口如实保留，不计产品或正式live/manual通过。

本次写作结束时间：{STAMP}
最后更新时间：{STAMP}
证据截止时间：{STAMP}
""", encoding="utf-8", newline="\n")
public = ROOT / "docs/decisions/CR-R18_public_envelopes_and_output_budget.md"
content = public.read_text(encoding="utf-8")
old = "af28d516ddfb894eece4c88a8520f71b4ff0ecf37281296adfd30d4a98ed4611"
new = "4ccc4337586137a407359a1c4a59dc5d92081a2f4b50ee32cc53fac16095d50b"
assert old in content
content = content.replace(old, new).replace("最后更新时间：2026-10-16T09:26:01+08:00", f"最后更新时间：{STAMP}")
content += f"\n修订记录：{STAMP}；831c61f收紧新TaskDescriptor.poll_uri UUID分组；原14defs不变，独立28+97通过。旧23/root初始schema和原红保留。新source/contract摘要已同步，不放行整R18或生产接线。\n"
public.write_text(content, encoding="utf-8", newline="\n")
print(STAMP)
