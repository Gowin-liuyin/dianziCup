# G-A · 合同纠偏与真实运行底座

文档首次创建时间：2026-10-14T20:56:36+08:00
本次写作开始时间：2026-10-14T20:56:36+08:00
本次写作结束时间：2026-10-14T20:56:36+08:00
最后更新时间：2026-10-14T22:19:34+08:00
阶段实际开始/结束时间：历史未单独记录；首个已记录时钟为2026-10-14T20:44:18+08:00，仅为观测时点 / 尚未结束
本报告证据截止时间：2026-10-14T22:19:34+08:00
主控/实现Agent：/root；R00验证器 /root/r00_plan_validation
独立审查Agent与报告：/root/r00_independent_review，reports/reviews/recovery/G-A-R00-review-1-recheck.md（仅R00）；阶段门尚未发生
阶段状态：in_progress
实现状态：partial
各层验证状态：unit=not_run；contract=not_run；integration=not_run；security=not_run；frontend=not_run；e2e=not_run；live=not_run；manual=not_run
工作分支：codex/full-delivery-recovery
已测代码SHA：旧审计复核对象8e265dc039a67319140f003f6a070ea714bf7bef；本阶段候选尚未冻结
已审代码SHA：尚未发生
提交/推送结果：b8199ce5dd0a7920ce5770e4f580fe23e0fe9f6b仅授权文档基线提交；阶段push尚未发生

## 1. 本阶段要解决的用户问题与验收范围

R00–R03，原T00/T01/T02/T03/T04/T05/T06/T07/T08/T16等能力切片；E1/F1/P1/A1/D1/R2，U01/U09/U10底座。输出准确合同/状态、默认认证API、PG业务真值与会话、真实worker与可靠游标。原T卡仍需所有切片和原六类验收。

## 2. 当前真实状态与修改

实际基线main@8e265dc，origin与授权URL一致，无tracked用户修改；本次四份计划/提示词/审计未跟踪文件经核对加入b8199ce文档基线。新增CR-R01–09待独立核对。旧状态原文含T18重复note已按原字节存档，不覆盖历史。运行与模型装配缺口仍未修复，不用状态“改绿”。

## 3. 并行执行与独立审查

[文件所有权与各工作包](../../../progress/recovery_workstreams.md)。当前两个只读分析包与一个验证器实现包独立写入。冻结批次后另新review；整个G-A仍需另新阶段review，不以R00过门代替运行底座。

## 4. 问题台账

| ID | 发现时间/触发/预期与实际 | 根因/影响 | 状态/下一步 |
|---|---|---|---|
| RA-001 | 本轮具体时刻见baseline-probe；默认/auth/me应401，实际404 | 默认create_application未注入认证；R01/U01 | 未解决；R01真实装配 |
| RA-002 | 本轮具体时刻见baseline-probe；唯一条目保存失败，游标仍before→after | 内存callback且失败未持久化；R03/R06漏采 | 未解决；事务与可恢复任务后推进 |
| RA-003 | 本轮具体时刻见baseline-probe；真实PDF/NVD失败 | TEXTLAYER测试标记与wrapper/CVSS错层；R04/R09 | 未解决；真实解析与原文证据回归 |
| RA-004 | 本轮具体时刻见baseline-probe；新实例会话/审计/事实丢失 | 内存状态；R02/U09/U10 | 未解决；PG事务/重启 |
| RA-005 | 2026-10-14T20:56:36+08:00；当前JSON普通解析吞T18首note | 重复键、旧accepted缺分层证据；R00全部前置 | 待复核；保留原字节、严格拒绝+纠偏 |
| RA-006 | 2026-10-14T20:50:51+08:00；模型/测绘候选环境变量三域为空 | 产品凭据/提供者未知；R05/R08/R13 live | 外部阻塞；已最小输入异步询问，代码独立推进 |
| RA-007 | 本轮具体时刻见baseline-probe；logout无Origin/CSRF仍200 | HTTP路由未调用write校验；R01/R20认证 | 未解决；装配前补真实路由负例 |

修复SHA/关闭时间均尚未发生。测试153通过只是局部fixture/纯逻辑，不表示这些产品问题关闭。

## 5. 实际验证

当前命令与证据：[基线](../../runs/recovery_r00_20261014/baseline.json)、[新索引命令](../../runs/recovery_r00_20261014/index_commands.json)、[运行复核报告](../../reviews/recovery/G-A-baseline-probe.md)。R00产品integration/security/frontend/e2e/live/manual均not_run；独立产品真库重启/竞争尚未运行。Docker Desktop已主控授权启动，守护进程当前可用性仍待就绪复核。没有真实采集服务/观察窗口。

## 6. 合同与计划差异

[CR-R01–CR-R09](../../../docs/decisions/CR-R07.md)准确落实核验待独立review；仅用户已有建设决策，无新评分/金标/分母变更。R19工具统一R04真实链之后、R24A→R23→B及切片依赖将同步manifest/地图，未声称已生效。

## 7. 评分和场景证据

E1/D1是当前合同/可追溯流程证据，F1/F2/F3/P1/P2/P3/A1尚无新正式成绩；U01/U09/U10产品运行效果仍待R01–03。R00表单/JSON校验不能替代这些评分证据。

## 8. 阶段结论和下一步

G-A尚不能过门。先完成R00新独立review使合同生效，再接R01运行入口、R02持久化、R03worker/游标；外部产品模型缺口不影响G-A内部运行实现，但不得冒充G-B回答live通过。

## 9. 文档修订记录

2026-10-14T20:56:36+08:00：/root首次建立阶段报告，全部未完成项保留状态和问题；后续每次写作时间从真实时钟记录。

2026-10-14T21:16:53+08:00：/root补充R00 48/48计划与公共合同通过、旧基线哈希负例/冻结内容完全不变、旧accepted纠偏和新schema/切片；真实产品问题仍未关闭，准备冻结新非作者review。用户提供凭据已仓库外DPAPI保护，不回显；PPT后置，平台/UI优先。Docker诊断发现临时dockerInference socket移除失败导致引擎停止，正在有限可逆修复，尚未计通过。


2026-10-14T22:19:34+08:00：独立reviewer /root/r00_independent_review 已在冻结15d0272bd2a9e25d19397d8147e9c3cbe6016f9b完成56/56与静态检查、切片正负例、新干净Windows/WSL基线0/0。依据[reports/reviews/recovery/G-A-R00-review-1-recheck.md](../../../reports/reviews/recovery/G-A-R00-review-1-recheck.md)仅登记R00与三个R00输出切片accepted、九CR生效；原整T不自动接受，G-A未过门、未push。R01质量/前端从该批准合同基线独立worktree实施。真实PG16.14/pgvector0.8.2与Redis7.4.11资源已认证读写/重启/负例，仍非应用集成。
