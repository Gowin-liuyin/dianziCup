# CR-R16 · 变化历史 HTTP 与授权游标

首次创建时间：2026-10-17T10:09:51+08:00
状态：既有批准建设目标内实施；准确落实 awaiting 独立 review

冻结 docs/plan/05 的 GET /changes 当前未装配。复用现 FindChangesArguments 与 ChangesPage/PG shared read，首切片 event_id 必填、limit 1..25、cursor 2048 字节，响应 {status:succeeded|no_result|partial,data:ChangesPage,error_code:null|change_history_incomplete,limitations:string[]}。partial 不降为空成功；错误固定代码，不输出 SQL、私有 payload 或凭据。Root 默认 App 接线；asset_id、旧/新结论及证据详情仍属最终范围，不以本摘要代替。

同事务认证后通过 _authenticated_read 新可选 keyword-only authorize_read 回调计入 bearer rate；业务失败全部 rollback。现不传 callback 的调用保持原行为。变化游标 fingerprint 追加 user_id/tenant_id/role/排序 permissions/permission_version，保留 event inputs/public epochs 校验。权限或版本变化及旧未绑定游标明确409，不返回空页。只由指定 R16 作者修改 read_adapters.py，其余调用方/原测试必须核查；不增加事实数据库、依赖或迁移。

兼容/迁移：新增 REST adapter 与字段明确 envelope；内部 ChangesPage 不变。旧游标失效需重新第一页；历史事实保留。回滚恢复 adapter/seam 版本，不删除事实、任务或数据库；回滚后不得把未绑定游标声称安全。

测试影响 R16/R17、T36–T38/T43、U08：cookie/bearer、scope拒绝、同事务rate rollback、权限/epoch换cursor、partial/空/证据不可用、旧历史不覆盖；unit/contract/security/PG/UI/e2e分层，未执行明确not_run。原评分/Gold/分母/最终old-new与资产能力不变。

修订记录：2026-10-17T10:09:51+08:00 Root记录并行前后端小合同，独立review后据真实版本装配。
