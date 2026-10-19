# G-C · R07 输入审计初审 1 的 fix1 定向复核

What this change does: fix1 在返回私有模型输入正文前，锁住冻结的历史 source、document、revision，以及当前 event/workflow；随后重新检查当前权限和审计完整性。历史读取仍允许旧 revision 非 current、旧关联退出当前 roster，不重跑 selector、不创建新的模型调用。

**Verdict: Ship，限本次输入审计 ACL 修复切片。** 原初审 finding1 的三个真实业务红以相同输入/assert亲跑变绿，新增授权/历史/并发和现实 writer 路径检查通过，没有新增确认缺陷。原 NVD oracle 仍红，生产0023、整体输入审计接线、整 R07/G-C/live仍未据此通过；本 reviewer不写accepted、不改共享进度、不push。

## 冻结身份与保护

被审代码 `0c57b559fe2f0d93f8a5359383f1db6cc7abc6f5`，code tree `295ecfd6f68422a63118b9e70069fc4b0085ea9b`；材料 `648c71795e1bea34511ec0d04348f35f6463a5e6`，material tree `d37984fb84395413d35daa7f789a1c6e09c4c33e`。独立干净 WT `D:/wt/r07-input-audit-review1-fix1`，分支 `codex/r07-input-audit-review1-fix1`；旧基线 `014de585413c8a82a04d00b1ff2fbd1ff62d733b`。实际 source仅 `job_service.py` + 新 `test_r07_input_audit_fix1_acl_pg.py`，2 files 253新增/8删除。

同一非作者 reviewer继续定向复核，沿用已读新版 Ponytail review5.2.0、AGENTS、00/R07卡和03/04/05/07、两关键CR；再次读冻结任务状态与本次diff/report。只新增本报告与 `reports/runs/recovery_r07_input_audit_review1_fix1_20261016/`，没有业务/DDL/API/settings/auth/attrs/锁/旧测试/金标/阈值/分母/盲测/共享状态变化，没有递归spawn。09:35:59+08:00第一条实时时钟及后续实际命令起止绑定在 `review_identity.json` 和同名命令回执；封存结束见 `recheck_manifest.json`，不使用mtime补时间。

`freeze_proof.json` 使用独立 Git batch object reads亲核：408旧 protected文件、93旧作者材料、原review报告/manifest及147个原raw文件全部保持；三个 owned contract/metadata/types原样，五语句0023 proposal SHA仍 **ee2fde666548f57cdd56376e443d00592ee107a3efb4d6c169e9c1df6581bbd6**。旧review报告SHA **89fce892f7d5787d6c574b38fc7c277a59a0d0669311b9d7b6c5b74100318b6b**，旧manifestSHA **272ce2e699e18560833c0575daea47910b9c04aeb1dae28baac991c455c439fc** 不变。

fix1 raw_manifest的Git原bytes SHA **50c03a99d779a44f4619a25867421213a4dd024da0c0894822bfc61cb93e48ae**。准确文件边界是manifest列103个材料，另manifest自身/后置index verification/material fingerprint三件closing材料，共106材料；加2 source，共108 package paths。这与交接的106材料+2 source相符，不把original_review_third三个计数字段当文件。closing三件与作者WT原bytes另核一致。普通checkout使103列项中的91件raw发生CRLF转换（12件raw相同），source新测试亦为CRLF；逐件Git原hash、checkout raw、LF等价保存，未改attrs或重写作者文件。

默认材料 `git diff --check code material` **exit2 / 1140诊断行** 独立复现，stdout存 `material_whitespace_actual.txt`（只对其中1处实际test认证用户名连接片段脱敏，行数不变，before/after文件hash另记）；source/check、code→material source/tests无差异、current tracked clean均exit0。这是原raw日志归档空白，不要求trim，不据它指控业务差异或声称全包whitespace通过。

## 原 Must 的关闭依据

`job_service.py:1252/1283/1312`的新路径为 current auth/user SHARE → 校验frozen hash/event/revision集合 → source SHARE → document SHARE → revision SHARE → event SHARE → workflow SHARE → 重读workflow与初值比对 → fresh `read_workflow`父ACL → `_read_input_audit_record`。source/document/revision身份必须等于冻结映射；缺行、变换或损坏拒绝。锁持续到调用方事务结束。

reader不另取source advisory；实际 source writer是source advisory→source FOR UPDATE→document/revision→event，SHARE与该FOR UPDATE冲突。publication的source advisory/source SHARE与reader源SHARE可并存，随后document/revision FOR UPDATE被reader阻挡。源码、fresh CBM和实际调用探针交叉确认了这一顺序，没有复用只允许current roster的publication helper，也没有新依赖或另一套状态。

原 source/document/revision三路 probe source raw完全相同，函数摘录/input/assert SHA仍 **e5032e8b97082e209ba640a8aedbc8a1bbd79833caf0b2dcdcf324a74b50d8ab**；`bootstrap_review.py/review_identity.json`证明字节复制。`original_acl_green`亲跑3pass，三份结果均writer_blocked=true、writer_committed=false。原初审13pass/4fail（3业务、1codec仪器红）及明确重建说明仍冻结，不改历史。

原审计39 + 新ACL13 + 我原独立17的69组合亲跑全部通过。新测试确认writer先source/document/revision/event，reader等锁后fresh拒绝；reader先则session/user/event/workflow writer不能提交；非空tenant的历史父权限可以正向读，撤权后拒绝；所有revision非current且所有旧event_documents inactive仍读原recorded；既有actor锁、跨租户、审计hash/shape/Unicode/补集/cap/receipt/legacy等完整回归保留。

我额外直接调用 **ensure_source_registration、persist_source_response、persist_catalog_documents、save_document_revision、EventRepository.publish_events、publish_enrichment_attempts** 六个实际 writer入口，在已授权audit读事务打开时均得到真实PG **SQLSTATE55P03 lock_not_available**，没有以连接失败冒充锁阻断。另一次真实ensure_source_registration先取得排他源行锁，reader先等待、writer提交后成功返回原recorded，没有死锁。相关七case source为显式synthetic/recorded fixture、无来源或模型网络IO；新 writer探针中的一次模块导入collection error和一个NVD query参数缺失SourceDocumentError保留，修正只在自有新探针，最终6pass+定向1pass，不混为业务修复。

## 真实命令与结果

实际运行器：`D:/dianzi/backend/.venv/Scripts/python.exe reports/runs/recovery_r07_input_audit_review1_fix1_20261016/checks.py <label> [--services] ...`。运行器将PYTHONPATH指向新WT，pytest cwd `D:/wt/r07-input-audit-review1-fix1/backend`；各label JSON保存完整argv、cwd、真实+08起止、HEAD、exit、JUnit counts，log/XML独立保留。pytest均明确 `--no-cov -q --junitxml=...`，不是降低原整体coverage门槛。

| label / 执行内容 | 真实结果 | exit |
|---|---|---:|
| original_acl_green：原相同三路race | 3pass / 0error/skip | 0 |
| audit_pg69：旧audit三integration+security、新ACL、原独立17 | 69pass / 0error/skip | 0 |
| unit_contract：原unit12+contract6 | 18pass | 0 |
| job_regression：原相关unit/contract/security | 69pass | 0 |
| models_original143：model_fields56 / single41 / root_causes46原期待 | 143pass | 0 |
| real_writer_paths_second | 6pass / 1自有URL仪器fail | 1 |
| real_source_response_writer：定向修正自有approved query参数 | 1pass | 0 |
| default_scope_metadata：default33 + scope24 + metadata20 | 76pass / 1原NVD fail，0error/skip | 1 |
| baseline_nvd：完整四个精确5b模块、同原case/input/assert | 1原NVD fail，0error/skip | 1 |
| static_ruff / static_format：两source | pass | 0 |
| static_mypy：四owned modules、冻结pyproject | pass | 0 |
| source_diff_check / material_source_unchanged / current_tracked_clean | pass | 0 |
| default材料whitespace原bytes | 1140诊断行，已分层 | 2 |

`default_scope_metadata_partition.json`独立从JUnit拆分：旧execution21为20pass/1red，defaultAPI9/alias1/固定probe2共12pass；scope16+security8为24pass；metadata20pass。不会把77写成全绿，重复原三探针、基线或复跑不累加为新的评分分母。每case记录另见 `test_summary.json`。

自有freeze工具起初错把checkout raw当冻结Git raw、随后把交接106/108文件边界当manifest列项数，原断言工具输出保留于会话，成功核验另存freeze_proof；属于审查工具口径问题，不是业务red/skip。没有改作者manifest、旧期待、数据或阈值。

## NVD、调用链与未验收边界

原 NVD testcase line528仍在Atlas partial与旧failed的期待处失败；精确5b四模块基线再次同红。原input SHA **c5cf6c0b00bc691dd97f1b8fd26504b7c104e047dfda0c278f54a6e70a66735a**、67块/25956 JSONB bytes不改。69组合中的我的原NVD探针再次证明实际wire texts与audit相等、后三维各一次offline codec、原50/16384char/65536byte预算、全部来源依赖/Unicode omitted补集/incomplete；Atlas taxonomy_missing partial/0receipt，错误fixture revision仍failed，publication partial/CVSS available。

本复核沿用初审的独立判断和正式CR验收建议：批准bounded-selection后，full roster67并不要求实际发送超过50，因此旧“四维预算失败/全0wire”oracle已不成立；不能仅因baseline也红关闭。主控须正式冻结oracle演进，在相同原输入、保原预算/全部依赖/omitted/incomplete/错误revision拒绝/原full-input143期待的前提下另验收。本复核未修改旧assert/skip，未关闭原NVD项。

fresh CBM `r07-input-audit-review1-fix1`重新索引目标源码，**2068 nodes / 11391 edges，0 skipped/partial/unusable**；不是作者2067/11364或原review2067/11371的图。schema、architecture、read_input_audit/_lock_input_audit_parents和source/revision/event/publication writers、default worker/API的trace归档，实际CLI argv与+08回执齐全。`all_callers.txt`与真实source交叉：内部quoted-text reader仍没有产品API caller；public read_workflow/API安全DTO不加正文，default worker仍通过runtime factory调用同一服务，job_runs/事实PG仍是权威。生成src索引目录已移入自有run的cbm_artifact，业务没有依赖它。

生产0023仍root-owned pending，五statement未变，本轮仅自有随机schema明确安装test-only proposal。默认API/worker函数的真实PG复跑不是实际broker投递/消费、运行服务或在线模型验收。历史reader验证PG冻结identity/hash和实际输入/trace，不重新读取CAS；已有CAS损坏0wire检查限新执行，不扩大为历史reader CAS重读证明。

## 资源与封存

仅指定DPAPI test resource的TEST DSN进Python内存，pwsh7/driver/127.0.0.1:25432/base test DB/test用户名/有效截止核验。业务只用独立新 **test_dianzi_r07_audit_review1_fix1_261016**、随机 `test_r07_review1_fix1_*` schema和双marker；fixture全部NullPool，只有一个serial pytest heavy PG进程，未提高PG限额/杀他人/改原业务DB/做downgrade。实际slot已向主控释放；`pg_release_receipt.json`在 **09:51:17+08:00** 核schema0、除检查本身外session0、database settings0，engine已dispose，没有启动后台服务。

外部probe显式加载共享失败hook并以SecretStr登记到实际stash。`exact_secret_scan.json`封存时重扫本run每份raw/JUnit、两source、fix1作者106材料、旧作者93/原review147及报告，扫描批准DSN/password的raw/URI/HTML/JSON变体，不记录值或值hash。实际DSN/password matches=0；用户名不blanket ignore：精确公共base测试库marker碰撞单列，另发现作者冻结default_scope_metadata.log/.xml各1处实际test认证用户名的Engine连接片段（密码已***），明确归类为masked-auth片段而非公共marker，不修改作者原bytes、不声称作者用户名全零。我自己的诊断副本仅脱敏此连接片段，自己的新测试raw/JUnit没有用户名片段。`username_fragment_classification.json`保留这个事实；未发现真实密码/完整DSN或软件日志输出的新缺陷，属于已冻结审查仪器材料的有限标识曝光。扫描结果与逐文件raw/LF SHA在 `recheck_manifest.json`。模型keys/生产secret/盲测/模型缓存未读，外部模型/付费/测绘/来源请求0，fee unknown。

Not checked: 生产0023、真实broker/API服务/前端e2e、provider/source/测绘live、人工/正式金标、整体coverage/性能/连续运行未验收。fix1 unit/contract/PG/security/static有真实通过；整R07/G-C仍partial，live blocked_live，manual/frontend/e2e not_run。评分证据限F2/P2/R1输入追溯与E1/X1权限/幂等边界，无正式分数。

下一步：主控可以据本意见登记原Must关闭并集成本窄ACL修复；NVD正式CR、0023/产品入口和后续阶段检查仍独立办理。原初审needs_changes报告不覆盖为新结论，原红历史不删除。
