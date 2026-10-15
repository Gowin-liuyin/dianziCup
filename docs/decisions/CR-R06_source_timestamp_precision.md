# R06 来源时间精度与固定政策完整性小合同

落实已批准的未知不等于确定时间、原文版本可追溯与真实来源目标；不改官方评分/金标/分母。冻结供独立定向核对，awaiting_review。

初审M2证实fromisoformat宽松将+00:99归一、-00:00当UTC、7位小数截成6位。首个修复草稿把>6位全部拒绝，但真实OSV原样本modified=2026-09-10T03:49:48.487641080Z有9位合法小数，原回归失败。原红日志保留；不能删此样本或伪造精确时间来过门。

新资料时间边界按64字符上限严格校验ASCII日期/T/时分秒/offset语法与日历，非法offset分/秒、非法日期或无法表示的已知UTC拒绝并隔离整页。合法缺失/date-only/无时区保持unknown；合法-00:00表示未知offset、合法小数超过PG/Python无损支持的6位时保留原值，source_published_at/source_modified_at=NULL，不截断成instant。OSV published/modified/withdrawn与GitHub release的raw时间合同仍要求显式offset语法，可保留未知offset/高精度raw；日期缺失不补抓取时间。

_json_document统一保存published_at_raw、modified_at_raw、published_precision、来源notes及catalog-pages-2版本；派生与原始payload均保留原timestamp字符串和原hash追溯。公开GET已有published_precision=unknown与nullable时间可兼容表示，无新DTO或字段泄漏；高精度modified原值在受版本保护的metadata/原始证据中。未知/失败/超6小时在原统计桶中分别报告，不让无有效时刻从总分母消失。原NVD/vLLM已审严格时间策略保持不变。

兼容/迁移：无需schema迁移，旧修订和旧原值不覆盖。修复后同内容的metadata/来源规则版本改变会形成新资料修订及原PG变更信号；原错误精确时间仍可在旧历史版本审计，不再作为新当前精确时间发布。回滚关闭新增采集并恢复旧代码，不删除历史/复位游标；旧代码不能用来重新发布已知错误时间。

M1在固定CAC2023政策上另验证每条heading之后的正文非空，生效句必须属于最后条款，不允许被前言的“施行”满足。固定日期或内容改变进入明确隔离/复核，不能据此推断法律有效性。已有完整原HTML仍是正例，去掉末条正文的原字节负例保持失败；未执行页面脚本。

任务/测试：源helper全部caller、原OSV/仓库/date/null/ranges、资料API unknown投影与实际PG游标/回执原子性均回归；-00:00与超精度需验证原值保持且NULL/unknown，非法+00:99需blocked/无本页提交。初审原blocked预期日志保留，由同独立reviewer依据本明确兼容策略补unknown复验，不改holdout或原指标门槛。规则只影响本恢复来源切片，不表示整R06/G-C通过。
