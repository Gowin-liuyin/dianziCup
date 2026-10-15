# G-B / R04 · PG知识只读API独立复核2

首次创建、本次写作开始/结束与证据截止：2026-10-15T14:11:24+08:00。reviewer /root/r04_api_independent_review，非作者、未参与业务实现。结论：7af91b3下本API限定技术范围通过，初审Must1/2/3关闭；不整卡accepted，不签R04或G-A/G-B阶段门。

What this change does: 在原NUL和stale修复之外，读取已保存维度时批量区分不可见输入与公开的错误事件关联。真正私有引用继续隐藏；存在、可见但不属于本事件修订的引用返回固定503，保留历史版本与有效原输入。

## 固定范围

目标实际解析完整SHA `7af91b3796ef14a545ba2413acd8254a7f8a095a`，tree `fb6ac8f8c7ac394e4c23c8294b7869397731f785`，新干净codex/review-r04-api-recheck-2-20261015分支，WT `C:/Users/yinha/.codex/worktrees/recovery-r04-api-review-1-recheck-2/dianzi`。每个正式收据确认此SHA/tree和clean；没有审root可变checkout。

本次95→7af的backend源码/测试diff只为knowledge_read_service.py及直接回归测试；该提交区间另含作者证据文档，未扩大本API验收范围。复用_revision_join/_revision_visible/_visible，在两个集合查询中按claim/evidence/revision/document/source完整层ACL读取所需ID；SQL只查询所需ID，不取其他事件正文。存在且可见但不在当前事件关联修订集合的成员抛KnowledgeProjectionError，统一503；私有对象不暴露名称/正文/ID。结构没有逐维/逐引用查询，但没有负载实测，不能报告性能达标。

AGENTS、00、恢复R04、T40/T41、03/05、来源持久化CR/只读投影、auth和前端DTO依据沿用初审及95复核，均实际读取。原auth、knowledge_contracts及source router装配相对95没有改变。三个报告保留各固定版本的独立结果，不拿作者/root日志签本人的通过。

## 原输入复验与关闭依据

原8SHA256 `e8fd5f80663779f323fbbf9ac35f28a7333db44478c1c62c081ee9a9daf6b69b`，原9 `6d77704e7a4415418c6ec73ae50d387e5b1a5fd6bd2d3859486e85796588b896`，95新2 `ce6d117ecd8dfb604bacdcadcacadfae57b8660fae9e4cd96a1f1ada3d09debf`；完整输入/期望字节不改。原24copy仅绑定本人新测试库，所有业务断言不改；conftest保留失败脱敏，实际秘密登记只在本人root0600文件。

- Must1：q/product/risk_type的原NUL HTTP输入422，三个模型NUL输入拒绝；Pydantic既有surrogate拒绝仍成立，长度/UUID/分页边界与字面%/_回归通过。
- Must2：不存在UUID与三数组[{}]固定503；两个公开外事件claim/evidence错关联输入也503。原私有source/claim/evidence/dimension全部仍隐藏，system_admin无tenant不通读私有；跨租户与不存在404一致。没有把保存损坏包装为空成功。
- Must3：支持claim已标stale时维度stale，原event_version/旧revision/withdrawn行为通过；旧claim只引用其自身source_revision_id证据，旧时间NULL/legacy定位未伪造。

43项为原24+原8+原9+95新2，共43passed/0fail/skip。默认create_application自己构造真实PG认证/状态，只有隔离engine工厂被测试绑定；实际登录cookie驱动/v1和/api/v1的event列表/详情/evidence读取，用户query自报tenant/role不能扩大范围，注销后旧cursor401。原来源/引用去重、q/product/risk_type/updated_after与cursor绑定、DB失败503、历史证据/hash/span/block边界均在这组保留断言。

## 真实命令与资源

raw `reports/runs/recovery_r04_api_review_1_recheck_2_20261015/`；cwd、完整argv、+08秒起止、退出码、代码SHA/tree、clean及COVERAGE_FILE见对应receipt，数量见XML。

| 检查 | 实际时段(+08) | 退出 | 证据 |
|---|---|---|---|
| pg_all_original_probes | 2026-10-15T14:07:51+08:00–2026-10-15T14:08:38+08:00 | exit0 | pg_all_original_probes.* |
| unit_windows | 2026-10-15T14:07:50+08:00–2026-10-15T14:08:18+08:00 | exit0 | unit_windows.* |
| static_mypy | 2026-10-15T14:07:50+08:00–2026-10-15T14:08:00+08:00 | exit0 | static_mypy.* |
| static_ruff | 2026-10-15T14:07:51+08:00–2026-10-15T14:07:51+08:00 | exit0 | static_ruff.* |
| static_format | 2026-10-15T14:08:42+08:00–2026-10-15T14:08:42+08:00 | exit0 | static_format.* |

全unit505passed/0fail/skip，原覆盖率3075/5026=61.18185435734182%，原60门不改；505中包括30个cursor unit。mypy70源码文件、Ruff全src/tests、format158文件均exit0。保留Starlette/httpx弃用warning，没有为了消warning改锁/依赖。95版先前Windows/Linux各505及auth36的证据保留在上轮；没有冒充7af本轮Linux完整505或auth36又执行过。本轮Linux43个真实PG端点检查覆盖改动的查询/实际scope。

本人专用DB `test_dianzi_r04_api_review_recheck2_20261015`，PG16.14，每例独立schema；data_mode=fixture、数据是明确合成，不计live情报。Windows新WT uv sync --locked真实68包；Linux为本人独立venv，初审逐项核对锁版本后物理复制Linux依赖，不共用Windows/作者venv。每run覆盖SQLite位于仓外独立cache，JSON原始保留。

自有CBM0.11.0只重新索引此WT backend/src：925nodes/4315edges、70文件、0not-indexed/partial/skipped。cache `/tmp/dianzi-cbm-r04-api-review-1-recheck-2-20261015`，project dianzi-r04-api-review-1-7af9；schema及_dimensions trace实际留档，源码rg/SQL与PG43项交叉确认ACL→PG→DTO链。app/auth完整链此前固定95已追踪，本轮app/auth blob未变，默认PG装配再次实际执行。

本人只写报告/raw，无业务/schema/锁/progress修改，无commit/push。专用DB释放见resource_release.json/receipt（schema0、active连接0、DROP后DB0，无强制断连/共享库修改/downgrade）。真实测试DSN全文、连接密码全文与登记动态密码/会话值全文及全部8字符片段扫描见private_test_secret_scan.json；报告/日志不含这些值，未读产品keys/.env/KEYS/holdout。所有模型/测绘/PoC/第三方资产调用0。

初审4934的5个失败、95的2个失败和环境setup失败仍原样保留，不能删除或套用新通过数。manifest按捕获字节冻结每批报告/raw，git blob/source绑定见相应manifest；作者68项captured/Gitblob双SHA0不符只证明完整性，不替代本人结果。

未检：sourcewriter/source_jobs逻辑/真实worker/采集、browser/live/manual、持续运行、全部富化/模型问答、性能/并发压力、正式人工金标、整R04与G-A/G-B。F1/D2/R1仅有保存PG知识三GET读取证据，F2仅所列逐维状态/引用，不能宣称评分满分。95 source router兼容已由默认PG三GET复测，本次app unchanged；源作业逻辑由另一个新独立reviewer负责。

建议主控仅按本报告登记API已测切片，再协调来源worker与真实浏览器闭环验收；未检live/manual不能算过门。

Verdict: Ship this bounded API slice. Whole-card and stage acceptance remain outside this review.

