# CR-R06 · 修订真实模式与 v2 读取兼容

文档首次创建时间：2026-10-17T01:56:52+08:00
本次写作开始时间：2026-10-17T01:56:52+08:00
状态：approved_for_implementation；新非作者复核固定版本后才可签切片验收。

授权依据：完整 R00–R24 批次、原文历史不覆盖、fixture/live 必须隔离，以及来源持久化 CR。此补充修复已证误标，不改变公开 DataMode 枚举、schema 版本、权限、金标或指标分母。诊断材料 5716a1d15c2eb60a13b2b4e05cbc6b4e25b0acfa，默认真实来源审查 ac6a0ed2efccc4b5af12888605d959937b57d982。

## 真实依据与兼容参数

实际模式只来自被投影修订的 source_metadata。live 必须同时有后端 trusted-source-runtime-v1 策略标记；fixture 可来自该可信策略，或历史明确 fixture 且没有策略字段的保守记录。缺失、None、类型不符、未知策略或值一律 unavailable；不能从部署模式、URL、引文或当前修订补写 live，也不迁移已有历史。

共享小函数负责单修订分类及有界集合的同质性。KnowledgeReadService 和 DocumentReadService 增加 keyword-only require_expected_mode=True，兼容既有构造调用，业务消费者默认必须实际模式等于它已配置的 expected mode，然后才能把证据转成没有模式字段的 citation、embedding 或推荐输入。这个约束不生成模式。服务端公共 knowledge/document router 唯一显式传 False，以现有 fixture/live DTO 如实展示同质历史；客户端无此参数，不能绕过认证或 SQL 可见性。未知和混合不得无声过滤、修改游标或返回伪造空列表。

documents list/detail/revisions 核对每条实际返回修订；events list 核对每个摘要实际使用的可见 active revision association；event detail 核对全部实际返回历史、claim/assertion 和引文的可见修订，不以 primary/current 替代；read_evidence 查询加入该 span 修订元数据。空集合只沿用部署运行模式且明确不是存在真实输入的证明。枚举只含 live/fixture；非空 unknown/mixed 为明确 503，不将未知标 fixture。

R18 classify_revision_mode 复用同一严格分类和 expected-mode 规则；不削弱现有公开 producer 的模式隔离。R07 StructuredFactProofReader 在两阶段当前身份/输入围栏中核被读取修订的模式，与配置匹配后才返回 typed report；指纹和终态重读涵盖这些元数据，防止首次验证后被更换。纯业务证明函数不因新增模式约束改变值支持或 unknown 条件语义。

## 有限实现与尚存限制

本包仅共享分类函数、两个 read service、两个公共 router、R18 分类函数、R07 reader 相应读取围栏和直属测试。既有 retrieval/service、hybrid、answering/evidence_bundle、调查/工具/推荐均保留默认 True，必须追踪所有调用并以实际负例核对；不能借 public False 路径消费 fixture。原测试中显式合成输入应通过既有 SourceResponse 或 persistence 参数标记 fixture，保留原业务断言；不可批量改原测试预期、改产品历史、金标或评分。

这是阻断误标的兼容修复。现有 v2 无逐修订 unknown/mixed 表示；混合或未知事件历史会明确不可提供，完整历史工作台体验仍 partial。不得因此宣布 R17 历史能力完成、删掉验收或把未知记录丢弃。后续支持逐修订来源状态需要另冻结兼容接口、完整前端/SDK 和独立验收，不能静默向严格 v2 客户端发新枚举。

## 迁移、回滚、任务与验证影响

无数据库迁移或依赖变更。只读修复不更新既有 revision/source_metadata。回滚移除公共 False 展示路径并继续严格失败关闭，不重新开启历史误标成功；保留所有旧 raw、任务与失败证据。影响 R06/R07/R12/R14/R15/R17/R18；报告各层实际状态，source storage 的先前通过不自动变成读取通过。

验收包含诊断 24 个原反例、两个真实模式历史的 PG 回读、unknown/mixed/空页、跨修订引用、原 ACL、引文与 cursor、真实规则标记缺失/冲突、内部 live 消费 fixture 被拒、输出变换之前的校验，以及旧业务回归。新增 reviewer 必须核固定 source SHA、默认 API、consumer 调用链与真实 PG；未跑层写 not_run，不代签完整阶段。

## 修订记录

2026-10-17T01:56:52+08:00，Root：根据真实 clock 转北京时间冻结兼容方案；尚未实施、未 push，整卡 partial。

2026-10-17T02:45:18+08:00，Root：模式集合容量复用R18既有2000输入上限，limit2001只检测超限并明确503，不丢历史/改游标/伪空。仅两个直属合成fixture输入改显式fixture（或明确trusted合成live），原业务Oracle与24诊断不改，不计live；所有可见实际修订必须核模式。
