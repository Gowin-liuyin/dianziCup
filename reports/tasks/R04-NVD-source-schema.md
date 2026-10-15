# R04 · 真实NVD字段与来源历史持久化切片

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T12:59:31+08:00。
状态 awaiting_review；实现partial；主控/root；阶段G-B，R03网络/游标尚在独立复核，允许本批独立组件开发，未过G-A或G-B。

NVD旧fixture的vulnerability wrapper和顶层baseScore与真实CVE API 2.0不符。新normalize_nvd_record/page读取vulnerabilities[].cve和各版cvssMetric*.cvssData.baseScore；保存机构、向量、版本与精确JSON路径，多机构并存，bool/非有限数/范围外评分拒绝，Rejected与字段缺失保留。HTTP429只调用一次，交PG唯一调度层；原T10-C06预期调用3→1是消除重复重试，原测试ID/其余行为/金标未删除。旧synthetic样本保留CVE、分值和CWE，仅纠正wrapper/路径，明确非金标。

实际匿名NVD GET于12:24:39–42得到200/3106bytes，原始证据recovery_r03_network_root_fixes_20261015/nvd_doh_fixed.*；byte相同留档fixtures/recorded/nvd_api_20261015_public.json及provenance。留档单测只能证明结构兼容，不能计作PG/UI live闭环。真实响应发布时间无offset，遵守合同不猜；原值保留，业务时间None。GitHub vLLM公开厂商响应已取得，适配器由独立实现者并行准备。

复用：标准datetime/urlsplit、既有JSON2/Unicode证据定位、内容寻址存储、PG版本/回收和Alembic。必要新增：NvdMetric/NvdPage明确真实结构；0013保存已存在UI合同必需的来源与定位字段，未建新框架或内存权威。兼容/迁移/回滚见CR-R04-R04_source_persistence.md。

实际运行：recovery_r04_sources_20261015/schema_initial（314通过）与schema_metadata（332通过，22.49s，64.69%），命令/时刻/退出码见各command.json。后者含unit、T10、T05、旧数据迁移和3个新PG来源元数据测试；专用test DB，每例临时schema，不对其他固定版本库downgrade。第一次脚本相对目录错误已在会话命令输出保留，未计作业务失败；新报告helper恢复为绝对根定位。静态首次两行SQL超长已按字符串拆分修正，未改逻辑；最终日志另存。

unit/contract/integration：上述限定范围passed；security：仅边界用例，整卡not_run；frontend/e2e/live链路/manual：not_run。已知限制：分页网络worker/API尚未装配；无NVD明确时区证据；尚无九维全体、真实模型、持续采集或评分指标。禁止因此登记整R04/T10 accepted。
