# R06 · 固定公开来源自动轮询

文档首次创建时间：2026-10-15T21:46:59+08:00
本次写作开始时间：2026-10-15T22:19:22+08:00
本次写作结束时间：2026-10-15T22:19:22+08:00
最后更新时间：2026-10-15T22:19:22+08:00
任务切片awaiting_review、implementation complete；整R06/G-C in_progress/partial。作者/root；分支codex/r06-source-polling；基线52433474f66a900c56ee6d5478337b0ec83d6eda；代码冻结93c458a0f97b65198d1fb690d42634b77342bb3c，独立r06_periodic_collection_independent_review正在审此SHA，不自签accepted、未push。代码编写实际起止未单独记录，不拿文件mtime代替；测试时段如下。

## 行为与范围

可信SOURCE_POLLING_ENABLED默认false、compose显式透传。开启后beat60秒→poll_due→单个PG事务→九固定来源live root jobs/outbox→既有dispatcher/worker。vLLM30分钟，余60分钟，每轮最多5页；参数不来自网页/任意URL/租户。关闭配置后任务直接返回disabled且不连PG，已排队任务/原文/历史保留。

仅新增source_polling.py，复用既有SourcePageRequest/enqueue_source_page、来源注册、source_cursor和job_runs/payload/outbox；没有新增调度表、迁移、依赖或内存业务真相。UTC桶固定window_end/key；重复tick/多进程/重启不增加同桶root jobs；包含continuation的该源active工作先续接，>500active或非法/超4096byte source payload明确报错不继续放大队列。公开来源系统管理员权限先于DB访问检查，普通租户不能调用。调度事务回滚无半成品，实际外网IO仍只由已有worker网关执行。

变更8文件494行：source_polling.py141、settings1、runtime33、compose1、直接unit84/PG206、CR-R06_periodic_collection与source_polling运行手册；测试为重启/并发/回滚/队列与停用必需，未建通用调度框架。合同只落实已批准R06:T49/T54持续采集，不改变官方门槛、金标、分母或原T整卡条件。

## 实际验证

命令cwd D:/wt/r06-source-polling/backend；完整argv/精确秒级起止/exit见各frozen.json。pure原60覆盖门保持；PG显式test_dianzi_r06_catalog_polling_20261015和独立UUID schema，未运行降级或硬编码开发库。当前作者未单独保存public前后snapshot，独立review要求补核对；不以fixture模式计来源live。

| 项 | 开始 / 结束（+08） | exit |
|---|---|---|
| tests/unit | 2026-10-15T21:38:56+08:00 / 2026-10-15T21:40:12+08:00 | 0 |
| tests/integration/test_r06_source_polling_pg.py | 2026-10-15T21:39:24+08:00 / 2026-10-15T21:39:37+08:00 | 0 |
| check | 2026-10-15T21:39:38+08:00 / 2026-10-15T21:39:39+08:00 | 0 |
| src | 2026-10-15T21:39:37+08:00 / 2026-10-15T21:39:38+08:00 | 0 |

冻结pure1777passed/10real_pg deselected/0fail/0skip，覆盖74.15%；PG10passed/0skip（真实PG、显式fixture source），含3并发、实际另进程restart、事务回滚、501active上限、非法/超大payload、旧OSV worker实际PG执行。Ruff、mypy93通过；格式检查前使用既有Ruff formatter，产品diff没有范围外文件。focused19passed由本批17与旧worker2组成，不相加为整卡分母。最早测试ModuleNotFoundError exit2保留polling_initial_red；首轮lint格式/长行错误为作者工具输出，未单独保存完整lint初始日志，最终check0可复验。environment_sync实际退出码未单独封存，uv日志与成功运行自己的venv保留，不编造exit0。

CBM官方0.11索引src-only，基线524图1233nodes/6137edges，冻结93图与schema/trace原输出在cbm_*_frozen.log；缓存/tmp/dianzi-cbm-r06-source-polling-20261015在仓外。图确认runtime.poll_due_public_sources→enqueue_due_source_collections→原source enqueue/outbox；另rg查配置/入口/全部callers。没有edge不当无调用，实际beat注册由unit、PG由integration交叉核查；未启动真实broker/beat/source，live/frontend/e2e/manual未运行。

## 限制与问题

采集间隔只是策略，不证明≤6小时/漏采率；限额与失败仍由真实日志判定。固定source目录不是九个官方类别或九条业务通道；CNNVD/自有webhook/EPSS/KEV另补，不被此poller替代。当前新7源依赖另审两Must：CAC最后条文缺失仍full_text，OSV非法或超精度时间被当精确UTC；主控在独立source-boundaries-fix修复，未关闭前不做九源live或跨阶段验收。本切片自检不能背书那些解析语义，资料读取UI的先前独立Ship也不能背书自动采集。

下一步全新reviewer核对93与本材料→修复/定向复核→与source边界修复和独立Ship来源管理UI合入→实际有界beat/worker/API/浏览器九源验证。整阶段另需新reviewer。没有新费用，模型/测绘调用0。独立结论、合并后regression与真实持续观察仍待取得。

## 独立审查与材料更正 · 2026-10-15T22:19:22+08:00

全新独立reviewer r06_periodic_collection_independent_review 已在固定93c458a出具限定Ship：[报告](../reviews/recovery/G-C-R06-source-polling-review-1.md)，SHA256 1f1b31d2af6898bf41101f69e31f5094dd9c6a4ee52767922b0077a9cfdfe07e。其17unit/10PG/24新增边界/4runtime错误检查、4实际进程并发/重启/kill事务回滚、真实原60秒beat→隔离Redis→默认runtime→PG→显式空OSV fixture worker与disabled重启65秒均通过。公开来源live仍not_run；本段不改变前述作者原验证范围。reviewer自有离线冻结venv1777/74.15%原60门通过，首轮共享venv双代码路径覆盖52.19%exit1保留，未改门槛。

原作者frozen.json的working_tree是静态模板文字，实际每份head已为93c458a且对应产品树冻结；不改写原日志。21:46:59初稿后有文字更正，其实际时刻未单独保存，不能以mtime补写；本次明确记录材料更正。write_polling_report.py保留初版生成器，不能直接重跑覆盖本报告；它不是最终行为规范。500是本轮入场拒绝阈值，单源500active时其他8源可使本轮达到508，下一tick拒绝，并非严格最终cap500。

原reviewer清单82成员包括1个pyc；主控校验全部hash后只归档81个规范成员，pyc不纳Git，原不可变清单与独立transfer receipt并存。一次reviewer缓存清理被自动审批以blocked by policy拒绝，已保留并排除工具缓存，未重试删除，无需用户操作。整R06/G-C仍partial；source边界Must尚在独立复核，不能据此启动正式九源验收。未新增业务/配置/测试改动。
