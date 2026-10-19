# R06 · 组合版本九源默认调度、PG/MinIO、REST 与真实 Edge 验证

文档首次创建时间：2026-10-15T23:20:06+08:00
本次写作开始时间：2026-10-15T23:20:06+08:00
最后更新时间：2026-10-15T23:20:06+08:00
准备工作实际开始：2026-10-15T22:30:01+08:00
本受控采集/服务段：2026-10-15T22:46:31+08:00 → 2026-10-15T23:06:18+08:00；1187 秒。
证据截止：最终本地只读快照 2026-10-15T23:11:03+08:00；后续文档/秘密扫描和清单冻结另记实际时刻。
执行 Agent：/root/r06_integrated_live_validation；基线/实际产品代码 1156b2ed6616e3a4297215c2893d2cbe633f5215。
独立 detached worktree：D:/wt/r06-integrated-live-1156；产品工作树干净，无业务修改/commit/push/accepted 登记。
任务切片：验证已独立 Ship 后合入的来源 normalizer/worker、来源 UI、poller 和 CPU guard；整 R06/G-C 仍 in_progress / partial，三项来源缺口及其他未验收范围不变。

## 1. 范围与门

读取实际 AGENTS、00/03/05/06/11/12 恢复合同、R06/R07 前置、已冻结 source boundaries/worker/polling/UI 和原 document live 报告。按 R06/T08/T11–T16/T49/T54 的能力切片，验证原生 60 秒 beat → 九固定来源 root → PG/outbox → worker/官方网关 → PG/MinIO → 认证 REST → Edge。没有模型、测绘、PoC、第三方扫描、holdout、人工金标或公开部署。

主控门首次全纯 1824 passed / 1 failed /74.36%（新增精确 fixture 未分类），原红日志保留。此 Agent 独立核对三项 fixture 后，主控仅新增精确分类，原 scanner/根/阈值不改，原安全 42 项复跑通过；另有主控 148 PG、339 frontend unit、type/lint/build、Ruff/format/mypy 通过。主控随后明确授权启动本外网段；本报告不把这些数字写成本 Agent 同次重跑全绿。root_live_gate_authorization.json 保留授权与门层级。

415ee580258ce55b8771c4fc4d070c3a8e78aea0 的分类、后续 1a52e17 的原日志字节保全是主控元数据提交；本实际产品始终 1156。独立 fixture 初审 d3e175… 和元数据复核 872109… 仅确认三项分类，不签整阶段。

## 2. 隔离、复用与真实运行入口

复用既有 document/GB 的 prepare、Windows OwnedJob、supervisor、DPAPI env、实际鉴权和 Playwright harness；只新增本次采集观察、固定来源失败取证和最终校验脚本。Python 标准库、现有 SQLAlchemy/httpx/Redis/MinIO/Playwright 与 Windows Job/PowerShell 平台能力，无新增依赖或业务抽象。

专库 test_dianzi_r06_integrated_live_20261015 从空库升级至 0015_catalog_document_metadata，两个真实 PG 预建测试角色 system_admin/null tenant 与 viewer/隔离 tenant。原 G-B 数据库只读前/后 0014 版本，没有迁移、写入或停旧 API28010。原 MinIO 服务继续持有已有资源边界；本 run 显式 CONTENT_STORE_BACKEND=minio、同一获授权身份/immutable bucket。旧 r04 配置实际是 local，不能凭旧报告猜 MinIO；第一次前检即在建库前阻止，保留 prepare_initial_guard.log。原始对象与所有诊断响应只在 MinIO 和仓外 runtime-cache，Git 中为元数据/哈希/viewport 截图。

Redis14 dbsize2，未 flush/删除；只读检查15 dbsize0后改用15，独有 queue r06_integrated_live_1156 和 global_keyprefix r06-integrated-live-1156:。API28012/UI25175 均 loopback。SOURCE_POLLING_ENABLED=true 启用原 beat60秒、vLLM1800秒/其余3600秒桶、每轮5页，不改间隔、不手工触发 poll_due。第一桶9 roots，跨实际23:00桶再9 roots；另一个实际浏览器 CAC backfill1 独立于这18个 beat roots。

秘密仅已授权 runtime/MinIO 配置和 DPAPI login env；日志逐值遮蔽，登录 Cookie/CSRF 不入日志或截图，清生成 provider key。Windows null env 会成为空 SecretStr，前检原 is None 误判被记录并改为拒绝非空值；没有凭据赋值或产品修复。所有环境恢复进程原值。

CBM 官方0.11/cache在仓外，独立 backend/src 项目 r06-integrated-live-1156 为1250 nodes/6301 edges，frontend/src 项目442/1662，0 skipped/partial。schema/architecture/poll_due outbound和 collectSourcePage both trace 与 rg/实际源码核对；索引仅 src，未读 holdout/秘密/无关资料。图有边不作为业务正确证明；默认 beat 和实际数据已另实测。

## 3. 真实来源与持久化结果

第一份采集观察 2026-10-15T22:46:33+08:00 → 22:50:32 exit0：9 roots、16分页任务/17执行尝试、149资料/149修订/1556证据、161 MinIO对象。观察器没有人工提交管理员 source root，仅 viewer 的真实403负例。最终段结束后如下，绝不把 framework job_runs365当采集次数：

| 固定来源 | 官方主要类别 | 文档 / 修订 | 实际分页 job 状态 | job执行尝试 |
|---|---|---|---|---|
| nvd_ollama | structured_vulnerability | 45 / 45 | succeeded:3, failed:1 | 6 |
| vllm_vendor | vendor_advisory | 100 / 100 | succeeded:8, partial:2 | 10 |
| osv_ollama | structured_vulnerability | 31 / 48 | succeeded:2 | 2 |
| avid_community | security_community | 1 / 1 | succeeded:1, blocked:2 | 4 |
| ollama_releases | code_repository | 0 / 0 | blocked:2 | 2 |
| trailofbits_blog | technical_blog | 20 / 20 | succeeded:2 | 2 |
| arxiv_security | academic_paper | 0 / 0 | blocked:2 | 2 |
| nist_ai_rmf | technical_standard | 1 / 1 | succeeded:2 | 3 |
| cac_generative_ai | policy_regulation | 1 / 1 | succeeded:3 | 3 |

最终 199 documents、216 revisions、2146 evidence、30 source jobs、34 source job attempts、24保存的HTTP成功记录、23 page receipts、234 content objects。6/8类别确有本次真实worker落库，academic_paper/code_repository仍0；九来源目录不等于九通道/八类别全通过。AVID第1条成功而后续受阻，不称完整社区采完。vLLM两桶第5页均 partial/source_page_limit_reached，与游标/receipt并存；目录没有伪装持续在线。

OSV合法9位 modified原值留在 source_metadata/original object，PG精确时刻 NULL，adapter2与未知精度不伪截断；NIST真实48页文本PDF、有48个page定位，January2023保留raw/unknown时刻；CAC真实24条、adapter3、有章节/片段定位，未执行法律适用判断；RSS20条仅 feed_excerpt，许可unknown，不称全文。raw response/container和派生member hash分开保留；原文未知许可未整包进入Git。详见 revision_metadata_final.json / source_jobs_final.json / collection_receipt.json。

最终234个实际MinIO对象逐个 read_verified 后对 SHA256和size验证，通过，合计 6905789 bytes，副本在 D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-integrated-live-1156/originals/<sha>.body。所有2146证据按保存block的完整文本坐标和quote哈希验证，invalid0；此证明定位/字节，不证明引用内容支持任意结论。既有NVD/vendor的supports_claim=true有其旧抽取行为，不能要求全部false。首轮最终检查仪器误将这部分判错，原 instrument_initial_final_receipt/log/命令保留；仅删去该错误额外假设后本地复核0错误，不改业务/数据。

## 4. 实际 Edge、权限与展示

初轮真实 Edge 22:52:38 → 22:58:08 exit1，4failed/1passed。DOM已呈现九源，仪器 getByLabel exact因label嵌套option文字不能匹配；另资料测试先筛政策后搜NIST未清筛选，实际空结果导致超时。保留原 spec/config/log/browser_report/error-context/hashes，两个输入错误均能由保存DOM/脚本复现。

新 v2只使用冻结 source-kind/source-stream ID，并在NIST标题查询前清类别筛选。2026-10-15T23:04:25+08:00 → 2026-10-15T23:04:46+08:00 exit0，5passed（20.5秒），没有 route interception/fixture/trace或自动登录截图：

1. 真system_admin九选项与实际18 roots的首桶9个job状态查询，不替换blocked/partial。
2. 页面通过真实Origin/PG session/CSRF提交CAC backfill1，实际worker succeeded，job063f0f45-e6c0-4308-b42c-86bae175be0d；5.37秒 created→finished仅此页任务，不是问答耗时。
3. viewer无来源调度权限，浏览器不发送源管理请求；另真实REST GET job和POST collect均403，logout后documents401。
4. 1366/390宽度筛六个已入库类别、资料详情/证据哈希、固定保存版本选择、刷新、真实空查询、logout深链清私有片段；无横向溢出、背景 pointer-events none，正常topology-drift/reduced-motion none。
5. 保存的官方CAC来源链接确实打开原publisher URL、title正常。

viewport图 document-visible-v2-1366.png / document-visible-v2-390.png / source-admin-visible-v2-1366.png 已用view_image原分辨率查看，文字/哈希/未知精度标记可读。手机图是实际滚动到证据区的900高viewport；没有裁图拼图或静态模拟数据。此处NIST只一条修订，固定版本选择入口通过，不冒称多修订历史变化/R16完整验收；OSV另外存在17个二次修订，相关业务一致性仍须后续审查。录像未运行，正式彩排另做。

## 5. 问题、负结果与失败取证

| ID | 实际触发/结果 | 状态与证据/下一步 |
|---|---|---|
| LIVE-RELEASE | 根页job dddb1725… blocked/source_response_invalid；下一桶仍blocked；没有code_repository文档 | 独立diagnosis进行；固定额外GET1 HTTP200/616207B，raw972aa160…a5cf，RepositoryFetchError。source_diagnosis.json及仓外body，不能称原失败响应已保存 |
| LIVE-ARXIV | 两桶root均blocked/source_response_invalid，无论文落库 | 原worker失败body/status/hash未保留；额外GET2为NetworkRequestError无body，不能冒称原parser输入；不猜API在线/停服，交root独立复现 |
| LIVE-AVID | 第1条tree/blob→PG成功，第二条blocked；第二桶仍blocked，源游标停在offset1 | 首诊断错传PG包装cursor已明确撤回并保留；真实lease先剥position。经原4GET预算余2次固定immutable tree/blob，正确offset1再现RepositoryFetchError→_reference_identifier:65；原始body路径/hash在 source_diagnosis_avid_position.json，交独立diagnosis |
| LIVE-NVD-2 | 第二桶job ee41c7b9…，source_server_error→network_timeout→source_server_error，3尝试后failed | 45旧已证实文档保留，游标/任务失败不写成采完；确切上游失败status/body没有保存，不伪填500。source_jobs_final.transitions |
| INSTRUMENT-SELECTOR/FILTER | 上述4初轮Edge失败，源码和DOM证实操作输入错误 | 新副本v2复跑5pass，原红保留；产品未改 |
| INSTRUMENT-ENV/REDIS | local错误配置、空SecretStr和Redis14已占前检 | 前检阻止建库/迁移/源码请求；显式MinIO+非空凭据判断+空Redis15后prepare0，未flush旧键 |
| INSTRUMENT-BROWSER-DEP | 独立v2 controller初用未安装psutil，ModuleNotFoundError，在新browser启动前失败 | 原日志保留，改用已有Windows PowerShell/CIM只读内存，不新增依赖；后续controller正常 |
| INSTRUMENT-SUPPORT | 最终evidence仪器额外要求所有 supports_claim=false，误报旧已支持事实 | 原结果保留，只复核原坐标/quote hash合同，全部2146定位正确；不改事实或假称初轮通过 |

额外诊断总4个固定GET，release1/arxiv1/AVIDtree+blob2，无重试/任意URL/模型。原worker parser失败事务回滚使失败response没登记，诊断重读不能偷换成原次raw；此为需要工程修复的观测缺口。所有原bytes在仓外。原始source HTTP总交换次数未被PG完整记录：34是job执行尝试、24是已保存成功HTTP，不相加假装精确HTTP总数；4诊断精确已知。按每个source job最多2 HTTP的保守上界为34×2+4=72，低于160本段预算；DNS/浏览器publisher子资源不混为source page尝试。正式连续统计必须补真实HTTP请求计数和失败取证。

## 6. 资源、停止与时间指标

原supervisor采用Windows OwnedJob：512MiB/进程、2GiB/core总Job、20%hostCPU、1200CPU秒、1200wall秒、80source jobs/160job attempts、每running source35秒看门狗、每日志16MiB。实际 1187 秒后23:06:17 owned stop，23:06:18四核心进程均Terminate exit1（原初轮browser也exit1）；不是自然退出0或产品失败计分。API/UI端口确认关闭。原runtime CPU193.625秒、peakJob1,408,823,296B；没有超6h稳定运行声明或不同版本拼接。

原supervisor只有一次browser触发，后补其文件的v2分支不会热加载。新v2在原段剩余窗口内单独OwnedJob（512MiB/进程、1GiB Job、20%hostCPU），绝不重启采集/续deadline；结合原/新进程树 private memory看门狗与原CPU累计预算。实际browser CPU29.796875秒、peakJob1,007,177,728B、结合private峰1,909,276,672B <2GiB。采集Job与v2Job理论CPU rate可20%+20%=40%，不宣称v2是单一aggregate20%；CIM执行有延时，也不声称严格每1.000秒采样。该仪器限制如实保留，正式性能资源隔离需统一后复验。

最终216修订中精确pub缺48、future0、其余168全部>6小时，p50=11324915.849896秒，p95=61634643.720237秒，max=79463805.170237秒。它们是首次/历史目录发现间隔，含大量旧公告，不是独立参考集合的正式实时采集分母；不将历史回补当实时达标，也不排除这些差距涂绿。独立漏采参考集合/漏采率未运行。无问答请求，问答延迟not_run；模型/测绘0、新付费调用费用0，项目此前模型费用不在本报告本段范围。

## 7. 命令、层级与证据

cwd D:/dianzi 的 launch.ps1各Mode注入授权env、只操作本专库/端口。完整实际命令和+08开始/结束/exit见 prepare_command、collection_command、browser_command、browser_command_v2、source_diagnosis_command、source_diagnosis_avid_position_command、finalize_command JSON；原 SQL/HTTP UTC字段明确原始工具UTC，面向人时间均+08。

| 层级 | 实际结果 |
|---|---|
| unit/contract | 本产品全门not_run；窄独立fixture34pass，不算live；主控门另见授权receipt |
| integration | 真PG0015/MinIO234对象/REST来源与资料通过所述范围，6类别；主控148PG不冒本Agent复跑 |
| security | 真实admin/viewer、Origin/CSRF正常请求、viewer403/logout401通过；全部攻击/租户导出未运行 |
| frontend/e2e | 首轮4fail/1pass、新仪器5pass；3原viewport实看；不称全部工作台闭环 |
| live | 部分证明、三解析/连接兼容缺口和第二桶NVDfailed；整R06/live不能passed |
| manual | Agent视觉检查3图；0人工金标/裁决、0正式manual acceptance |

代码版本和runtime资源配置见runtime_start/end，第一次与最终业务快照不能相加成独立事件/测试数量。原red、复核green、诊断4请求与成功原文证据保持独立命名。整个R06剩CNNVD授权/国内库、签名webhook、广产品源、独立漏采参考、正式持续时效和停机回补等；R07九维、R09知识卡、图/推荐/全平台和人工正式评测未被本小包代替。

## 8. 合同差异与交接

无新增产品合同/接口/依赖/金标/评分口径改动。唯一业务范围是执行已审组合的真实验证；原厂商和NVD保持现有行为。独立diagnosis需要根据本原输入给最小修复/回归、后由新reviewer闭合，再同新冻结版本复验失败来源；不能拿本1156成功片段给后续不同产品SHA背书。

本包状态awaiting_review（验证材料）；整R06/G-C in_progress/partial。未push、不自签accepted，不停止主控总目标。可继续与缺口独立的富化/工具/标注准备，但正式8类别/时效和依赖缺失的live门不越过。

## 9. 修订/字节与秘密

本报告首次创建在实际写作时刻；没有把准备代码时长、文档写作、测试时间与1187秒运行窗口混称。原初失败/仪器红结果都保留，有独立metadata receipt而非覆盖。扫描与artifact_manifest在全部文档落盘后运行，manifest排除pyc/__pycache__/缓存/CBM、仓外原文和秘密；不写自身递归hash。收尾hash/实际扫描时刻另见清单。

补充仪器记录：首次writer依赖Windows默认GBK读取UTF8业务JSON而UnicodeDecodeError；原日志/exit1在report_writer_initial_unicode.log/json，显式UTF8并删除未使用读取后重新写作，没有改业务/原文。
本次写作结束时间：2026-10-15T23:20:06+08:00

材料补注 · 2026-10-15T23:24:51+08:00：报告草稿编写起止没有单独记时；前述本次写作时刻是自动组装/落盘的真实时刻，不能据此声称完整文档编写只花0秒。本段新增模型/测绘付费调用0、费用0；宿主与既有运行资源成本unknown。final_receipt_scope_metadata_erratum保存过期supports_claim描述的原副本，只更正说明文字，不改业务或检验数量。
