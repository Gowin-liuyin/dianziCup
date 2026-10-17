# CR-R18 · 风险汇总合法到期测试输入

首次创建时间：2026-10-17T10:09:51+08:00
状态：Root授权窄输入纠偏；准确落实 awaiting 原独立 reviewer

source9aa 五窗真实 PG 13 distinct 为12pass/1setupfail；auth_scope 的 expired case 将 expires_at=now-1s，但 issued_at=now-约0.873s，触发0006 ck_auth_session_expiry(expires_at>issued_at)，尚未到业务 read/SessionExpiredError oracle。原红/两40P01保持。

唯一原作者仅该case以同fixture_now设 issued_at=now-2s/expires_at=now-1s，校正合法 expired interval。生产 source blob、原函数、assert/grade/ACL/等待/阈值与分母不变；直属AST guard只精确归一授权输入三个节点并保留全module原其他AST。独审核差异，Root单target real PG复验，不以其他绿掩盖原红。无 DBschema/业务迁移；回滚只还原测试输入，原证据保留。

修订记录：2026-10-17T10:09:51+08:00 据原PG CHECK和实际时刻记录最小输入修复。
