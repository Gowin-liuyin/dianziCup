# R12 · 生产混合检索前向迁移切片

文档首次创建时间：2026-10-16T07:12:24+08:00
本次写作开始/结束时间：2026-10-16T07:12:24+08:00 / 2026-10-16T07:12:25+08:00
最后更新时间与证据截止时间：2026-10-16T07:12:25+08:00
主控实现：/root；分支codex/r12-runtime-integration；已测代码ed0e14a03a06ed104f23afd0be5407d873ed8edf。
状态awaiting_review；本切片实现complete，整R12/T30/T35仍partial。integration/security passed限以下实际输入；unit/contract相关fixture143 passed；frontend/e2e/model-generation/live-source/manual not_run。真实本地E5/rerank仅原C02合成三文档，未计正式题集。新非作者独立review尚未进行。无push、无阶段通过。

## 1. 输入输出与复用

normal forward0019→0020得到四张与既有indexer列/PK/check/vector384一致的可重建表，并用六个事实身份外键及两处outbox外键阻止孤儿投影。旧R05向量、事实、游标、资产及任务不改。复用已审R12 indexer/retriever/OpenSearch REST/E5、SQLAlchemy/Alembic/pgvector和全部原T30函数断言；只需新增生产DDL及隔离生产回归adapter，无新dependency、微服务或平行问答框架。

## 2. 修改与真实问题

文件：0020_hybrid_retrieval.py、test_r12_production_schema.py、test_r12_production_indexing.py、CR-R12_production_hybrid_migration.md。初始head0019缺四表是源码事实；最初名为migration_missing_red的执行实际为fixture ScopeMismatch 1error，不能包装成缺表业务红。第二次7errors同根；将本地fixture改function scope后真实7PG通过。

首次完整生产测试10failed/20passed：测试迁移search_path错误含public，Alembic看到自有数据库public既有version便跳过新schema，使不同测试读入旧public派生行。根因在新fixture/historical proof，不是已审HybridIndexer。修为migration search_path仅精确自身schema，runtime再加public，同时显式检查四表真实位于自身schema。0020沿用0014的transaction-local public vector type路径，独立0019→0020也可解析vector。没有改任何原T30输入或断言、没有清空public旧失败数据或更换分母。新30项通过与源冻结后30项通过，旧10红/1与7error原log/XML保留。

## 3. 实际验证

逐命令真实cwd/argv/+08起止/退出/HEAD见本run同名JSON，所有数量由XML提取test_results.json；绝不累计迭代重复用例。frozen_production：30passed/0fail/error/skip，2026-10-16T07:07:11.270744+08:00→2026-10-16T07:08:10.121100+08:00。其中8个DDL/history实例+原22个T30参数化行为；真实隔离PG25432/OpenSearch29200、query权限/撤回/失败水位/并发replay/模型空间边界在真实forward0020运行，不用产品create_all。MetaData.create_all在两adapter显式禁止；history比较所有0019旧表逐原row JSON/count，raw源码identity源proof分列LF。

related_fixture：143passed；其原R12/R05测试未改，命令HEAD b502源码与当前相关业务相同，仅根新增迁移/adapter，不冒称该旧命令运行于ed0。mypy130源文件通过；Ruff/format通过四owned文件。第一次lint5长行已保留并分割同义字符串修复，无ignore。初期直接命令没有逐条起止时记录，未补造；当前checks.py命令完整capture。首CBM索引在业务修改前真实成功，原终端工具记录；封存新CBM项目dianzi-r12-runtime-production-20261016，1639nodes/8621edges、四项parse缺漏0，排除assets/cache不等于审过assets。architecture/schema/refresh_scope入出/迁移caller全部exit0。

## 4. 真实接线与限制

源码rg/CBM显示当前API/worker还没有HybridIndexer.refresh_scope业务caller；有定义/测试调用不算产品接通。root继续默认语义service、knowledge-change worker/outbox、catalog epoch reconciliation与多轮问答接线；并行已委派conversation内部PG和Neo4j实现。没有本批browser、Celeryprocess、生成模型回答、正式召回/准确率、P50/P95或完整QA耗时，不用本地E5单例替代这些门。图/四态/历史/人工金标仍是各自前置缺口，不删范围。

## 5. 安全、资源与回滚

只用test_dianzi_r12_runtime_20261016与每例精确test_r12_production/history UUID schema、dianzi_test_r12_随机index；cleanup仅这些schema/index，不触碰source正在采集库/Redis15/其它index/用户文件。失败public残留仅本自有testDB保留，不当事实。连接从已授权测试资源内存读取，因并行WSL读超时改用rootWindows DPAPI测试reference；不读取产品vault、不打印/入argv秘密。共享pytest failure hook＋写前实值脱敏、最终实值扫描65文件0匹配；缓存/pyc不归档。

没有破坏性downgrade/外部来源/生成或付费provider调用；测试OS只自有索引。复用现有权重无新下载；费用unknown仅资源整体成本，未虚构报价。回滚/兼容与任务影响在CR；优先停新消费者/保留派生与事实历史，不自动回退生产库。

## 6. 结论与下一步

本切片等待新的独立非作者reviewer复跑冻结代码/原断言/历史升级/安全失败，核材料后才可限定Ship；主控不自签accepted。阶段G-C/G-D未过门，没有本阶段push，远端仍此前G-B收据。继续0021/22生产DDL、R07/R11/R17已审切片集成与实际worker/API/UI联测，完整目标不因单卡报告而停止。

2026-10-16T07:21:11+08:00 修订：第一次材料check因两条原raw CRLF回执失败并阻断commit，原material_check.log保留；仅该run owned_database.json及synthetic_source_blobs/raw_manifest.jsonl加cr-at-eol归档规则，不裁字节/不改全局检查。initial manifest保留68项历史原hash；最终manifest追加这一修订与归档工具/失败log。
