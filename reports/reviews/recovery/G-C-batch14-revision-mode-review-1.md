# G-C · 批次14修订模式首次独立审查

首次创建：2026-10-17T04:10:01.427+08:00（Windows文件创建时间实读；最终证据截止见封存记录）

任务：R06/G-C revision-mode 读取切片；状态：**needs_changes**。本报告不修改任务状态，不签整 R06、R07 或 G-C。

What this change does: 本变更从被读取修订的 `source_metadata` 分类 fixture/live，并拒绝未知、混合或与内部消费者预期不符的输入。两个公共 router 明确允许如实展示同质历史；R07 在初次读取和终态重读检查模式，R01 在查询/迁移异常路径也释放 Engine。

## 固定版本与独立性

- Root candidate：`48f96b5ba35d19f5e26868a2bccd5b124afb2bd0`；parent：`bc089809c03472582f6256b495a6f9a2a308a5d2`。
- 独立分支 `codex/g-c-batch14-mode-review-1`，工作树 `D:/dianzi-worktrees/g-c-batch14-mode-review-1`，从该 SHA 创建。业务、合同、progress、frontend 均无 diff；只有本报告和直属审查 helper/log。
- 25 个输入 manifest 条目的 candidate Git blob 均与相应作者 blob、冻结 raw SHA256 相同。该新 Windows checkout 将全部 25 文件转成 CRLF，故 checkout raw SHA256 与 LF 输入不同；逐项确认只有 CRLF 差异，没有把 raw 相同与 clean/blob 相同混写。详见 `source_and_count_audit.json`。
- 原 24 诊断 candidate blob 与 `5716a1d15c2eb60a13b2b4e05cbc6b4e25b0acfa` 逐字节相同。重放原函数/断言，通过冻结测试的 server `False` 注入和旧 `_summaries` 私有 tuple 适配；这 24 例属于 fixture 单元证明，不是实际 HTTP/PG 或在线来源。
- 已读 AGENTS、执行地图、R06/R07 卡、API/data/evaluation 合同、progress、`CR-R06_revision_mode_read_projection` 和 Ponytail 5.3.1 review。原前置、未知语义、历史、ACL、评分分母保持。

## Must fix

1. **新 PG 事件模式两例没有到达读取逻辑**（`backend/tests/integration/test_r06_revision_mode_read_pg.py:218`，M01/P2）

   - What this is：该测试应把显式 fixture/live 来源持久化，然后从真实 PG 回读事件详情，检查返回模式。
   - Problem：`source_response("nvd_ollama")` 的返回类型在 `backend/tests/r06_source_worker_fixtures.py:114` 为 `(bytes, content_type)`；整个 tuple 被传入 `SourceResponse.body`。`backend/src/ai_intel/ingestion/source_documents.py:240` 按现有输入边界拒绝非 bytes，抛 `SourceDocumentError("source response byte limit exceeded")`。固定版本真实 PG8 为 **6 passed / 2 failed / 0 skipped**，两个事件例均未进入 `KnowledgeReadService.event_detail`。这不是 PG 环境缺失或产品字节上限需要放宽。
   - Fix：解包 `body, _content_type = source_response("nvd_ollama")`，只把 body 传给 body；保留原白名单 URI、两个模式参数和全部断言。第二项是媒体类型，不能改作 URI。
   - If we skip it：offline、collect 和新 helper 的模式证明无法替代这两个冻结 PG 回读验收；本切片缺失要求的真实事件检查。

失败 nodeid：`test_event_detail_keeps_same_pg_source_mode[fixture]`、`[live]`。原始 stdout SHA256 `fe6876df4e9414f4c641b1e496c3f3537a6000ae25490cae9738c2e1ebfbec16`；XML SHA256 `5473df532fd4c89312fbfd116eeb15971eea579aab67420ca4cfe0c3a7fce6e0`。均位于本报告同名 own run 的 `pg_modes_and_default.*`。该组合还包含审查人额外探针的同一输入接线错误，所以组合原结果为 6 passed / 3 failed；不能把额外一红记成第三个产品缺陷。

## 已核业务与调用链

`revision_mode.py` 仅认可 trusted-source-runtime-v1 的 live/fixture，历史无策略的显式 fixture 仍保守认可；缺失、None、非字典、未知策略、伪 live 都拒绝。空集合只保留配置模式，不能证明存在真实输入。2001 输入明确失败，不从历史中删行或偷偷过滤为成功。

Document detail 使用所选修订的模式；list/revisions 核当前实际返回页。事件 list 核可见 active revision association；detail 核完整可见历史和额外 claim/assertion 修订。evidence SQL 增加 span 自身修订的元数据。公共两 router 是唯一 `require_expected_mode=False` 服务端入口；客户端 query 不改变这个配置。

已逐项源码追踪 `retrieval/service`、`retrieval/hybrid`、`answering/service`、`answering/evidence_bundle`、`investigation/tool_gateway`、`investigation/read_adapters`、workflow、recommendation loader 和 R18 producer。它们保留默认严格匹配，且在 citation/embedding 或无 mode 的输出转换前读取并校验实际修订。新负例亲跑确认 live 内部 reader 消费 fixture 被拒。

另由只读子审核 R07：请求修订、claim assertion 与 evidence 父修订集合保持；parents 全字段指纹包含 source_metadata；835/888 行的两处检查分别在内容 IO 前和锁后重读之后，随后仍检查输入变化。值支持、qualifier、同 claim owner、三 UUID、current、unknown/conflict 和输出围栏未放宽。唯一生产链仍为 workflow → source report node → proof reader，证据投影仍严格。真实 R07 并发/锁整套仅 collect，不把静态结论计为 PG 验收。

## 实际命令与分层结果

所有命令 cwd 为本 WT `backend`（helper 从 WT 根启动），Python 为 `D:/dianzi/backend/.venv/Scripts/python.exe`；实际 argv、+08 起止、退出码、PID/birth、原 stdout/stderr/XML 均记录在 `reports/runs/g_c_batch14_mode_review_1_20261017/`。

| 范围 | 实际命令/证据 | 实际结果 |
|---|---|---|
| unit/contract core | `python review_checks.py core`，实际为 pytest 所列 10 文件 `--no-cov -q` | exit0，173 passed，0 fail/error/skip；含原24重放、R07模式/强证明、R18边界、R01 finally及辅助负例 |
| related unit/contract | `python review_checks.py related`，实际为 pytest 所列7文件 | exit0，139 passed，0 fail/error/skip；与core不同文件、XML case keys交集0，distinct **312**，不累计重复轮次 |
| PG 收集 | `python review_checks.py collect` | exit0，94 collected；只有收集，旧PG不计执行通过 |
| integration | `python pg_controller.py`，实际 pytest 新PG8 + 额外默认探针 | exit1，6 passed/3 failed/0 skip；作者8单列6/2，额外探针1红见上文 |
| Ruff | `python review_checks.py ruff` | exit0，22个切片文件 |
| format | `python review_checks.py format` | exit0，22 files already formatted |
| mypy | `python review_checks.py mypy` → `python -m mypy src` | exit0，194 source files，无类型问题；04:01:52.993–04:02:20.967+08 |
| security | 只在额外PG探针实际检查匿名401、权限移除403及实际PG登录；正式security suite | **not_run**，局部ACL检查不能签整套安全 |
| frontend/e2e/live/manual | 无这些层的命令 | 全部 **not_run**。数据均为显式合成输入，真实 PG 不等于真实来源或模型 live |

Root783是待独立验证的整合报告；本审没有亲跑全783，不能据此替 Root签全批。R14预算及R10 graph配置由别的切片审查承担。

## 真实资源与仪器红

第一 PG attempt 04:05:07.770–04:05:13.094+08，exit1/9 setup errors。审查 controller 的 DIANZI_TEST_RUN_ID 与 `test_dianzi_<run_id>` 不匹配；这是仪器输入错误，目标连接峰0，未执行业务。原件保留为 `attempt1_*`，只修 run_id，不改产品、fixture Oracle 或测试 outcome。

第二窗口 04:05:40.048–04:06:04.029+08，23.985s。自有库 `test_dianzi_r06_mode_be4a61a4f6ae42`，native OID **10452998**，native COMMENT SHA256 `2d25c9189801784b8e0adff4b163b6b49bd7e0e3a68b817c86101e514b92f3de`；真实 exact9 字段为 project/kind/run_id/owner/product_sha/maximum_seconds/queue/redis_prefix/created_at。marker 的旧 kind 文案保留受审模板，但本运行明确是合成输入 integration，不能据该文案称来源 live。

亲核 test role `rolsuper=true`、`rolconnlimit=-1`、server `max_connections=50`，每 backend PID/birth/创建 phase/caller 在 `pg_controller.command.json` 和 `pg_backend_creation.jsonl`。business target 峰 **2**，加父库 sampler 1 的真实 owned 总峰 **3**，all-server client峰也是3；profile2是业务 soft budget，非物理/总连接2。采样保留 all_server_client_rows/count，包括 sampler，没有过滤后宣称总2。Win+Linux合计峰6/16；本轮未启动自有 Linux 服务。只从已授权 DPAPI 用冻结 load_parent_url 捕获内存秘密，child stdout不输出秘密引用。精确DSN/password/8字符片段扫描0。

cleanup 先确认原 native OID+完整COMMENT全文及 target sessions0，再 DROP 唯一自有nonce库；parent真实关闭，新子进程残留0。不触 Source固定 OID10451302/10434264，不改共享角色/父服务、不降级、不 force terminate，不启动模型/FOFA/paid、browser、Redis或MinIO。两窗口均在授权240秒内；交回主控后等待补验资源。

CBM 独占窗口04:02:46.008–04:03:19.149+08。亲跑官方0.11.0 `--help`、fresh source-only index、schema、trace，均exit0；2692 nodes/15984 edges，Win+Linux合计峰9/16、Linuxafter0。一次尝试 `cli --json help` 实际报 unknown tool、exit1，原log保留；真实 `--help` 已给有效工具清单。新cache只索引该WT backend/src，未接触secret/holdout。图29多跳caller含PDF歧义，实际6直接caller经rg核对，不能把图全部当真实调用事实。

来源审计首次 raw==Gitblob 断言因CRLF过滤exit1；纠正为分别记录 raw/Gitblob/CRLF，与作者和candidate逐项比对。该仪器红不计产品缺陷，不改源码换取同hash。

封存 staged diff 首次因原始 pytest 红日志/XML的 trailing whitespace 报非零；原输出不改。仅本 own run 内 `.gitattributes` 将 log/XML/jsonl/stat 按原字节保存并作为生成证据关闭文本diff，JSON/helper也保留原换行。第二次检查因 Windows 生成 JSON 的 CRLF 报非零，再按仓库既有做法定点允许 cr-at-eol，其他空白规则保留。此规则不作用于产品源码或检查命令，后续完整 staged diff 再核，不能把两次红写成通过。

## 合同、评分证据与后续

本次没有新增契约偏差、迁移、依赖、金标或计分分母改变。与 CR 相符的生产行为在已到达路径未发现另一个具体缺陷；M01阻断新PG事件两例的验收。F1/E1的模式真实性、历史不覆盖、失败边界已有局部证据；F2/P2的强证明仅本切片自动/静态证据，不能推导富化准确率、来源覆盖、时效、六小时或阶段通过。

下一步：作者以最小测试输入修复冻结新 source/material；由原身份定向复核新的8PG及默认事件/2000边界，不修改原红记录。默认 probe 后续补验若获资源，其结果另追加，仍不替代原冻结版本的两红。

Verdict: **fix M01 first**。Not checked: 完整旧PG、R07真实并发/锁、formal security、frontend/e2e、来源/模型 live、人工和全783回归。
