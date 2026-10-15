# G-A · 合同纠偏与真实运行底座

文档首次创建时间：2026-10-14T20:56:36+08:00
本次写作开始时间：2026-10-15T15:21:37+08:00
本次写作结束时间：2026-10-15T15:21:37+08:00（证据平台归属文字更正）
最后更新时间：2026-10-15T15:21:37+08:00
阶段实际开始/结束时间：历史未单独记录，首个已留档时钟2026-10-14T20:44:18+08:00仅为观测时点 / 尚未独立过门
本报告证据截止时间：2026-10-15T15:15:03+08:00
主控/实现Agent：/root及progress/recovery_workstreams.md中的各限定实现包
独立阶段审查Agent与报告：/root/g_a_checkpoint_review；reports/reviews/recovery/G-A-checkpoint-review-1.md（文档差异复核中）
阶段状态：awaiting_review
实现状态：complete（仅R00–R03已批准的G-A能力切片）
各层验证状态：unit/contract/integration/security已取得阶段组合通过；frontend/e2e见不变前端与专项浏览器证据；live仅受控网关单源实测；manual=not_run，无人工金标或正式评测结论
工作分支：codex/full-delivery-recovery
已测代码SHA：b27a79d9bce769564e86034a164010b3fd176080（阶段组合）；8f6bd9f为初审/运行初始候选；31c2866模型另有专项复验
已审代码SHA：8f6bd9f初审与b27a79d三测试修复定向复验；最终阶段文档尚待独立核对
提交/推送结果：代码与证据已本地分批提交；G-A阶段push尚未发生，无已核对远端阶段SHA

## 1. 本阶段要解决的用户问题与验收范围

R00纠正历史accepted证据、CR-R01–R09、T00–T59完整映射及合并验收；R01默认API/认证/worker/scheduler/frontend和依赖/质量入口；R02 PG会话与知识/版本/证据/关系持久化及MinIO；R03 PG任务/outbox/游标、真实Celery消费、有限重试/幂等/围栏和受控外联网关。对应E1/R2/F1/F2/P1早期能力与U01登录/证据准备，不签整张原T卡、U02–U14或官方分数。能力切片依赖按独立激活R00执行；缺失后段仍阻断相应最终卡。

## 2. 当前真实状态与修改

默认应用已装配真实PG认证、会话撤销、共享限流、业务读取路由与真实依赖观察；worker/scheduler观测过期即不ready，导入不联网，缺配置启动或探测明确失败。事实、不可变修订、证据、来源断言、版本关系、维度与任务状态存PG；MinIO官方SDK真实读写并与PG引用/回收锁衔接。Celery/Redis仅传递，不存另一套业务真相；页效果、回执、下页outbox、完成与游标同事务，过期owner不能提交。

复用SQLAlchemy/Alembic、Celery/Redis、MinIO SDK、stdlib/http.client/ssl、既有领域判断与前端React；必要新增是PG repository、装配、权限/事务边界与受控网关，不重写平行账本、无万能CRUD。实际故障揭示的共同根因均修到共享路径：会话并发/CSRF/脱敏、版本归属、引用GC并发、HTTP pinning/时限与重复响应头。后段R04源翻页与R05模型变更有独立专项审查，不能拿其通过替代本阶段审查。

## 3. 并行执行与独立审查

主控独占合同/迁移/依赖锁/状态/集成/push；实现和review各使用独立codex分支/worktree。详细基线、文件权属、提交和专项结论见progress/recovery_workstreams.md与对应tasks/reviews。新阶段reviewer未参与实现，固定8f6新WT后在b27新干净WT定向复核；独立缓存、PG test_dianzi_ga_checkpoint_review_20261015、RedisDB10、自己的worker/API/beat与MinIO测试对象。未拿root正在变化checkout签通过。

新阶段审查发现3项组合测试问题；实现由root完成b27，原非作者重复执行98组合两遍及1200全组合。作者之外的真实Linux API/双prefork worker/beat/强杀恢复、网关与MinIO均由新阶段审查者实际运行。独立报告当前仅文档归档差异复核pending，主控不自签。

## 4. 问题台账

| ID | 触发/预期/实际与根因 | 修复/复验/状态 |
|---|---|---|
| GA-CP-001 | 当前迁移head0013运行cursor fixture仍硬要求0012，49项setup error；应执行原断言，不能跳过 | b27使用官方Alembic当前head比较；原49错误保留；独立98组合连续两次通过，限定已修复 |
| GA-CP-002 | 知识发布后或同库复跑job负载引用测试，硬写public epoch1冲突；不是产品历史丢失 | b27复用PG原子bump_scope_epoch；独立同库98两遍通过，限定已修复 |
| GA-CP-003 | C盘tmp/D盘WT的nested pytest未固定rootdir，误扫系统目录WinError5，exit2而非预期断言失败1 | b27显式rootdir=probe.parent；保留实际失败/脱敏校验，不降低断言；独立98两遍通过 |
| GA-CP-004 | 固定8f6缺11条引用证据文件，root工作区文件存在不等于候选可复现 | d9b8d6归档1909个R01/R02审查/任务/run文件，6533523字节，9实际秘密/321模式零命中；独立固定commit结构复核待完成 |
| GA-ENV-001 | WSL来源DNS失败而Windows网关可达；不能放松TLS/私网限制或伪装在线 | 新阶段Windows显式已批准DoH单NVD真实200；Linux实际仅证明本机API/prefork/beat，未证明来源出网恢复；完整多来源持续运行、生产网络稳定性仍未证明，留R06/R20/R22 |

问题首次发现的精确时刻以新阶段原命令收据为准；未单独记录的写作/发现秒不回填。本报告不重述为新的发现时间。旧auth/PG/MinIO/network专项问题、触发输入/修复SHA/复验和关闭证据见各原始报告，保留历史全文于progress/history/G-A_pre_checkpoint_d9b8d6.md。

## 5. 实际验证

| 冻结版本/范围 | 实际时间与结果 | 原始证据 |
|---|---|---|
| 8f6完整纯unit | 独立678 passed/0fail/0skip；raw3511/5421=64.76664821988562%，原60门 | recovery_ga_checkpoint_review_1_20261015/unit.* |
| b27纯unit | 2026-10-15T15:07:01+08:00–15:07:36+08:00，686 passed；raw3515/5426，门未改 | 同目录recheck收据/coverage |
| b27整组合 | 2026-10-15T15:09:41+08:00–15:11:24+08:00，1200 passed/0fail/error/skip；unit/全contract/security/选定真实PG/MinIO/游标任务；混合raw5126/6032不冒充纯unit | 同目录实际command/XML/log |
| b27同库可重复性 | 15:06:51–15:07:01及15:07:02–15:07:12，均北京时间，98/98各通过，无skip；保留原setup与epoch/跨盘失败 | 同目录recheck日志；root ga_combined_regression_fixed仅作者辅助 |
| 真实Linux worker/beat | 2026-10-15T14:59:00+08:00–15:00:40+08:00，2/2；PG隔离库/RedisDB10、双prefork竞争/重复、强杀后60s租约接管2attempt、broker断线outbox一个效果 | 独立run_linux_worker/test_linux_executor与资源适配收据 |
| Linux API重启/撤销/观测 | 独立4观察passed，真实共享PG/Redis/OpenSearch；MinIO配置实际装配；合成账号/任务明确fixture，不计外部来源live | 同目录Linux API原始收据 |
| MinIO | 新阶段7/7真实通过；此前SDK/对象重启及PG知识引用专项另有日志，不累计成独立总数 | 独立MinIO命令与旧专项 |
| 单源真实网关 | 2026-10-15T15:05:58+08:00–15:06:00+08:00，Windows显式DoH NVD HTTP200/3105bytes；不是持续采集或生产负载 | 新阶段gateway原始收据 |
| 前端/浏览器 | d391与当前b27前端不变，120unit/类型/lint通过；真实UI41交互归属7184，时间修复10交互归属d391+7184，不能跨版本拼新同版e2e | G-B-R04-live-ui-review-1.md与相应PNG/run；G-A认证专项另留档 |

每条命令cwd、完整参数、开始/结束/退出码、实际JUnit与配置/资源身份在reports/runs/recovery_ga_checkpoint_review_1_20261015/，本表不替代raw。正式评分/性能P50/P95/max、六小时观察、完整恢复、人工双标与云端CI执行均not_run，本阶段不声称这些已达标。新阶段自己的API/worker/beat/DB10均已结束/清空，非无限后台。

## 6. 合同与计划差异

CR-R01–CR-R09落实用户已批准建设目标，独立激活保留原任务全部最终验收。CR-R10兼容升级由已有完整批次授权覆盖，旧“待新授权”仅历史，不能继续当阻塞。PG/内容存储/任务/共享HTTP等细则均有实际CR；本次b27仅修测试可组合性，没有业务合同、金标、分母或门槛变更。R01部署/最小认证、R02持久、R03执行切片与后段增强分开，仍保留T06的R20增强等最终条件。

## 7. 评分和场景证据

E1/R2：固定锁与独立新WT、默认API/worker/beat、PG权威任务与日志；F1/P1：游标原子性与故障接管；F2：版本/证据/关系可追溯与隔离；U01：认证/撤销与可操作工作台基础。F3/A1、九维自动富化、推荐/更新重判、各协议插件、正式P指标与U02–U14仍按后续映射，不自评满分，不将旧accepted数当完成比例。

## 8. 阶段结论和下一步

当前是可供独立最终核对的候选：代码/自动检查与真实依赖组合已获得新非作者证据，文档归档固定复核尚未完成，阶段仍awaiting_review、尚未push。复核通过后主控才登记阶段accepted、显式检查秘密/远端与差异，按授权推本次codex分支并核对remote SHA。整T卡和后续live/人工缺口不自动变绿。

G-B继续真实来源→原文/PG/API/UI与生成/embedding/rerank→引用回答。GitHub匿名额度15:07:53重置前的403原始阻塞保留；模型31c两wire真实调用已发生4次、费用unknown，首轮逐字引文CRLF失败与第二提示版本成功分开，不能当正式准确率。embedding/rerank独立本地真实实现与来源任务前端已并行，人工金标和FOFA资产授权范围仍待外部输入。

## 9. 文档修订记录

2026-10-15T15:15:03+08:00–2026-10-15T15:15:03+08:00：/root为新独立阶段审查整理当前候选，保留首次创建时间与全部旧全文；更新1200组合、Linux真执行、3修复和11缺档归档证据，尚未自行accepted或push。

2026-10-15T15:21:37+08:00：/root按原命令argv更正单源公网GET为Windows；Linux只证明本机API/prefork/beat，未证明来源DNS恢复，业务代码/结果不变。
