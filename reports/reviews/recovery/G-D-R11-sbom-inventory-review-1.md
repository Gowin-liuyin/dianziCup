# R11/T24 SBOM库存与容量 · 独立初审1

What this change does: 本批把已审 CDX 1.5/1.6/1.7 与 SPDX wire SPDX-2.3 纯适配器接入私有资产导入，保存不可变原文和独立侧车，以完整结构摘要识别变化。局部库存 JSON 预算覆盖合法10000组件，旧快照 DTO 和投影摘要保持兼容。

评审结论：`needs_changes`，必须先修复发现1。该结论只覆盖本批库存/容量/侧车表，不签整个R11、T24、T28或G-D。实现者最多awaiting_review，状态文件由主控登记；本审未修改progress、业务、原测试、公共schema、迁移、锁文件、金标或阈值，未提交或push。

评审人：新非作者独立Agent `/root/r11_sbom_inventory_first_independent_review`。WT `D:/wt/r11-sbom-inventory-review1`，分支 `codex/r11-sbom-inventory-review1`。被审代码 `0892b6af7fbc0c16651aeb25f14493fb4c3fa48d`；被审最终材料与本审基底 `c0369e6b7cb71c19f7594da8737e6bb3717893f3`。侧车表来源root `0532c4f58611e068fc7d5b03da984bc57dbad9f2`，同patch本WT祖先 `e1cad47f1c2f90bc024cd99c9b189613d675fb4c`；纯适配材料祖先 `f6acedcd2b004671c317f55dd058f46e5e517de9`。本审同时检查表与业务，没有借此前静态DDL smoke签PG。

实际记录时间为Asia/Shanghai秒级，见本run `commands.jsonl`、`uv_sync_receipt.json`及最终`seal_receipt.json`。首结构化测试命令06:32:21，最后业务检查06:42:15（2026-10-16）。更早的工具读取、WT创建及探索没有完整磁盘命令收据，不补造起止。主工作区已有未提交修改，未触碰；本WT最终仅本报告与独占run目录有新增文件。

初次uv日志路径探索在PowerShell Out-File重定向处失败；该shell工具exit0不代表uv执行成功，没有将此轮计通过。随后使用正确绝对路径实际离线sync exit0，并保存uv_sync.log/receipt；初探索只保留会话工具事实，无磁盘原日志，不补造。

**Must fix**

1. **[P1] 侧车声明原样返回受保护URI，泄漏连接串、文件路径和URL凭据**（`backend/src/ai_intel/assets/sbom_inventory.py:94`；同函数91行透传component_sources、92行dependency_edges、93行completeness_declarations；`sbom_inventory_contracts.py:47`与`inventory.py:174`）。
   - **这是什么：** `freeze_sbom_sidecar`直接把纯适配器声明写入侧车DTO，GET在校验形状和摘要绑定后返回该DTO。字符串有类型，但没有出站隐私边界。
   - **问题：** SPDX `externalDocumentRefs[0].spdxDocument`为合成`postgresql://synthetic_user:synthetic_password@db.internal:5432/private`、`file:///C:/private/synthetic-parent`、带userinfo的HTTPS URI时，认证POST均201，sidecar GET均200并原样含该值。另官方合法CDX1.7的bom-ref、dependency ref、composition assemblies含合成数据库URI时，同租户analyst（只有READ_ASSET，无WRITE_ASSET）也200读到原值。4失败是同一根因，输入均通过冻结官方离线schema，不是非法标准输入造成的假阳性。跨租户404仍有效，本发现是冻结隐私合同失守，不声称已发生跨租户泄漏。
   - **最小修复：** 在dispatcher/冻结侧车和历史读取边界复用一个受保护声明校验，覆盖URI可出现的来源ref、关系/composition引用和external document字段。至少拒绝或安全净化文件/数据库URI、userinfo凭据；保留私有raw、原始全JSON摘要与版本，不重写已审parser，不改旧DTO，不靠前端掩盖。已有不安全冻结payload也应在GET安全拒绝为503或以批准的安全DTO规则处理。普通无凭据HTTPS文档引用、checksum和正常graph需保持可读取；具体拒绝/净化策略如改变受支持profile，记录最小CR。
   - **若跳过：** 上传原文里的连接信息会进入默认声明读取，违反`CR-R11_sbom_inventory_proposal.md:28`“原文、内部路径、连接串、opaque值均不返回”。惰性URI不执行只能防止抓取，不能证明回显符合隐私合同。
   - **复验：** 修复后从新的冻结SHA复跑原337+28+46、4个失败样本，以及普通HTTPS引用、tenant/角色、raw/hash不变和历史读取不重新解析的回归。当前只提交最小复现与建议，没有改业务，尚无修复后通过证据。

没有另外列Should fix/Nice to have；未把猜测、风格偏好或本审脚本错误制造成业务发现。

**实际读取与定位**

已读AGENTS、00执行图、恢复R11 manifest能力前置与任务状态、原T24/T28、03/04/05/06、三个SBOM CR、原资产CR及作者R11-sbom-inventory报告；采用本机`ponytail-review`5.2.0。R11最终仍需要版本、条件、研判、OpenVEX及界面等全部切片，原T24/T28六验收没有缩减。作者材料里的05异步202/当前同步201、analyst写权限差异保持原批准范围，未趁本审改协议或授权。

本次自己的CBM源项目`r11-sbom-review1-src-20261016`为1509节点/7879边，默认排除了assets；另外索引`r11-sbom-review1-assets-20261016`为253/1132，partial/unusable均0。schema、architecture及parse_manifest/parse_inventory_input/import_manifest/get_snapshot_sbom trace原结果完整保留；CLI实际返回的工具schema使用JSON参数，deprecated参数提示保留。调用图未显示嵌套路由caller，已用源码rg交叉确认，不把0 callers当无路径。入口的实际链路是HTTP认证与事务内当前权限→InventoryService→dispatcher→既有SBOM/manifest parser→raw snapshot/sidecar/current→save_change_publication的epoch/change/job/outbox→import receipt，同Session提交；GET再次认证当前scope后按三列身份join返回冻结payload。

已逐段核对businessdiff `0892^..0892`的14文件、root新增表/CR、已审parser及所有直接调用者，读取既有inventory_models、auth事务入口、knowledge publication和前端冻结合同。源blob冻结证据在`audit_receipt.json`与`source_blobs/`，不以作者自检或旧图替代本审。

**真实命令与结果**

统一解释器为本WT `backend/.venv/Scripts/python.exe`，测试/质量检查cwd均本WT backend，CBM cwd为WT根。完整argv、cwd、上海起止到秒、exit、原日志路径在独占run [commands.jsonl](../../runs/recovery_r11_sbom_inventory_review1_20261016/commands.jsonl)。核心结果如下，重复复跑不叠加：

| 命令/日志 | exit | 真实结果 |
|---|---:|---|
| `uv sync --frozen --offline --no-progress`，uv_sync.log/receipt | 0 | 独立离线venv，无锁改动 |
| `review_runner.py pure` → `python -m pytest` 原18文件、`--no-cov -q --junitxml=.../pure.xml` | 0 | 337 passed，unit213/contract30/security94，0 fail/error/skip，69.55s |
| `review_runner.py sbom` →原PGHTTP测试资源副本，pg_sbom.log/xml | 0 | 28 passed，0 fail/error/skip，9.30s |
| `review_runner.py legacy` →原T24资源副本，pg_legacy.log/xml | 0 | 46 passed，0 fail/error/skip，4.43s |
| `review_runner.py probes` 初轮，pg_probes.log/xml | 2（child） | 本审错误import造成collection 1 error，0业务例执行；修本审脚本，不计业务失败或通过 |
| probes第二轮，pg_probes_second.log/xml | 1 | 18例：15 passed、3 privacy failed，0 error/skip，6.46s |
| `review_runner.py compatibility`，pg_compatibility.log/xml | 1 | 3例：CDX1.5/1.6容量2 passed，CDX引用隐私1 failed；0 error/skip，117.70s包含离线schema验证 |
| `review_runner.py targeted`，pg_targeted.log/xml | 0 | 单独真实SBOM身份的shape/sidecar SHA/combined SHA损坏3例均503；SQL观察器绑定修正后复跑1例；4 passed、17 deselected、0skip，2.76s |
| `python -m mypy src/ai_intel`，mypy.log | 0 | 125 source files无问题 |
| 本改动13源码/测试 + root表，`ruff check`、`ruff format --check --no-cache` | 各0 | 14文件通过 |
| 自有材料脚本 Ruff/format，review_materials_* | final0 | 初4脚本首轮50风格/导入等问题原日志保留；最终含digest/seal共6脚本，修正明确格式与检查提示，未改原资源副本断言或业务 |
| `review_runner.py audit`，audit_final.log | 0 | 81作者材料raw SHA核对，18source blob对应code；先两次本审错误假设前端字符串assert exit1保留，不算前端或业务失败 |

唯一功能用例为原411例全通过，加本审24个新例20通过/4失败，共435唯一功能例、431通过/4失败；targeted中的SQL复跑不重复计数。初collection error与材料检查失败另列。测试warning保留：Starlette/httpx、旧per-request cookies弃用；不改依赖或关闭检查。

**PG资源、行为及容量**

只从批准WSL connection.json捕获连接到内存，凭据不入argv/报告，局部PG loopback25432，16.14。资源身份与前向revision详见`*_database.json`：SBOM/probes/compatibility/targeted使用`test_dianzi_r11_sbom_review_...`前向0019；legacy独立`test_dianzi_r11_inventory_review_...`前向0018。原fixture16/18断言完整保留；资源副本仅改数据库/run_id前缀两行，`*_resource_guard.patch`可核对。全部只测试创建局部sidecar表，明确`test_table_create_not_production_0022`，不drop、不downgrade、不删库、不碰队列15/其他端口/MinIO/持续采集器，也没有外部来源/模型/FOFA/付费请求。

真实PG已核对：PK/三列同租户FK；hash小写长度、版本长度、JSONB object、NOT NULL；UPDATE/DELETE触发器；CDX三个版本/SPDX的raw bytes与raw SHA，raw不可改写；graph/checksum/composition/opaque-only变化新增history/current/change/outbox；旧projection仍原语义，combined只用于新SBOM判等；空白/对象键序复用、精确raw幂等冲突、A→B→A、旧请求重放不复原current、4并发仅一次发布。最终import receipt处人为失败后assets/snapshot/sidecar/receipt/epoch/change/outbox均回滚。shape和摘要损坏拒503，不吞为empty/pending；历史parser替换为抛异常后仍可读取，tenant B 404、撤权403、匿名/撤销401、Origin/CSRF及extra tenant参数拒绝均有本审原回归。

容量修复的共享strict_json_object仍50k、SBOM raw 200k/深度16/10000/1MiB不变。局部预算810163的数学键值计数与完整8字段+64路径的10000组件纯测试已核对；原两条dense10000能力缺口测试只按批准从projection_node_limit改为完整成功，输入/schema未改。作者capacity首红3例和旧预期DID NOT RAISE两例仍在81项封存中，本审没有剪红、降门槛或删难例。

官方离线CDX1.5/1.6/1.7/SPDX schema与多字段10000容量均已有独立执行。CDX1.5实际HTTP输入精确1048576字节，1.6/1.7/SPDX均小于1MiB；最后位置/版本/typed source/raw一致，无截断。普通checksum仍非image_digest、dependency非runtime path、composition complete仍unknown/空声明范围、未知生态非安全结论。

当前`sql_capacity_measurements.json`是targeted复跑的观察：1与10000组件写入+一次sidecar读取均15条SQL；10000原文737852字节，service写1.671843s。第一次观察1与10000也同为15条，10k写2.745515s，文件读取见会话工具记录；该绿测量文件随后由targeted脚本更新，旧红日志没有覆盖。源码遍历/映射以栈、list/set/dict、排序完成，没有每组件PG调用；新写解析两遍是有限常数倍。此为本机合成容量观察，不是P3完整问答SLA、并发吞吐或产品live。

**材料、原始证据与限制**

独立`audit_receipt.json`确认作者manifest 81项，精确SHA256 `7aa107ebf586796c3d7aad2574d5617de60665af8dbee47a69d2cd451aa27f82`；报告原文从`report_raw.md.gz`恢复为SHA256 `1e1ba2d404c4b4e649328d51e49aecc8ec217299cb0777296f9f19d00d357a49`，并核对工作树LF/CRLF归一内容。18份filtered Git blob与code一致，Git LF bytes另gzip封存。review报告的精确raw copy、文件列表、源码SHA、实际值秘密扫描和shape扫描在本审seal_receipt；仅本run用局部attributes保护证据，不改全局属性。

共享conftest失败redaction hook通过插件挂载到独占副本与外目录probe；实际配置的连接/密码最终在内存扫描，shape检查区分合成URI和已遮口令的Engine表示，不把fixture假字符串当真实凭据。没有捕获或公开真实会话/口令。命令输出为实际捕获后UTF-8文本落盘，Windows文本写入可能表现为CR/CRLF转换；签的是保留日志的实际文件bytes，不冒称未经文本转换的stdout。材料格式化前执行源码保存为`*.executed.gz`；compatibility测试运行期间纯格式化改变行位置，原traceback可能显示新磁盘行文，XML的实际失败message和原执行源码同时保留，4个真实失败不因此改skip或剪掉。

前两次seal工具exit1：首次因shape扫描未识别pytest缩写合成URI的6处显示，第二次是说明文字和分类器常量又写入相同缩写。路径/长度诊断保留`shape_diagnosis.json`。仅对四个已知本审失败日志/XML里的精确缩写增加合成分类，并移除说明里的完整URI文字；不删失败内容、不增加产品豁免。最终仍扫描实际配置值与未分类凭据形状。前两次seal工具输出没有另存完整磁盘日志，不补造。

只读核对前端冻结1acf的`frontend/src/features/assets/asset-contracts.ts`，source_kind:string及text(item.source_kind)、严格旧DTO字段/10000上限保持兼容；格式选项仅JSON/CSV。首轮误找本WT未存在的api路径和两次审查脚本字符串假设（z.string、row）错误均为本审工具错误，纠正为实际item后不再猜、扩大前端补丁。没有运行前端或浏览器。

评分证据限于F2/F3可追溯库存/历史及变化发布、E1租户/事务/质量、D1冻结材料；P2只有功能边界，没有金标准确率；P3只有上述受控局部观察。原T24 C01–C06已有JSON/CSV与SBOM相关局部证据，C06本次隐私边界仍未通过，不能签整卡。T28研判/证据包/规则与R16重判不在本批，没有据outbox存在声称消费已完成。

本审改动文件只为本报告与`reports/runs/recovery_r11_sbom_inventory_review1_20261016/`中的runner、独占resource copies、独立probes、raw日志/XML/receipt/source blobs/seal；具体文件和SHA以最终manifest为准。scope_diff_receipt确认backend/docs/contracts/progress/frontend与c036无diff。

Verdict: fix 1 first. 状态`needs_changes`，下一步为作者按最小隐私边界修复并冻结新SHA后独立复核。Not checked: 生产0022前向迁移、正式API app装配、SBOM frontend/browser_e2e、产品live/manual、真实资产所有权/完整性、研判/OpenVEX、正式性能和持续运行；完整R11/T24/T28仍partial。




最终报告封存写入时间：2026-10-16T06:47:10+08:00（Asia/Shanghai）。
