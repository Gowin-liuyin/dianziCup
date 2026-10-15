"""Write an evidence-based report with actual creation time and test layer counts."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
run = Path(__file__).parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
sha = subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
assert sha=="164fc8eae1fdc5a108cbbc1950e7abd40f0eb3ef"
coverage = json.loads((run/"pure_unit_export.coverage.json").read_bytes())["totals"]
body = f"""# R04 · 固定来源响应的原文、事件与证据持久化切片

文档首次创建/本次写作开始时间：{started}
本次写作结束/最后更新时间/证据截止时间：__END__
实现 Agent：/root/r04_vendor_source；集成主控：/root。
状态：awaiting_review；本接口实现 complete，R04/T05/T09/T10/T12/T17 整卡仍 partial。
最早已记录本包基线核对：2026-10-15T13:09:57+08:00；代码准确编写起止和时长历史未记录，不以测试窗口代替。
分支：codex/recovery-r04-source-documents。
初始基线：2ff2f999b3824252d54b93af6d1da78ecb6f1427。
依赖更新：按主控明确指派 cherry-pick 6c7fd7a4a01107acbbfbd90fc7ad62136b0da71b 为本工作树 5ea0d34；仅集成主控公共补丁，不由本 Agent 改公共代码。
冻结/已测源码：{sha}，tree fe6f877b4a9b49d1d8dd7ced2d82b8809f5038f4。
主控集成源码：df214c664847f8a2c721579955108da47a55c9a6（主控已核实交付并另行做实际秘密扫描）。
独立审查：待新的非作者 reviewer；本 Agent 不签 accepted。没有阶段 gate/push 声明。
unit passed；contract passed（明确 isolated fixture）；integration passed（本包真实隔离 PG+filesystem）；security passed（本包权限/输入/事务针对性负例，不能代替整系统安全）；frontend/e2e/live/manual not_run。

## 1. 用户问题与范围

把真实公开源的留档响应接入共享 PG 原文版本、事件、事实和永久证据，解决解析函数仅被测试调用、原文被重新序列化、HTTP envelope 时间制造假变化、重复发布、未知时间被猜测、半页成功等问题。对应 G-B/R04 的 F1/F2/D2/R1 证据切片，原任务最终验收仍完整保留。已读取 AGENTS、执行地图、R04/T05/T09/T10/T17、03/04/05合同、CR-R04-R04_source_persistence 与当前状态/交接；使用 Ponytail 5.2 full。

文件所有权仅 source_documents.py、直接 unit/integration 测试、此报告与 reports/runs/recovery_r04_source_documents_20261015/**；未修改 API、worker/runtime、schema/迁移、DTO、依赖锁、配置、progress、阈值、金标或盲测。上述共享依赖更新由主控编写并授权集成，不能归为本 Agent 实现。

## 2. 冻结接口与真正行为

- SourceResponse(source_kind: Literal['nvd_ollama','vllm_vendor'],body:bytes,request_url:str,observed_at:datetime)。请求只允许固定 endpoint 与完整白名单 query：NVD keywordSearch=ollama/resultsPerPage=1..100/startIndex≥0；vendor per_page=1..100/state=published/page≥1。query顺序可变，重复、未知字段、凭据、非授权 origin/path、用户信息、片段、控制字符与超容量拒绝。不是任意 URL 工具，函数不发 HTTP。
- SavedSourceResponse(source_id,revision_ids,event_ids,response_content_hash,new_revision_count)。revision_ids 严格原始 records 顺序，一条记录对应一份修订身份（复用也占位置）；event_ids 按首次出现去重，来源别名解析后可能多个 revision 共用 event，不能和 records 按位置 zip。
- persist_source_response(session,store,access_scope,response,*,ingested_at)：不 commit、不关闭 session，整体保存点包住来源/原文/修订/事件/claim/epoch/outbox/fetch；任何成员或 IO 失败整页回滚，不跳过或伪造 partial 成功。外层 caller rollback 经真实 PG 验证能撤销本页所有引用。对象写入先于 PG 事务时可能留下孤儿，不清理其他引用；共享安全 GC 负责孤儿。
- ensure_source_registration(session,access_scope,source_kind,created_at)->str：主控明确批准此最小公共增补，以便 source_jobs 在领取游标前登记来源。仅 public system_admin/tenant_id=None 且 MANAGE_PUBLIC_SOURCES/READ_PUBLIC；固定名字/类别/origin/public范围核对，旧行不覆写。调用方拥有 commit。
- SOURCE_DEFINITIONS：nvd_ollama UUID5(NAMESPACE_URL,'dianzi:source:nvd-ollama')，name='NVD Ollama keyword window'，category='structured_vulnerability'，base_origin='https://services.nvd.nist.gov'；vllm_vendor UUID5(NAMESPACE_URL,'dianzi:source:vllm-vendor')，name='vLLM repository security advisories'，category='vendor_advisory'，base_origin='https://api.github.com'。

JSON2 先严格验证完整页（UTF-8/NUL/重复键/非有限数/深度/叶数），响应最多 5MiB、单页最多100且不超请求数。随后仅用标准库 JSONDecoder.raw_decode 在两种固定结构中定位成员字符区间，重新编码同一 UTF-8 子串保留原字节；没有 json.dumps 冒充原文，没有通用 JSON 框架。

完整响应通过 register_response_content 的同 hash 事务锁/存储校验/PG登记，response_content_hash/source_response_hash 外键保留原文。成员稳定 document UUID按source+record生成，save_document_revision 比较末版；同成员 hash复用，A→B→A三版本，envelope.timestamp 改变仅新增完整响应和 fetch观察。0013 metadata/text_blocks保存来源日期/URI/parser/normalizer/page/json_pointer；相同末版不重写其日期与首次观察。NVD 无时区时间为业务 NULL，原值留完整原文。

复用 EventRepository/KnowledgeRepository/DimensionRepository/add_text_block/attach_evidence_span 的权限、证据、事务发布与 outbox。没有第二事实库或万能 CRUD。候选 event UUID按source+record生成，现有公开 CVE/GHSA 映射可解析为已有事件，Saved 返回真正 event_documents ID；无 CVE GHSA正常建立，后补 CVE保留身份；两个已映射事件冲突明确失败整页。

仅 source_excerpt（原文最多2000 code point）、vendor 包名的 affected_product、已知机构的 CVSS 等直接字段形成 supported事实；未从 NVD keywordSearch推断产品，没有漏洞适用/安全判断。CVSS分数、机构、向量分别提供真实字段位置证据，None机构不捏造，其他已知机构不丢；同一CVSS版本的实质score/vector差异为 conflict，不同CVSS版本不误当冲突。其他八维尚未取得不填在线结果；NVD无法形成已知机构CVSS时 pending。维度遵守既有100 claim/reference上限，超合同仍明确失败而非截断来源事实。

原修订/事实/证据保留；只将同文档先前修订的当前标记转为非当前，并保留旧 event_documents 历史。源级 source_status（NVD原文）与非空 source_withdrawn_at（vendor 原文时间）是 source_explicit事实和原位置证据，不改变共享 events active/merged 状态机、不发布“仍有效/安全”推断。主控已明确批准该兼容解释；R16负责旧新结果重判、撤回传播和重新激活，完整T10/T12仍未验收。

## 3. 真实测试与证据层级

各命令的完整参数、cwd、+08:00开始/结束/时长/退出码在 run/*.receipt.json，stdout/JUnit/coverage与失败均保留。次数不能相加作为产品完成度。

| 检查 | 实际时间 | 结果 | 证据 |
|---|---|---|---|
| 先写测试 | 13:15:52–13:15:54 | exit2，缺新模块 collection error，预期红灯 | unit_red |
| 第一 unit | 13:18:24–13:18:26 | exit1，44pass/1fail/2errors：重复ID用错page容量；巨大参数名超Windows环境上限 | unit_first.log.gz/xml.gz 与 large_log_archive.json |
| 修正 unit设置 | 13:22:47–13:22:49 | exit0，46pass；无case删除 | unit_second |
| 第一真实PG | 13:26:18–13:26:42 | exit1，18pass/1fail；测试机构UUID期望写错，原文与库一致 | pg_first |
| 第二真实PG | 13:28:49–13:29:12 | exit0，19pass，秘密匹配[] | pg_second |
| 加多机构/版本回归 | 13:31:08–13:31:39 | exit0，38 mixed pass（22本包PG+2共享GC PG+14纯计算） | pg_final |
| 导出/证据/来源状态终轮 | 13:37:52–13:38:26 | exit0，41 mixed pass（25本包真实PG+2共享GC PG+14纯计算），0fail/skip，秘密匹配[] | pg_export |
| 纯unit终轮 | 13:37:52–13:38:12 | exit0，446pass/0fail/skip，1既有Starlette warning，原始{coverage['percent_covered']}%={coverage['covered_lines']}/{coverage['num_statements']}≥60 | pure_unit_export |
| 既有T09/T10/T17定向合同 | 13:43:41–13:43:43 | exit0，20pass，isolated fixture（含T17 unit重复复跑） | contracts_frozen |
| 静态 | mypy13:37:52–13:37:53；Ruff13:41:00–13:41:01 | 各exit0，mypy66 source；Ruff3源码/测试文件；format已执行 | mypy_export/ruff_frozen/format_export_apply |
| 资源与自有测试凭据检查 | 13:46:02 | 自有库其他活跃连接0、自有schema0、真实DSN/密码/全部8字符片段匹配[] | resource_close.json |

之前“41PG”的对话简写在此明确更正为27真实PG+14纯计算，不把integration目录位置当证明层级。原60 coverage阈值、官方/人工金标与所有评测分母未改。纯unit不混入PG抬覆盖率。

真实PG为专用 test_dianzi_r04_source_documents_20261015，连接串只从授权 root-only /tmp/.../connection.json 内存取得，另建自有库和每例schema，结束删除自己schema，未动其他DB/执行降级。filesystem是真实内容存储；本包没有用MinIO/HTTP/model/browser替身当live。留档真实NVD/vendor输入，以及对其在内存进行明确synthetic修改的负例都只算fixture集成；测试请求page/startIndex和观察时间为显式合成上下文，不冒称原诊断请求/观察时点。产品live参数由root网关真实返回构造。

主要已证明：两源原文/响应hash可重读、原文成员字节/JSON路径、幂等、envelope不造修订、A→B→A、旧证据、无CVE后补、跨源解析、别名冲突回滚、caller rollback、合法空观察不产生安全结论、坏成员/第二成员存储/引文失败整页回滚、4线程初次插入、权限/URL/旧scope不覆盖、CVSS未知/同版冲突/跨版兼容与三字段支持、拒绝/撤回来源声明。

## 4. 问题台账

- TEST-01：巨大5MiB参数被pytest自动展开到case ID，Windows PYTEST_CURRENT_TEST超32767字符，产生setup/teardown error与20MB日志。仅给该同一输入显式短ID，未删case；原stdout/JUnit无损gzip保存，解压byte/hash校验，原时间/退出码不变。
- TEST-02：重复vendor记录负例却request per_page=1，2记录先触发容量拒绝，预期分支错误。改合成请求per_page=2，验证真正重复ID拒绝；不是改原金标/门槛。
- TEST-03：首轮PG期望机构UUID凭记忆错写，来源原文实际134c704f-9b21-4f2e-91b3-4a467353bcc0；更正新测试字面值，不改fixture/业务结果。18pass/1fail日志保留。
- LOG-01：首轮自有扫描错误把完整DSN所有8字符片段也扫描，匹配postgre/普通路径等，过度遮盖日志；不是确证密码泄露。改只扫描完整DSN、完整密码及密码8字符片段。旧过度遮盖日志/20个标记保留，后两轮匹配[]；不宣称已扫描未知产品模型密钥，由root最新凭据规则扫描集成提交。
- STATIC-01：首轮mypy发现resolved_ids缺类型与version可能None，补明确tuple[str,...]/正整数检查；首轮Ruff测试导入、长行与上下文格式，按现有规则修复无ignore；最终0。
- GC依赖：主控独立review确证旧响应引用与GC race后，主控6c7提供共享register_response_content/GC修复；本包按授权集成并复用，不复刻公共锁/存储逻辑。16共享回归有2个真实GC race例通过，独立组件意见由主控登记。
- 源撤回传播：已保留原声明与证据，完整重判/重激活未由本包完成，负责人主控R16；不能把事件注册active标签称来源仍有效。
- 初期只读文件路径猜错和创建run目录前Copy-Item失败，未改业务或用户文件；随后rg定位/创建允许run路径修正。部分发生时间历史未记录，未按mtime猜测。

## 5. 调用链、并行与冻结

独立工作区 C:/Users/yinha/.codex/worktrees/recovery-r04-source-documents/dianzi。主控/API实现/独立review并行，本 Agent只拥有3业务/测试文件与此run/report。未调用其他用户聊天或发送外部消息。

CBM CLI0.11.0，开工独立索引backend/src，schema/architecture/trace已落盘；冻结164fc8e再刷新独立项目dianzi-r04-source-documents-164fc8e，869nodes/3930edges，全部成功解析。缓存/tmp/dianzi-cbm-r04-source-documents-20261015在仓外，不索引秘密/holdout/附件。graph+rg+源码核对 persist→register→raw存储/revision→EventRepository→block/evidence→KnowledgeRepository→DimensionRepository→fetch；同Session。此冻结作者worktree没有HTTP/worker/API挂载，只有定义和测试入口，不能据此声称产品在线链已经可用；主控正在df集成候选接真实source_jobs/runtime/API，需新独立review。

## 6. 限制与下一步

没有新依赖、模型、HTTP/分页下载器、worker注册、API路由、UI或后台服务；必要新增仅来源固定边界与现有深模块编排、对应负例与PG行为测试。没有“节省多少行/费用”估算。费用unknown，产品付费调用0；本包source HTTP调用0，数据来源诊断由主控此前取得。

本包不代替完整G-A/G-B/R04/R05验收。MinIO实际运行接通、真实持续来源→worker/cursor→API/浏览器、实际来源观察/性能、模型回答、整系统安全、人工与正式盲测仍not_run或由主控后续任务处理。R16撤回/旧新/空结果重判未完成；资产/多跳/9维等不因这一切片绿。

独立复核入口：用冻结164或主控df、新隔离schema与授权专用test资源，复跑本包25PG、纯unit原60、合同20、相关GC回归。所有秘密只注入env/private file；run_pg.py包含精确自有库验证，不复制硬编码开发/生产DSN。当前自有数据库与0600配置保留供review，全部临时schema/活跃任务已释放，无需kill他人进程。

## 7. 修订记录

- {started}：首次依据真实日志和系统时钟创建；未知历史不猜。
- __END__：核对层级、失败保留、接口顺序与剩余切片，状态awaiting_review。
"""
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
report=root/"reports/tasks/R04-source-documents.md"
report.write_text(body.replace("__END__",ended),encoding="utf-8")
print(json.dumps({"created_at":started,"ended_at":ended,"report":str(report)}))
