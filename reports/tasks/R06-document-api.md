# R06 · 公开资料历史与证据只读API

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T20:23:14+08:00
主控作者/root；状态awaiting_review；实现complete仅本资料GET切片，整R06/R09/R17仍partial。
代码冻结49ee33f6a95099be619a59ff47c621713a089137；基线71e852ce4be147d30aa1bc824bf18afda99fb332；WT D:/wt/r06-product-wiring。

## 用户行为、输入输出与复用

真实认证Cookie → PG同事务复鉴权/公开来源、资料、修订过滤 → 文档列表、所选固定历史修订、原始日期精度、来源许可元数据及可验证证据分页 → /v1与/api/v1同一GET。新增接口无模型调用、任意抓取或私有资产导出；论文/政策不被转换为漏洞。JSON字段按CR-R04-R06_document_read_api和document_contracts冻结，前端已独立按此合同实现。

复用FastAPI/现有PG认证锁、SQLAlchemy、原KnowledgeReadService逐条证据hash/Unicode坐标校验和problem错误，无新增生产依赖、第二事实库或CRUD框架。新增read_service/router是资料独立于事件所需的投影；共享_evidence_rows仅增加默认不启用的有界分页/公开过滤参数，原事件/问答调用语义保留。实际CBM旧71索引及49刷新仅backend/src，不含秘密/holdout；调用链是create_application→build_document_router→同事务lock_authenticated_scope→DocumentReadService→PG三层public JOIN→KnowledgeReadService原证据投影→DTO。

## 安全、历史与失败

READ_PUBLIC只来自认证用户；即便同租户管理员拥有READ_ASSET，本资料列表/详情/历史/证据都不混私有。每次GET重新锁定真实会话与用户，初始鉴权后撤销会被第二道锁拒绝401。分页cursor严格base64、重复JSON键拒绝、绑定q/kind/category，固定入库时间+ID排序；非法422，依赖/证据完整性损坏503，不返回伪成功空列表。外文/HTML原文作为JSON text，未约定metadata字段不导出。

历史从revision.source_metadata读标题，老记录缺历史标题明确“历史标题未记录”，不套当前标题；无元数据覆盖unknown/许可null/日期unknown，不补造UTC。页固定revision_id避免拼新旧正文。source_published/source_modified/observed/ingested分开；calendar_date保留raw且无精确UTC。没有公开正文时明确notes，不称安全。资料证据最大2000、页面100，列表100/历史offset100000为既定合同边界；超过或损坏503。任意metadata URL不会触发访问。

## 实际验证与问题

命令cwd/真实秒级Asia/Shanghai起止、argv/exit、SHA、JUnit见reports/runs/recovery_r06_product_wiring_20261015/。本报告不把重复套件相加，也不把合成源输入当来源live。

- document_cursor_red：新接口不存在时exit2 ModuleNotFoundError，先定义9回归后实现；随后cursor9pass/exit0。
- document_pg_initial：17真实独立PG/API pass；补充历史未知/任意metadata/外文文本和跨文档版本负例后document_pg_v1为20pass/exit0、19.04秒；document_pg_frozen49再次针对固定版本复跑，结果见收据，写作时若未完不提前计绿。每例在专库test_dianzi_r06_catalog_documents_api_20261015的唯一UUID schema，显式fixture data_mode；没有变动采集库r04或公共用户数据。
- 纯unit/contract/security原门：document_pure_v1为1687pass/10 real_pg deselected，但复用其他WT editable解释器导致coverage同时扫描另一套未执行源码，52.58%/exit1；不降60门。为当前WT uv sync --frozen --extra semantic建独立环境、相同命令重跑document_pure_own_venv：1687pass/10deselected/0skip、74.74%、exit0、82.38秒。原红保留。uv安装起止未独立落盘，tool真实输出9.95秒，无推测写作时间。
- Ruff首轮4长行、后来单个SIM117红，已格式化/合并with修正，document_ruff_v2 exit0；mypy91 source files exit0。PG冻结后只有test with同义风格变动，不改预期/断言。所有代码diff--check exit0。

覆盖unit/contract/security纯门及20真实PG/API；frontend/e2e/live/manual未由此批执行。独立审查尚未委派/未签Ship；此前A/B parser单独Ship不替代此批。

## 兼容、迁移、回滚与边界

见已有CR-R04资料只读合同。此批不新增迁移/锁/依赖；要求已迁移0015。旧events/evidence/questions及双前缀保留。关闭新增资料导航/路由可停止功能，保留PG历史，不downgrade/删文档。新7来源worker仍待接线，当前PG测试是合成公开原文不是live；真实浏览器必须后续接同后端验证。九维/图谱/资产/推荐/完整工作台及正式评分未因此通过。

下一步：全新非作者固定49审查并复跑负例；资料前端第三权限竞态修复后由原reviewer复核；统一worker新源→实际来源/原文/PG/API/浏览器。无新增付费调用，人工金标/FOFA授权范围仍待用户输入，但不阻塞本GET实现。没有push/accepted。
修订 2026-10-15T20:25:37+08:00 /root：固定49ee33的document_pg_frozen49为20 passed、exit0、15.58秒。初次元数据归档db33因Git换行转换造成45个manifest成员中的31个Git blob与原始文件hash不等；a578仅为本run添加-text与cr-at-eol属性并显式renormalize，原始45文件未修改，Git blob/原始manifest全45匹配，未屏蔽scanner/测试/其他目录或实际行尾空格。产品代码仍49ee33，资料GET完整live浏览器尚未执行。
