"""有界POST的实际范围、原始失败和独立待审边界。"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
run = Path(__file__).resolve().parent
now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
unit = json.loads((run / "unit_coverage.json").read_text())["totals"]
mixed = json.loads((run / "fixed/coverage.json").read_text())["totals"]
report = f"""# R05 · 共享网关的有界JSON POST准备切片

首次创建/本次写作开始/结束/最后更新时间：{now}。
实现者/root；状态awaiting_review；R05整体partial/not_started实际模型；G-A/B未过门，本包是安全独立接口准备。

既有网关只支持GET，无法发送OpenAI Chat Completions或Anthropic Messages请求。复用现有numeric-IP固定、Host/SNI、CA验证、绝对deadline、共享并发、响应大小/错误分类与凭据脱敏；新增post_json只发送1..1MiB bytes、固定Content-Type、只允许受控anthropic-version日期头；Host/认证/Content-Length不由调用者覆盖。凭据仍只由OriginCredentials向精确HTTPS origin注入。POST所有301/302/303/307/308拒绝，不把输入或鉴权转发到下一地址；没有网络重试或GET成功后备。JSON业务schema在上层模型适配器校验，本层只限传输资源，不假装已经实现模型输出校验。

必要新增仅PinnedHttpTransport.request的GET/POST关键字和NetworkGateway.post_json；两入口共用_bounded_fetch避免复制预算/IO，旧fetch公共参数和GET行为保持。request_fingerprint_sha256继续是既有URL指纹，不能当作POST payload/prompt指纹或缓存键，模型层必须另存prompt/schema摘要。无依赖/PG/public DTO迁移。

实际验证：第一次相关运行511passed但新oversized参数未指定短test id，pytest把1MiB合成值放进PYTEST_CURRENT_TEST，Windows32767环境变量上限造成setup/teardown 2errors；不是HTTP产品负例失败。保留network_regression.log/tests.xml原始失败，仅给3个新参数显式ids，未改输入/预期/阈值。post_fixed20/20；fixed/完整相关512passed/0fail/skip，raw coverage {mixed['covered_lines']}/{mixed['num_statements']}={mixed['percent_covered']}%。纯unit396passed raw {unit['covered_lines']}/{unit['num_statements']}={unit['percent_covered']}%，静态Ruff/format/mypy65当时版本通过；该代码快照尚未包括后来的API挂载，不能给API背书。所用全部socket fixture明确隔离，不计live。实际命令/时刻/退出码均在run目录receipt；post_fixed直接命令未单独记录起止，写历史未记录，不补造。

两个真实请求协议的官方依据：[OpenAI Chat API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)、[DeepSeek Chat](https://api-docs.deepseek.com/api/create-chat-completion/)、[DeepSeek Anthropic兼容](https://api-docs.deepseek.com/guides/anthropic_api/)。DeepSeek网页直接open多次timeout，官方检索正文及既有provider-docs报告保留，OpenAI页面实际open读取；文档不当成本机实际调用事实。

unit/contract/security仅上述传输切片passed，integration/frontend/e2e/live/manual=not_run；产品模型调用0、费用unknown；生成codec、embedding/reranker、pgvector索引和问答还要实现。新非作者必须固定候选复跑后才可有限验收；不签整R05/T18/G-B。后续若模型服务301/307，明确配置错误而非放宽自动重定向；业务失败由PG唯一调度与调用预算处理。
"""
(root / "reports/tasks/R05-http-post.md").write_text(report, encoding="utf-8")
decision = f"""# CR-R04 / R05 · 受控JSON POST补充

首次创建/本次写作开始/结束/最后更新时间：{now}。状态awaiting_review；记录者/root；属于既有R03/T08/R05/T18已授权接口能力，无评分/金标/来源或费用边界变化。

新行为：共享可信外部网关允许有界JSON POST，保留原GET合同；请求bytes1..1MiB，固定Content-Type，额外普通头只允许anthropic-version日期；凭据精确origin注入，所有重定向失败，单次网络尝试，不跟进/改为GET、不泄漏正文或秘密到下一origin。响应大小/TLS/固定peer/绝对deadline/共享并发/错误正文不读沿用既有合同。仅复用传输基础，无新依赖/schema或任意URL/shell/SQL工具。模型配置和数据外发仍须由认证上下文与批准provider决定，接口存在不代表上游可用或可以发送私有资产。

兼容：旧fetch和request GET默认参数不变；新POST是keyword-only。现有URL指纹不宣称涵盖POST body，prompt/schema/payload摘要由模型层明确记录。迁移无；回滚为停止新模型调用并还原本小接口，保留原任务/用量/失败，不启用fixture后备。影响R05/R08需要POST的受控供应商；对应验收是body/headers大小、私有输入、无重定向、真实HTTP错误/超时、schema和原GET回归。root20新cases及512相关通过，独立审查未发生，正式live0。
"""
(root / "docs/decisions/CR-R04-R05_model_post.md").write_text(decision, encoding="utf-8")
print(now)
