"""登记既有CR-R04下问答提交与权限事务的实现合同，不改外部评分或授权。"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
path = root / "docs/decisions/CR-R04-R05_question_commit.md"
assert not path.exists()
now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
path.write_text(f"""# CR-R04 / R05 · 引用问答持久化与提交权限补充

首次创建/本次写作开始/结束/最后更新时间：{now}。状态awaiting_review；主控/root。属于已批准CR-R04公开合同适配、R02 PostgreSQL认证/状态、R05单事件引用问答的实现记录；修复05 API §2原必需请求键、进程中断和撤销竞态，不改变身份模型、角色、租户、评分、金标、费用授权或R12最终范围。

输入是经Cookie/CSRF校验的公开事件单问；POST /v1/questions 与 /api/v1/questions 使用同一服务与PG记录，GET /answers/{{answer_id}}只返回同一user+tenant拥有的答案。QuestionRequest/QAAnswer v2不扩字段，data_mode与完整耗时保留；不支持的资产/历史/多轮/调查范围422，后续R12补齐。引文来自永久证据，派生pgvector与本地模型不能另建事实真相；完成前复查epoch、公开可见、当前revision、有效claims、原文hash与精确子串。

所有成功问答写入必须ASCII可见字符1..200的Idempotency-Key。缺失/空/非法在服务预约前422 invalid_key，无模型调用。相同user/tenant/键以结构化JSON形成稳定答案UUID；相同body重放返回PG原操作，不新付费；异体409。PG唯一预约和每进程1个同步槽分别防跨进程重复与容量耗尽。没有故障时自动重试付费请求的后门。

PG model_trace记录独立reservation_id和UTC到期时刻。单预约420秒是保守回收上限，不是P3性能达标：至多64片段、8批passage+query+rerank各30秒上限，加两轮生成65秒上限及短PG IO；实际完整客户端时延另报。GET或同key重放观察到到期时，通过pending+原owner+原expiry的CAS将预约标failed / answer_interrupted，费用unknown、未取得调用元数据标incomplete_interrupted，不将空attempts伪称0付费。没有重发模型。late writer完成必须仍pending、同reservation_id且PG clock_timestamp未到期，否则不能覆写终态；已获得的晚到attempts可以追加到原trace，不能把失败改成成功。旧无reservation元数据的pending不擅猜owner/重付费，需要显式人工恢复；已完成旧答案不受影响。当前真实试验库此前无此类旧pending。

最终提交在同一PG事务内FOR SHARE锁定auth_sessions与users，再读取当前role/tenant与过期/撤销状态，检查READ_PUBLIC与原主体一致，再锁scope epoch并完成答案CAS。提交锁内不运行外部模型。撤销或用户归属变更若先提交，答案失败；答案已持锁时撤销等待提交，线性顺序可复验。GET当前性读取也持相同认证锁；scope_provider事务外初检不能替代该锁。新增auth_state.lock_authenticated_scope仅供调用者现有连接事务使用，不签发/修改会话。

兼容与迁移：0014只新增派生检索块和答案表，原文/证据/事实/游标保持；真实来源库0013→0014已核对105事件、434证据及证据身份hash不变。内部GroundedQuestionService.ask/read_grounded_answer新增keyword-only session_token，由认证HTTP Cookie传入，不进模型/日志/trace；所有当前产品调用方为question_routes，已核查，外部REST schema不变。独立探针如直接调用内部函数，需传自有隔离PG会话token。测试中的显式内存认证只验证前置拒绝，不可用于产品提交锁后备。

回滚：关闭问答POST入口与新调用，保留已存答案、用量、失败及0014表，使用前向修复；不降库、不删除历史、不回退fixture或旧可空键/无权限锁实现。部署容器的semantic extra、内存和受控出网仍须主控另行接通，当前Windows真实段并非容器复现证明。

任务与测试影响：R05/R17当前切片、T18/T20/T30/T31/T43的后续合并验收；R14/R20最终恢复仍须调度/运维覆盖。已有34真实PG/HTTP/合同case通过（显式合成模型，不是live），最后SQL expiry条件另2PG通过；82源码mypy/Ruff通过。新独立pipeline reviewer已证实三项原缺陷（缺键、永久pending、撤销/迁租提交竞态），需在新冻结SHA独立复验到期、late owner、真实logout/tenant先后顺序和当前答案历史，未取得意见前不签本补充或整R05/G-B。真实公开单问旧23c代码有效key下17.009秒、两次供应商调用及GET/重放成功，仅该有限链路，不替新修复版本背书。
""", encoding="utf-8")
print(str(path))
