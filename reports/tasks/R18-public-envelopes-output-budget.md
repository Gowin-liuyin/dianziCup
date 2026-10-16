# R18 · 公开封装与输出词表合同切片

文档首次创建时间：2026-10-16T09:12:52+08:00
本次写作开始时间：2026-10-16T09:12:52+08:00
任务状态：awaiting_review（仅合同切片）；整 R18 in_progress/partial。
实现状态：partial。
工作分支：codex/full-delivery-recovery；代码基线6aeeeec5489b92bb49613fe5daa4eec379182348。
主控实现者：/root；新非作者 reviewer 待派，未登记accepted。

输入→输出：冻结v2公共合同→独立versioned十个封装/分级与异步结果合同；官方pinned词表→工作区外可校验offline预算资源。实际defaultREST、PG资格判定、新SDK/六MCP工具尚未接入，本片不能叫完整平台。

复用：原14defs不改，标准JSON/JSONSchema/FormatChecker及官方tiktoken词表；新增封装是原TaskHandle不支持terminal、原StackCheckResult无结构化分级及来源无公开页的具体需要，没有重写业务或增加新模型依赖。

验证：23 contract tests在 `contract_scoped` exit0/0fail/skip；旧七schema样例作为case内逐项复验，未另加测试数量。`commands.json`有cwd/完整argv/+08起止/exit；全仓覆盖误选exit1和两style红保留，final_style_fix1/final_format_fix1=0。`recovery_r18_output_encoding_20261016/encoding_receipt.json`是官方3613922B词表hash/3 roundtrip/0network offline实际证据，initial receipt/trace是patch对象仪器错误，修后0。费用unknown，付费model calls0。

unit：not_run（没有业务unit实现）；contract：passed（仅本片）；integration/security/frontend/e2e/live/manual：not_run。完整8000token产品分页和producer语义尚未验证；未知/无命中/冲突不降为安全，历史不覆盖当前。

合同影响与回滚详见 `docs/decisions/CR-R18_public_envelopes_and_output_budget.md`；没有改原v2、评分/金标/分母或全仓覆盖门。下一步freeze本片→新非作者review→SDK/MCP受版本约束adapter→root共享PG公开router、Key/限流/worker真实接入→产品API/浏览器/客户端实测。上传/报告/订阅/插件及最终R18验收保持未完成。

本次写作结束时间：2026-10-16T09:12:52+08:00
最后更新时间：2026-10-16T09:12:52+08:00
证据截止时间：2026-10-16T09:12:52+08:00

## 原非作者复核修订 · 2026-10-16T11:02:05+08:00

root831c61f修poll UUID路径，原23+新5=28和原独立97均通过，独立报告G-E-R18-public-extensions-review-1-recheck.md SHA7682341596be2939452319927ca3ff95f4ed866e72c119ac87356599cbc3390c有限Ship。新schema Git/LF SHA4ccc4337586137a407359a1c4a59dc5d92081a2f4b50ee32cc53fac16095d50b；旧14defs与v2不变。原2非UUID红不改，实际producer/六工具/最终R18仍未通过。首次时间保持，修订人/root，写作结束/证据截止：2026-10-16T11:02:05+08:00。
