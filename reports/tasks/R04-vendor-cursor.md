# R04 · GitHub 厂商分页游标修复

文档首次创建时间：2026-10-15T14:47:28+08:00
本次写作开始时间：2026-10-15T14:47:28+08:00
本次写作结束时间：2026-10-15T14:47:28+08:00
最后更新时间：2026-10-15T14:47:28+08:00
工作包：G-B / R04-vendor-cursor；主控 `/root`，实现 `/root/r04_vendor_source`。
状态：awaiting_review；实现 complete（仅此修复切片）；R04/阶段未签 accepted。
基线：7184dc63525ae3e8ea439ec64fc03dfaa629f7a8。
冻结源码：5ca56649bc87d7a9a74f4d52595cdd94f50a233a；分支 codex/recovery-r04-vendor-cursor。
工作树：C:/Users/yinha/.codex/worktrees/recovery-r04-vendor-cursor/dianzi。
独立审查：由主控交原 pipeline reviewer 定向复验；作者未签验收。未 push。

## 问题、边界与修复

主控实际 GET 观察（不是本包 live）：page=1/2 得到同样的10条、115956 bytes，SHA256
f5007db50489ecebbbfec5d8cc8798eb18cff1d12faf503795ce97c85e6894e1。
原实现满10条就 page+1，因此无法取得后页；20页上限有效但只能 partial，不能说全采完成。
留档原始观察见 [公开 probe](../runs/recovery_r04_vendor_cursor_20261015/vendor_pagination_probe.recorded.json)，
原始字节仍为主控 reports/runs/recovery_r04_source_jobs_20261015/vendor_pagination_page_1.json 与 page_2.json。
本包无新增公开 GET，无产品凭据读取，无模型调用；不把留档 fixture 计 live。

依据 GitHub 官方 [repository advisories](https://docs.github.com/en/rest/security-advisories/repository-advisories)
和 [REST pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api)，
改用实际 rel=next 的 after。首请求不带page；PG后续位置固定为 cursor_version=2/after。
每次重建固定命名仓库 URL，不直接读取 Link 地址。仅接受 api.github.com:443 或默认443，
两条明确路径（vllm命名路径/已实见numeric599547518），唯一固定 per_page=10/state=published/after。
拒绝未知/重复参数、外域、私网、userinfo、fragment、其他仓库、混合page及空端口。
after只作为不透明ASCII值（1..2048，字母数字与-_/+=）；header限8192字符/16链接。
无next即结束，满10条也不猜；格式错误、重复next或同after不前进明确失败并回滚整页。

旧持久化page>1报 legacy_vendor_cursor_requires_restart/blocked，保留旧回执；page1只兼容首位置。
未提供重置/迁移入口，R06由主控实现显式管理恢复。本包不会静默清空回填或移动水位。
原文服务保留旧page>=1记录URL，新增无page/after，禁止混合；vendor URL上限6500是
2048字符经urlencode最坏膨胀的必要兼容，NVD仍2000；固定来源、权限、事务均未放松。
只新增一个共享 validate_vendor_after，避免URL构建、Link和保存各自接受不同cursor。

## 文件所有权、复用与调用路径

源码提交精确4文件：ingestion/source_jobs.py、source_documents.py、
tests/unit/test_r04_source_jobs.py、tests/integration/test_r04_source_jobs_pg.py。
报告和本run目录属于作者；未改schema/迁移/依赖/锁/API/runtime/进度/金标/门槛。
复用现有SourceCursorRepository、PG任务/outbox、execute_job事务、ContentStorage与
persist_source_response；保留7秒间隔、20页上限、PG唯一重试与租约。新增仅固定GitHub分页校验，
未引入新依赖或通用HTTP框架。NVD offset/metadata与原始成员字节保存路径保持。

CBM v0.11.0只索引当前backend/src，缓存位于仓外 /tmp/dianzi-cbm-r04-vendor-cursor-20261015。
基线索引 dianzi-r04-vendor-cursor-7184 为926节点/4357边；冻结后独立名
dianzi-r04-vendor-cursor-5ca5664 重新索引。schema/architecture/trace日志均在本run目录。
trace结果与 [rg调用方](../runs/recovery_r04_vendor_cursor_20261015/callers_final.log) 及源码交叉确认：
默认 runtime 注册 handler → collect_page → source_page_url → 共享gateway GET →
persist_source_response → _next_position/_vendor_next_after → commit_page → 后续PG任务。
图的嵌套函数调用边不全，未把没有边当作无产品路径；实际execute_job PG测试验证该路径。

## 实际验证与失败保留

最终unit 575/575 passed，0 failed/skip；原始行覆盖3141/5093 = 61.672884351070095%，
未降低60阈值，独立 COVERAGE_FILE 在仓外；[coverage](../runs/recovery_r04_vendor_cursor_20261015/coverage_final.json)。
source_jobs真实PG 19/19 passed（原10 + 新9），sourcewriter原25/25回归passed，合计44 PG。
PG只用 test_dianzi_r04_vendor_cursor_20261015，每例独立schema，filesystem对象与fixture隔离。
原25测试仅在运行期间精确替换唯一硬编码testDB名，finally逐字节恢复；原/临时hash见
sourcewriter_regression.receipt.json，业务断言/门槛/数据不变，未提交该文件。
真实DB并不使留档来源成为live。两页含新成员/空末页、满页无next、重复after不推进、
恶意header整页回滚、legacy不GET不清回执，原NVD分页/延迟/partial/失败原子性均覆盖。
权限、版本、A→B→A、引文及并发由原sourcewriter25项复跑覆盖。
最终mypy 70源文件通过、授权4文件Ruff通过、git diff --check通过。
unit/contract（留档Link/URL与原文合同）/integration/security：passed；
独立额外contract suite、frontend/e2e/live/manual：not_run；不得用本包替代G-B全阶段验收。

保留失败：unit_red 38 failed/48 passed用于复现旧行为；ruff_first 7项格式/导入位置后修复；
pg_first 3 failed/16 passed，根因为新增断言未按SOURCE_JOB_TYPE过滤，误把原文发布生成的
索引任务当作分页任务（含一个误通过用例也一并收紧），现精确过滤并完整19项复跑。
cbm_index_frozen误用 --project-name/--force 失败；读取原已成功receipt后改 --name/--persistence false，
cbm_index_final成功。未丢弃原失败，未把环境/工具失败叫业务通过。

每条receipt含完整命令、cwd、+08开始/结束、退出码，日志同名；不是持续采集观察时长。

| run | 开始 | 结束 | exit | 命令与配置 |
|---|---|---|---|---|
| callers_final | 2026-10-15T14:46:22+08:00 | 2026-10-15T14:46:22+08:00 | 0 | [callers_final.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/callers_final.receipt.json) |
| cbm_arch_before | 2026-10-15T14:34:35+08:00 | 2026-10-15T14:34:38+08:00 | 0 | [cbm_arch_before.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/cbm_arch_before.receipt.json) |
| cbm_index_before | 2026-10-15T14:32:08+08:00 | 2026-10-15T14:32:13+08:00 | 0 | [cbm_index_before.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/cbm_index_before.receipt.json) |
| cbm_index_final | 2026-10-15T14:45:54+08:00 | 2026-10-15T14:46:00+08:00 | 0 | [cbm_index_final.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/cbm_index_final.receipt.json) |
| cbm_index_frozen | 2026-10-15T14:45:18+08:00 | 2026-10-15T14:45:19+08:00 | 1 | [cbm_index_frozen.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/cbm_index_frozen.receipt.json) |
| cbm_schema_before | 2026-10-15T14:34:35+08:00 | 2026-10-15T14:34:38+08:00 | 0 | [cbm_schema_before.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/cbm_schema_before.receipt.json) |
| cbm_trace_before | 2026-10-15T14:34:35+08:00 | 2026-10-15T14:34:38+08:00 | 0 | [cbm_trace_before.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/cbm_trace_before.receipt.json) |
| cbm_trace_final | 2026-10-15T14:46:22+08:00 | 2026-10-15T14:46:25+08:00 | 0 | [cbm_trace_final.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/cbm_trace_final.receipt.json) |
| mypy_final | 2026-10-15T14:44:38+08:00 | 2026-10-15T14:44:39+08:00 | 0 | [mypy_final.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/mypy_final.receipt.json) |
| mypy_first | 2026-10-15T14:40:41+08:00 | 2026-10-15T14:40:49+08:00 | 0 | [mypy_first.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/mypy_first.receipt.json) |
| pg_final | 2026-10-15T14:43:40+08:00 | 2026-10-15T14:44:28+08:00 | 0 | [pg_final.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/pg_final.receipt.json) |
| pg_first | 2026-10-15T14:41:45+08:00 | 2026-10-15T14:42:32+08:00 | 1 | [pg_first.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/pg_first.receipt.json) |
| ruff_final | 2026-10-15T14:42:19+08:00 | 2026-10-15T14:42:19+08:00 | 0 | [ruff_final.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/ruff_final.receipt.json) |
| ruff_first | 2026-10-15T14:40:41+08:00 | 2026-10-15T14:40:41+08:00 | 1 | [ruff_first.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/ruff_first.receipt.json) |
| source_commit | 2026-10-15T14:44:53+08:00 | 2026-10-15T14:44:53+08:00 | 0 | [source_commit.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/source_commit.receipt.json) |
| sourcewriter_regression | 2026-10-15T14:45:18+08:00 | 2026-10-15T14:45:48+08:00 | 0 | [sourcewriter_regression.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/sourcewriter_regression.receipt.json) |
| static_final | 2026-10-15T14:44:03+08:00 | 2026-10-15T14:44:03+08:00 | 0 | [static_final.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/static_final.receipt.json) |
| unit_all | 2026-10-15T14:42:19+08:00 | 2026-10-15T14:42:39+08:00 | 0 | [unit_all.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/unit_all.receipt.json) |
| unit_final | 2026-10-15T14:43:39+08:00 | 2026-10-15T14:44:01+08:00 | 0 | [unit_final.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/unit_final.receipt.json) |
| unit_red | 2026-10-15T14:38:52+08:00 | 2026-10-15T14:38:54+08:00 | 1 | [unit_red.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/unit_red.receipt.json) |
| unit_target | 2026-10-15T14:39:30+08:00 | 2026-10-15T14:39:32+08:00 | 0 | [unit_target.receipt.json](../runs/recovery_r04_vendor_cursor_20261015/unit_target.receipt.json) |

## 问题台账与剩余边界

1. VCUR-01：真实page忽略导致重复页，来源为主控14:24:49+08观察；此包源码5ca5664修复，
   最终19PG/575unit验证，独立复验及真实GET仍待主控执行，状态待复核。
2. VCUR-02：新增PG测试混入索引任务；14:42:32+08首次失败，修正查询类型；
   14:44:28+08复跑19 passed，状态已修复，失败日志保留。
3. VCUR-03：作者14:44:53+08调用链检查发现 http_transport.py:103–117 将响应头转dict前
   guarded_headers未包含link，同大小写重复Link可能被覆盖；服务层已拒组合重复next及Link/link，
   无法恢复上游丢失字段。已交主控唯一所有者追加共享层负例与修复，未越权修改。
   根因影响真实网络入口，整条分页验收仍依赖该修复及独立复核，未宣称关闭。
4. VCUR-04：legacy page>1没有可证明cursor转换；已明确blocked，历史保留，
   主控后续R06显式管理恢复。非本卡自动清库或伪造续采成功。

秘密范围：作者未加载产品密钥；PG runner只内存读取获批root600测试连接，日志全DSN/密码与
密码8字符片段扫描为0（不输出值）；源码staged通用secret pattern为0。主控集成时还需其
完整产品凭据扫描，作者没有索取其他工作流秘密。实际本包付费API调用0，编程Agent费用unknown。
测试资源清理见resource_close.json；保留专用DB与root600连接供独立review，不停共享服务。

## 交付结论

此修复切片awaiting_review，不签R04/T10/T12/整个G-B，不push。
下一步主控集成源码、修复共享重复Link丢失、原独立reviewer定向复验，在未占用live流做真实采集。
U01来源完整采集证据因本问题得到可复验修复，但来源广度/R06恢复管理/前端/模型与正式评分不在本包声明内。
报告证据截止时间：2026-10-15T14:47:28+08:00；本次修订：首次封存，以实际命令与失败记录为准。

证据封存更正：2026-10-15T14:48:01+08:00首次提交中，复制的seal_evidence.py因命令引号错误
未更新旧报告名/基线，索引误引用上一个包，未影响源码或测试结果。随后显式固定本包源码5ca5664、
基线7184及本报告路径，重新封存；旧提交保留历史，不拿错误索引背书本包。
