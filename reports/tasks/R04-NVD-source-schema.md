# R04 · 真实NVD字段与来源历史持久化切片

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T12:59:31+08:00。
状态 awaiting_review；实现partial；主控/root；阶段G-B，R03网络/游标尚在独立复核，允许本批独立组件开发，未过G-A或G-B。

NVD旧fixture的vulnerability wrapper和顶层baseScore与真实CVE API 2.0不符。新normalize_nvd_record/page读取vulnerabilities[].cve和各版cvssMetric*.cvssData.baseScore；保存机构、向量、版本与精确JSON路径，多机构并存，bool/非有限数/范围外评分拒绝，Rejected与字段缺失保留。HTTP429只调用一次，交PG唯一调度层；原T10-C06预期调用3→1是消除重复重试，原测试ID/其余行为/金标未删除。旧synthetic样本保留CVE、分值和CWE，仅纠正wrapper/路径，明确非金标。

实际匿名NVD GET于12:24:39–42得到200/3106bytes，原始证据recovery_r03_network_root_fixes_20261015/nvd_doh_fixed.*；byte相同留档fixtures/recorded/nvd_api_20261015_public.json及provenance。留档单测只能证明结构兼容，不能计作PG/UI live闭环。真实响应发布时间无offset，遵守合同不猜；原值保留，业务时间None。GitHub vLLM公开厂商响应已取得，适配器由独立实现者并行准备。

复用：标准datetime/urlsplit、既有JSON2/Unicode证据定位、内容寻址存储、PG版本/回收和Alembic。必要新增：NvdMetric/NvdPage明确真实结构；0013保存已存在UI合同必需的来源与定位字段，未建新框架或内存权威。兼容/迁移/回滚见CR-R04-R04_source_persistence.md。

实际运行：recovery_r04_sources_20261015/schema_initial（314通过）与schema_metadata（332通过，22.49s，64.69%），命令/时刻/退出码见各command.json。后者含unit、T10、T05、旧数据迁移和3个新PG来源元数据测试；专用test DB，每例临时schema，不对其他固定版本库downgrade。第一次脚本相对目录错误已在会话命令输出保留，未计作业务失败；新报告helper恢复为绝对根定位。静态首次两行SQL超长已按字符串拆分修正，未改逻辑；最终日志另存。

unit/contract/integration：上述限定范围passed；security：仅边界用例，整卡not_run；frontend/e2e/live链路/manual：not_run。已知限制：分页网络worker/API尚未装配；无NVD明确时区证据；尚无九维全体、真实模型、持续采集或评分指标。禁止因此登记整R04/T10 accepted。

## 2026-10-15T13:25:24+08:00 · 初审三项Must的定向修复候选

新非作者r04_sources_independent_review固定2ff2f999实际发现并复现：NVD description/CWE/reference的NUL和surrogate未拒绝；-00:00、非法offset和超6位秒小数被datetime宽松归一；GC四组引用COUNT后并发提交新响应FK，旧GC先删文件而SQL DELETE被FK拒绝，PG仍指向已丢失原文。独立16项中12fail/4pass；原报告和原始输入保留，不用此前回归通过抵消缺陷。

候选修复复用标准re/datetime及已有_optional_text，严格限制源时间语法和精度、拒绝未知offset；合法naive源时间仍NULL，原值仍在原文。描述/CWE/reference经UTF8/NUL校验。GC在savepoint先执行PG DELETE/外键检查，成功后才调用存储删除；23503并发引用冲突保留对象并返回False，其他数据库错误仍抛出。已有hash advisory锁保留；新增最小register_response_content(Session,ContentStorage,bytes,aware_time)共享同hash事务锁、校验存储原字节并登记content_objects，新响应引用在同一调用方事务完成。来源服务不再复制内容注册逻辑，不改变公开DTO、schema、计分或盲测。R20完整备份/故障恢复仍须独立验证，不以此race修复声称全存储恢复通过。

定向原输入复制到tests/integration/test_r04_review_regressions.py，仅把WT定位与专用schema fixture资源绑定到当前checkout，未更改原断言。最初Ruff移掉不同名fixture导入导致2setup errors，继而临时空schema未迁移导致2UndefinedTable；这两轮是root取证适配错误，分别保留reviewed_fixes和reviewed_fixes_2日志。绑定显式同名fixture并调用迁移后reviewed_fixes_3实际行为通过；Windows/WSL同checkout并发写默认.coverage导致路径混合警告，第三轮覆盖率不作门证据。已改每运行独立COVERAGE_FILE并重新执行reviewed_fixes_4_isolated_coverage，只有新独立覆盖率JSON可用于门槛。所有旧失败保持，未skip或调整期待。

另一真实兼容问题：API实现Agent在Linux全unit发现既有pdf_text.py读取subprocess.CREATE_NO_WINDOW的类型检查失败。根因是该stdlib属性仅Windows导出；root将其改为已核对[Win32官方常量0x08000000](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags)，仍只在os.name=nt传入，Linux仍0，不削弱Windows后台子进程行为。Linux33组件补测和新的完整unit日志在recovery_r04_parsing_linux_20261015；首次全unit与Windows覆盖数据相撞的结果不作覆盖率门，新full_unit_2使用独立缓存。该一行兼容修复将单独冻结，不能用旧48ad审查给新代码背书。

本候选仍awaiting_review，三个Must只有原reviewer在新固定SHA定向复跑后才能关闭；API/worker/页面live链路、持续采集、正式指标仍未证明。
