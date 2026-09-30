
# 本次资料核查索引

核查日期：2026-09-30。以下区分已读取与未完整取得的内容。只核查文档，没有安装运行完整系统、没有实际接入授权账户、没有复现实验。在线文档可能变化，编码时固定版本并记录实际接口测试。

官方赛题：`competition_brief.pdf`；此前方案：`previous_research_plan.md`。此前方案的研究引用是历史调研输入，本执行包不把其所有仓库能力重新认证为已复现。

## S01 · FastAPI · Concurrency and async / await

入口：`https://fastapi.tiangolo.com/async/`

核查状态：已读取官方正文。

用途与限制：同步/异步职责；选同步IO只是本项目简化设计，不是框架强制。

## S02 · SQLAlchemy · Session Basics

入口：`https://docs.sqlalchemy.org/en/20/orm/session_basics.html`

核查状态：已读取官方正文。

用途与限制：Session生命周期与并发隔离；具体库补丁版本T02锁定。

## S03 · Celery · Tasks

入口：`https://docs.celeryq.dev/en/stable/userguide/tasks.html`

核查状态：已读取官方正文。

用途与限制：幂等、确认、重试与超时；不能据此声称消息绝不丢失。

## S04 · LangGraph · Persistence

入口：`https://docs.langchain.com/oss/python/langgraph/persistence`

核查状态：已读取官方正文。

用途与限制：checkpoint与线程持久化；实际checkpointer API和兼容版本须实装核验。

## S05 · OpenSearch · Hybrid search

入口：`https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/index/`

核查状态：已检索官方文档。

用途与限制：混合检索思路；索引、过滤与评分实现以固定版本契约测试为准。

## S06 · PostgreSQL · Explicit Locking

入口：`https://www.postgresql.org/docs/current/explicit-locking.html`

核查状态：已读取官方正文。

用途与限制：事务与锁设计参照；outbox/CAS完整协议是本项目设计。

## S07 · Node.js · Previous Releases

入口：`https://nodejs.org/en/about/previous-releases`

核查状态：已读取官方正文。

用途与限制：核查时Node24为LTS；不声称未来仍是唯一或最新LTS。

## S08 · uv · Locking and syncing

入口：`https://docs.astral.sh/uv/concepts/projects/sync/`

核查状态：已读取官方正文。

用途与限制：锁文件与同步；不手写未求解lock文件。

## S09 · OSV Schema

入口：`https://ossf.github.io/osv-schema/`

核查状态：已读取官方正文。

用途与限制：别名与版本范围语义；实际来源样本仍需测试。

## S10 · OpenVEX Specification

入口：`https://github.com/openvex/spec/blob/main/OPENVEX-SPEC.md`

核查状态：已读取官方公开规范。

用途与限制：选定并固定规范版本；内部状态不能直接拼成标准状态。

## S11 · FOFA API入口

入口：`https://fofa.info/api`

核查状态：仅取得公开入口，正文不完整。

用途与限制：账户字段、配额、授权与许可未知；T25实际探测前不能写死。

## S12 · NVD Vulnerability APIs

入口：`https://nvd.nist.gov/developers/vulnerabilities`

核查状态：本次未取得可用正文。

用途与限制：仅作官方复核入口，T10必须查实际文档与响应，不猜分页和配额。

## S13 · NIST CSRC Publications

入口：`https://csrc.nist.gov/publications`

核查状态：已读取官方目录。

用途与限制：技术标准候选来源；具体条目类型与抓取方式仍需核验。

## S14 · arXiv API Manual

入口：`https://docs.arxiv.org/help/api/user-manual.html`

核查状态：本次访问失败。

用途与限制：候选复核入口；不能把失败访问当作接口已验证。

## S15 · 国家网信办政策法规栏目候选

入口：`https://www.cac.gov.cn/zcfg/index.htm`

核查状态：本次访问失败。

用途与限制：候选入口，最终URL/结构/抓取许可需要T15验证；不据此陈述政策内容。

## 如何在代码项目中引用

记录来源标题、官方入口、访问日期、实际版本、许可证和使用范围。引用链接不是运行结果；任何“提高准确率”“减少调用”都必须引用本项目实际对照实验。未能取得文档的接口先登记阻塞，取得后补契约测试。
