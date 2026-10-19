What this change does: 本变更新增 `extract_model_dimension`，使一个任务只提取 ATLAS、版本、文献或 PoC 中的一个维度，默认输出预算 1024，最多一次模型请求且不修复格式。旧四维入口的签名、默认总预算 4096、维度顺序和已有证据门禁保持。

记录时间：2026-10-16，实际命令时刻均为上海时区 `+08:00`，见独立 run receipts。审查人 `/root/r07_single_model_dimension_independent_review`，未参与实现、未采用作者结论作为证据。使用 Ponytail-review 5.2.0，先读合同与调用链，再复跑和补充反例。

本报告只放行这个未接产品调用方的内部接口切片。没有发现需要作者修复的可复现缺陷；不登记 `accepted`，不放行整 R07、原 T 卡或 G-C。整系统九维富化、父 worker 和持久 jobs 仍需后续实现及独立验证。

## 冻结身份与边界

| 项目 | 本轮实际核对值 |
|---|---|
| 审查材料 | `b05e63462f1b513eabc183d0a8d42b03196696d2` |
| 审查代码 | `d8a3189bb7bc1cfde24825f5478920e37eac9556` |
| 有效 diff 基线 | `63e4cafe1363530eb08cdfe7fec56cfc07a81b8a` |
| 前置等价性 | 63e4caf 的 generation 源码及派发前超时测试，与已审前置 `47c47bc2b5d537166ee47a01c2ab14c035466e3d` 的对应 Git blob 逐字相等；本变更未修改 |
| 自有工作树 | `D:/wt/r07-single-review1`，新建 detached b05e634 |
| 作者工作树 | `D:/wt/r07-single-field`，独立 `git status --porcelain=v1` 空输出、exit 0 |
| 自有解释器 | `D:/wt/r07-single-review1/backend/.venv/Scripts/python.exe`，Python 3.12.13；`uv sync --frozen --project backend --group dev --python 3.12` exit 0 |
| 独立材料 | `reports/runs/recovery_r07_single_model_dimension_review1_20261016/` |

已读 AGENTS、执行图、恢复 R07/R03、T18/T19/T20、03/04/05/06 合同、CR-R07 候选/v3 合同、冻结 progress/handoff 与作者报告。主仓已有修改保留；本轮未更改业务、原测试、锁、配置、认证、数据库、公共 schema、进度或 Git 属性，未 spawn、push 或启动服务。实际新增仅本报告、自有运行脚本、独立测试与材料。

63e4caf→d8a3189 实际仅四文件：`backend/src/ai_intel/enrichment/model_fields.py` 和新单维 unit/contract/security 三份测试。独立 diff-check exit 0。`review_source_unchanged` 再核对 b05e634 的 source/tests/uv.lock/pyproject/.gitattributes，exit 0。

## 行为审查

输入仅接受严格字符串 `atlas/versions/literature/poc`。空、未知、多维、重复维度容器在 0 DNS/0 transport 时抛固定 `field_dimension_invalid`；单维预算严格 int、范围 1..8192，bool、float、NaN、Infinity 等抛 `field_call_policy_invalid`。布尔策略参数也拒绝整数和字符串。

单维入口对真实 client 的 `total_timeout_seconds > 20` 立即拒绝，未修改 client、gateway 或 semaphore。独立反复拒绝及真实双线程共享一个许可的探针均通过；占用许可等待超时返回单维 `model_concurrency_timeout`，无网络和伪造调用元数据，释放后下一次请求成功。固定时钟证明 DNS 消耗同一个生成 deadline；DNS 后到期是 `model_network_timeout`，不重置预算、不重试。这里验证现有生成 deadline，并不承诺 Python 进程或后续 CPU 候选校验的 20 秒硬终止。

旧入口仍传 `FIELD_DIMENSIONS=(atlas,versions,literature,poc)`，默认 4096，按 floor(total/4) 分配；其 60 秒 client 仍可使用。单维直接将一个元素传私有实现，早期 budget/unconfigured/egress/empty/ATLAS 缺固定 taxonomy 的结果只含所选维度，没有先四次调用后过滤。私有外发拒绝、真实 client 要求、固定修订、资产清单拒绝、来源/完整行/条件校验与错误分类均仍走原路径。

四种 provider 分别实际经过 `GenerationClient.generate → NetworkGateway.post_json → _bounded_fetch → _fetch → PinnedHttpTransport.request → _HttpResponse`。独立 82 项只替换离线 resolver 与最底层 `_PinnedConnection`，没有替换 generate、post_json 或 transport.request。成功、格式错、连接错、超时、401、429、503、302 的各次执行均最多一个 POST，无格式 repair、失败重试或跳转；保留失败 outcome、provider/model/prompt/schema、usage/hash 和 `fee=unknown`。这些是合成 connection 边界计数，外部 DNS/socket/TLS/供应商 live 次数为 0。

候选仍为 `MODEL_HYPOTHESIS/PENDING`，无证据保持 pending 而非 not_found；ATLAS 仍要求官方路径中的完整固定版本与 source_version 对齐。版本必要条件、否定和未知比较、文献标题/URI 身份与 partial 限制、PoC 仅 candidate_found 沿用共享校验。类型、引用和 hash 相符不证明事实支持；没有发布事实或运行 PoC。合成 taxonomy commit 形状不是官方下载真实性证据。

父 worker 尚未接线。后续调用方须固定四个子任务、各默认 1024、批准的独立 client `<=20s` 且满足工具预算，父默认合计仍 4096。接口允许显式更大的单维预算，不等于提高父默认预算或授予费用授权。

## 独立执行记录

下表均由独立工作树的真实 JUnit/receipt 读取，最终各组均 0 fail/error/skip。重叠调用链上的回归次数不合并成不同能力数量，不是准确率、评分分母或性能指标；没有 whole-project coverage 声明。

| 检查 / receipt 前缀 | 实际 +08:00 开始—结束 | exit | 结果 |
|---|---|---:|---|
| `new_103` | 03:06:57.804431—03:07:08.614289 | 0 | 新 unit 41 / contract 44 / security 18，共 103 passed |
| `original_236` | 03:06:57.804431—03:07:11.012337 | 0 | 原指定十一文件 236 passed |
| `original_47` | 03:07:27.143421—03:07:31.299669 | 0 | 两份旧独立探针 47 passed |
| `root_causes_46` | 03:07:27.554127—03:07:32.470702 | 0 | 旧根因边界 46 passed |
| `gateway_32` | 03:07:47.870951—03:07:51.268893 | 0 | 旧四维 Pinned transport 32 passed |
| `generation_17` | 03:07:47.760777—03:07:51.080795 | 0 | 共享派发前超时 17 passed |
| `independent_probes_recheck` | 03:09:15.115665—03:09:18.808189 | 0 | 新自拟单维 Pinned/负例/并发/deadline 82 passed |
| `ruff` / `format` | 03:07:47.824675—03:07:48.429648 | 0 / 0 | 作者四 source/test 文件全部通过 |
| `mypy` | 03:07:47.913628—03:07:51.602598 | 0 | model_fields 业务模块通过 |
| `source_diff_check` | 03:10:46.343188—03:10:46.455280 | 0 | 有效基线至代码 SHA 的 source/test diff |
| `frozen_audit_sealed` | 03:11:12.888592—03:11:35.378073 | 0 | 164 artifact raw/blob、4 source identity 与属性审计 |

实际命令的完整逐参 `argv`、`cwd`、开始/结束、退出码与冻结 SHA 保存在同名 `*.command.json`，stdout/stderr/JUnit 独立保存。主命令如下，未改仓库 pytest 默认覆盖率门；有界 review 运行显式 `-o addopts=`：

```text
cwd=D:/wt/r07-single-review1/backend
D:/wt/r07-single-review1/backend/.venv/Scripts/python.exe -m pytest -o addopts= -q tests/unit/test_r07_single_model_dimension.py tests/contract/test_r07_single_model_dimension_contract.py tests/security/test_r07_single_model_dimension_security.py --junitxml=D:/wt/r07-single-review1/reports/runs/recovery_r07_single_model_dimension_review1_20261016/new_103.xml

cwd=D:/wt/r07-single-review1
backend/.venv/Scripts/python.exe -m pytest -o addopts= -o "pythonpath=backend/src backend" --import-mode=prepend -q reports/runs/recovery_r07_single_model_dimension_review1_20261016/test_single_dimension_independent.py --junitxml=reports/runs/recovery_r07_single_model_dimension_review1_20261016/independent_probes_recheck.xml
```

`run_check.py` 仅将冻结原回归 receipt 的解释器/工作树/JUnit 目标改为自有路径；未改测试内容。`original_236.command.json` 列出十一文件，旧 47/32 的导入根按冻结测试依赖显式配置。Ruff=`python -m ruff check` 四文件；format=`python -m ruff format --check` 同四文件；mypy=`python -m mypy src/ai_intel/enrichment/model_fields.py`，cwd 均 backend。

## 原始失败与材料核验

作者 manifest 本体 SHA-256 独立核实为 `9d267434cca417d4a0a8eb3216956473f91b98b49148711e7b9dcb5950d85c0b`。164 件作者 raw 的 size/SHA 与冻结 Git blob 身份/size/SHA 全匹配；4 source 对应 d8a3189 blob 不变。审查 checkout 的 `.gitattributes` 与报告可能按 Windows checkout 转 CRLF，不能据此谎称所有 checkout 字节与作者 raw 相同。`frozen_audit.json` 分别登记作者 raw、review checkout raw 与 blob；author raw 的逐字核对没有用换行归一化冒充。

已核对原属性 blob 完整前缀保留，新增只有本作者 run/** `-text` 加 11 个具体 raw log/XML `-diff`，清单逐字等于 `attribute_adjustment.json`，没有扩大到源码/测试或全仓。材料 diff-check 仅恢复原先 `cr-at-eol`，其他空白检查保持，exit 0；本 reviewer 未修改 Git 属性。

作者失败 XML 及 raw 均保留并重新解析：original_red 103 failures；green_draft 66 failures，其中 61 tuple/list 断言、4 空 revision_ids context、1 超时码预期；green_draft2 5 failures；new_draft_green 1 concurrency/network 超时触发位置差异；baseline_red 3 collection errors；baseline_red2 102 failures/1 pass，102 项均为原模块无单维入口；final_review_32 1 collection error。旧四维 tuple 契约、有效非空 context 与固定时钟的修正有具体原因，未改业务来迁就测试、未改金标/分母/阈值或改 skip。独立 baseline red 实际 exit 1、102 failed/1 passed/0 error/skip，与上述失效位置相符，命令与结果另见本 run 的 `independent_baseline_red.*`；只在测试进程载入 63e4caf Git blob，不改工作树源码。

本 reviewer 也保留三类仪器失败：`cbm_schema_missing_project` exit 1（CLI 要求 project）；`independent_probes` exit 2、1 collection error（pytest pythonpath 错用逗号，改为空格分隔后 82 passed）；`frozen_audit` exit 1（错误要求 Windows checkout 的 .gitattributes raw 等于作者 raw，修正为分别核对作者 raw 与 checkout/blob 后通过）。失败未删、未覆盖，也未算业务测试失败或成功。manifest/summary 包含这些原始输出。

## CBM 与调用方检查

使用官方 WSL Ubuntu-22.04 root CLI `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` v0.11.0，先读 help/schema；独有 cache `/tmp/dianzi-cbm-r07-single-review1-20261016`，project `r07-single-review1-src`，allowed root 仅本 WT backend/src，fast/persistence=false。索引 1391 nodes/7057 edges，not-indexed/partial/unusable 都为 0；未索引 reports、holdout、秘密或资产清单。

独立取得 schema、architecture、单维/旧入口/GenerationClient.generate/PinnedHttpTransport.request 的 qualified both-direction traces，并用 `rg_callers`、`rg_export_and_budget` 查 source/tests/导出。新旧入口在 source 均无产品 caller，只有测试调用；私有实现只有新旧两个入口。GenerationClient 的其他真实问答 caller 保留。CBM 的 Pinned request caller=0 是 callback 分析限制，已结合 network 源码和独立实际 transport 路径交叉核验，不据此误判其没有调用。

## 验证层、合同和评分证据

| 层 | 本接口切片状态 | 实际限制 |
|---|---|---|
| unit | passed | 输入、状态、预算与 deadline 的限定离线行为 |
| contract | passed | 四种 provider codec、单维返回/元数据与旧四维回归 |
| security | passed | 私有外发、权限升级字段、资产清单和输入门禁 |
| integration | not_run | 无 PG、worker、服务或产品调用方 |
| frontend | not_run | 未执行前端 |
| e2e | not_run | 无真实产品全链路 |
| live | not_run | provider/source/taxonomy 下载均未外网；后续仍 blocked_live |
| manual | not_run | 无人工事实支持、金标或演示验收 |

六类工程检查中仅 unit/contract/security 执行；integration/frontend/e2e 未跑，八层再加 live/manual 均不能推定通过。正确性、安全、并发、测试、速度与简化审查未发现本变更新增的具体阻断；并发只是进程内 client 许可证明，不等于跨 worker/PG 负载或吞吐验收。

R07 六项验收只覆盖本切片对应的四模型维度正例、无证据保留未知、单维失败隔离和候选证据边界；九维产品/适用性/评分冲突并存仍须后续全链路核验。F2/P2 本轮证据是单任务单维、预算/调用上限、条件与候选边界；R1 只保留文献固定身份与 partial 的回归。没有准确率、召回率、持续运行、真实来源广度、费用、吞吐或人工评分证据。

未发现本切片需要修改的合同/计划偏差。最小下一步是主控收到本冻结报告后，另行接父 worker 的四个子任务、PG 任务/元数据/发布/重放与 API，再取得独立集成和授权 live 证据。不能用本意见为整 R07/G-C 签通过。

Verdict: Ship. 仅 `d8a3189` 单维接口代码与 `b05e634` 配套冻结材料的离线 unit/contract/security 切片。

Not checked: 真实供应商和来源、官方 taxonomy 下载真实性、费用、PG/worker/API/UI 接线、跨进程恢复/吞吐、语义支持与人工/最终评分。
