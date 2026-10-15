# R04 · 真实PG知识只读API工作包

文档首次创建时间：2026-10-15T13:25:46+08:00
本次写作开始时间：2026-10-15T13:23:44+08:00
本次写作结束时间：2026-10-15T13:30:37+08:00
最后更新时间：2026-10-15T13:30:37+08:00
证据截止时间：2026-10-15T13:30:37+08:00
实现Agent：/root/r04_knowledge_api
独立审查Agent：主控后续派发新的非作者；本报告不是独立验收。
工作分支：codex/recovery-r04-knowledge-api
基线SHA：5c62e69773b45494c790aa15ac6ecb643825b157
已测冻结源码SHA：6e7c4c7aeea5f9d25deaa4b676b63dda65af477e
backend/src tree：729fe54126c7fcde9e5a35acab3d187b74b4272b
任务状态：awaiting_review；本工作包实现 complete，整张R04仍 partial。
unit/contract/integration/security：所列隔离范围 passed；Linux全unit failed（见问题台账）；frontend/e2e/live/manual：not_run。
提交/push：源码已本地提交；证据提交由后续交付消息给出；未push。

## 1. 范围与输入输出

读取AGENTS、执行地图、R04、T40/T41、03/05合同、来源持久化与只读投影CR、新Ponytail 5.2 full，按父Agent冻结接口实现。唯一产品输入是认证cookie及PG事实表，不提供fixture后备、外部URL读取或写业务接口。

默认应用新增GET `/v1/events`、`/v1/events/{UUID}`、`/v1/evidence/{UUID}`，以及相同的`/api/v1`别名。DTO完全复用`api/knowledge_contracts.py`，逐字段/枚举与`frontend/src/api/knowledge-contracts.ts`核对，未修改前端。认证身份来自`SESSION_COOKIE_NAME`和`AuthenticationSessionService.build_access_scope`，每次请求重验，客户端无法通过tenant参数切换身份。

列表默认20、最大100。排序键是(first_seen_at,event_id)降序；有界base64url游标包含排序键及全部过滤条件的SHA256，变更条件复用旧游标422。游标不作为授权；可修改排序位置不会绕过每次SQL范围过滤，不需要新增签名密钥。q按标题/保存外部ID字面不区分大小写匹配；product只查询当前关联、当前修订、current的`affected_product`来源文字主张，拒绝用标题猜产品；risk_type精确匹配。updated_after匹配实际保存的first_seen_at、可见关联修订ingested_at/created_at或关联associated_at，不把源未知时间替换成任何这些时点。

## 2. 修改与复用

源码/测试共5个文件：`api/app.py`仅4行挂载；新增`api/knowledge_routes.py`、`api/knowledge_read_service.py`、`tests/unit/test_r04_knowledge_api_cursor.py`、`tests/integration/test_r04_knowledge_api_pg.py`。未改schema、迁移、DTO、settings、认证实现、锁文件、原金标、阈值、分母或progress。

复用FastAPI、SQLAlchemy、现有认证与problem响应、领域枚举及保存的知识表。现有sources没有共享映射，按主控确认仅用`sqlalchemy.table/column`声明3个只读查询字段；没有再造ORM事实模型。新增服务确有必要：此前默认app没有知识端点，冻结DTO没有任何PG读取调用方；SQL连接公共/私有来源、修订与证据，并生成严格投影。无新依赖、通用CRUD框架或伪数据服务。

同一请求用REPEATABLE READ快照读取；连接池/SQL超时由已有engine配置控制。列表摘要对本页事件批量查询外部ID与关联修订，不对每行发一次查询。详情批量读取主张、证据及逐维引用；维度来源范围查询只涉及该事件已保存source_scope，不全表扫描所有来源。

public要求READ_PUBLIC；tenant只有同租户且READ_ASSET才可读取。system_admin无tenant不能通读私有记录。每层revision、document、source、claim、evidence都重新过滤。跨租户与不存在统一404；缺读权限403；缺失/无效cookie401；数据库或已保存投影损坏503固定problem，不回显底层异常、SQL或输入，不返回200空列表。

source_count按可见有效关联去重source_id，不按文档数计；primary_product_ids未有明确实体关联，保持空；freshness摘要保持unknown。版本按已保存created_at、revision_number和ID稳定排序，历史修订保留；旧claim仅返回与其source_revision_id一致的证据，不能借新修订定位。旧日期NULL和legacy_unverified保持。逐维只显示已保存结果，缺维度为空；失败状态及错误码原样区分，事件版本或引用修订失效的已有维度标stale，不把历史值覆盖成当前值。

引文读取重新校验UTF-8 SHA256及非零block的全文Unicode坐标；验证坐标越界、哈希损坏、block属于其他revision都503。旧无验证记录返回legacy_unverified、verified_at=null；展示hash可计算，但不由此宣称来源或语义支持验证。原文URI不猜来源根地址；旧URI带userinfo、敏感query或fragment时不向前端返回。

## 3. 调用链及索引

修改前索引`dianzi-r04-api-5c62`：825 nodes/3642 edges；读取architecture/schema，trace build_access_scope，再以源码/rg核对。第一次get_graph_schema遗漏project参数失败，补参数成功，错误没有当分析结果使用。

冻结索引`dianzi-r04-api-6e7c`：856 nodes/3870 edges，范围仅此WT的backend/src，缓存`/tmp/dianzi-cbm-r04-api-20261015`在仓外，未包含secret/holdout。trace显示`create_application → build_knowledge_router → GET events/detail/evidence`；源码实际挂载两种前缀。进一步链路是cookie → PG认证上下文 → SQLAlchemy Session → ACL过滤的PG表查询 → 严格DTO。图边不是业务正确证明，下面真实PG测试交叉核实。

## 4. 实际验证

原始日志统一位于`reports/runs/recovery_r04_knowledge_api_20261015/`，每个正式命令的cwd、完整argv、+08起止时间、退出码和代码SHA在相应receipt.json；XML给出数量。runner统一字符串`source_tree=working tree, not frozen`是保守模板标签：frozen命令的源码SHA确为6e7c4c7，源码/测试没有未提交差异，不能理解为审查了正在修改的代码。

| 检查 | 实际时段(+08) | 结果 | 日志/收据 |
|---|---|---|---|
| Windows锁包纯unit，`python -m pytest tests/unit -q --cov-report=json:... --junitxml=...` | 13:22:20–13:22:45 | exit0，329/329，0失败/skip；2602/4286 statements，原始60.70928604759683%，原60门槛未改 | unit_frozen.log/xml/coverage.json/receipt.json |
| 隔离真实PG三GET与负例，`python -m pytest tests/integration/test_r04_knowledge_api_pg.py --no-cov -q --junitxml=...` | 13:22:10–13:22:46 | exit0，24/24，0失败/skip | integration_frozen.log/xml/receipt.json |
| Windows mypy 66源码文件 | 13:22:46–13:22:46 | exit0 | mypy_frozen.log/receipt.json |
| 5相关文件Ruff与format --check | 13:23:44–13:23:44 | 两命令exit0 | ruff_frozen、format_frozen日志/收据 |
| 全后端src/tests Ruff与format --check | 13:27:10–13:27:10 | 两命令exit0，146文件格式无变更 | ruff_all_frozen、format_all_frozen日志/收据 |
| 新增游标/URI unit | 首轮命令起止历史未单独记录；pytest实际0.55s | 24/24；随后已包含冻结329纯unit重跑 | unit_first.log/xml |
| Linux全纯unit与原T02门 | 13:17:27–13:18:00 | exit1，328通过/1失败/0skip；raw coverage60.709%，是mypy恢复测试失败而非覆盖率通过整门 | unit_all_first.log/xml/coverage.json/receipt.json |

PG资源由已授权WSLroot私密connection文件读取DSN，仅内存/child env使用；专用数据库`test_dianzi_r04_api_20261015`，每例新建`test_r04_api_<uuid>` schema并仅清理自己的schema。没有迁移/清理生产、开发或其他审查库。默认app仅测试engine工厂注入为真实隔离PG engine，认证/会话本身使用真实PG目录和状态；业务SQL及DTO没有mock。数据显式synthetic/fixture、测试settings data_mode=fixture，不计真实来源live。

24个PG案例覆盖：正常列表/无CVE公告/详情/证据；等时戳分页/中途新增不重复；文字过滤%_及SQL注入形状；游标绑定过滤；产品只用当前来源主张；旧/新修订与source去重；实际入库更新时间；tenant A/B、system_admin无tenant、viewer、公共event下私有source/revision；旧日期/定位；缺失/无效认证3端点；边界422；非法UUID；数据库异常503；缺权限403；失败与available维度；event_version变化stale；私有维度/子引文；旧claim不能采用新证据；hash/span/block损坏3负例。

Starlette TestClient对httpx有一条弃用warning，如实保留；未为消warning新增依赖。无新性能/并发/浏览器/live/人工指标。SQL快照一致性未做并发变更压力测试，正式浏览器与来源→PG→UI由root集成后验证。所有模型/测绘调用次数0。

## 5. 问题台账

| 问题 | 触发/实际/根因 | 影响/修复/状态 |
|---|---|---|
| API-TEST-01 | 测试调用不存在precreate_user，15失败3通过；现有正确方法create_precreated_user | 测试准备错误，改正确调用，不改产品认证；integration_second再跑17通过1失败；冻结24全通过，已修复 |
| API-TEST-02 | 多个synthetic来源统一name='fixture vendor'，name唯一约束导致ON CONFLICT忽略第二来源，文档FK失败 | 测试来源名改唯一稳定source_id，保留故障日志；integration_third 18/18、冻结24/24，已修复 |
| API-RUN-01 | WSL git读取Windows worktree .git路径失败，测试执行后receipt脚本退出1 | 调Windows git.exe并转换-C路径；保留首次unit/PG/mypy日志，首次命令时段未完整记录，不补造；后续收据正常，已修复 |
| API-LINUX-01 | 纯unit原T02要求mypy正确恢复，但当前baseline pdf_text.py直接subprocess.CREATE_NO_WINDOW，Linux stubs没有该属性 | root负责共享平台修复，API包禁止改PDF文件；Windows整门通过，Linux整门仍failed，未解决/跨包依赖；无skip/ignore/删测试 |
| API-ENV-01 | 尝试旧Windows review venv缺少已锁pypdf/dnspython，mypy8条import缺失 | 创建本WT .venv，uv sync --locked实际68包，完整mypy66通过；未修改共享环境，已修复 |
| API-SCAN-01 | 首次扫描错误地把完整DSN的每个8字符片段都当秘密，命中测试库名/协议等正常公共文本 | 保留private_test_secret_scan_1_false_positive.json；正确规则仍扫描DSN全文、密码全文及密码全部8字符片段，61文件0命中；没有隐去真实秘密命中 |
| API-RUN-02 | PowerShell内联Python核对资源的引号未转义正确，shell解析count(*)报错，未连接数据库 | 改独立resource_release.py，不串另一shell构造文件删除；仅统计自己隔离库，原终端失败是证据脚本错误，不算业务失败 |

初轮Ruff未格式化/unused/type错误日志保留；只修本包类型和格式。安全回归在冻结版本真实PG复跑，不把输入fixture当外部接口已实测。

## 6. 合同差异、证据与限制

没有新增范围/评分/盲测差异。按父Agent2026-10-15本轮确认实现来源三字段只读表达式、产品来源主张匹配及实际保存更新时间；外部 DTO 结构未改。既有approved CR-R04来源持久化0013与只读API v2投影是本包前置。原T40/T41、R04全部剩余映射不因这一工作包验收而减少。

F1/D2/R1相关证据仅为API可读取保存的PG事件、来源修订、未知时间和永久证据定位；F2仅真实保存的逐维状态/引用展示，不证明九维live已全部接通。没有对官方评分自评满分。

明确剩余：新独立review；root集成来源写入/worker及真实两源PG dataset；真实浏览器登录到列表→详情→原文证据；R05真实模型引用回答；Linux PDF类型修复后全unit复跑；持续采集/性能/正式人工金标仍不属于本包证明。API本身不返回临时demo、资产推断或未执行成功。

## 7. 交付与资源

所有自建Session/engine在测试退出关闭，24例schema清理；测试DB和WSLroot0600 connection文件留给后续review，不运行后台进程，无新容器/端口/queue，当前仅root可读取的测试资源。本包未push、未更新accepted/progress。

源码staged diff check为0；证据staged diff check为2，只有保留的失败pytest traceback/XML空白分隔行trailing whitespace，不为使审计绿灯删除或改写原日志。evidence_index同时提供捕获文件sha256和Git index blob SHA256：本机既有core.autocrlf会归一部分文本行尾，审查commit内容应核对git_blob_sha256，核对当前原始捕获文件应核对sha256；两者语义明确，未修改全局.gitattributes。

独立复跑入口：Windows在此WT的backend运行`.venv/Scripts/python.exe -m pytest tests/unit`与`.venv/Scripts/mypy.exe src/ai_intel`；PG通过本报告run_checks.py integration_*从私密test connection取得env后执行冻结pytest命令。首次建立资源只能用integration_first名称，已有资源用integration_review等新名称，不覆盖旧日志。

修订记录：2026-10-15T13:25:46+08:00，作者首次落盘源码冻结、自检与失败历史；后续独立审查结论由新reviewer写独立报告，作者不自签。


修订记录：2026-10-15T13:27:51+08:00，补全冻结后的全146文件静态检查、扫描误报与资源脚本故障记录，首次创建时间保留。


修订记录：2026-10-15T13:30:37+08:00，补充主控交接：API源码6e7c4c7已集成为d8f9248，独立review将审集成候选；主控另在4934de3修复Linux PDF类型平台问题。本报告保留原Linux失败，不套用主控后续396项结果作为本包冻结329项或API验收证明。证据索引每项并列captured_sha256/captured_size_bytes与git_blob_sha256/git_blob_size_bytes，遵照主控要求保留捕获字节、旧失败与全局属性。
