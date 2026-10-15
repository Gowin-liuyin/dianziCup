# R05 · 共享生成客户端派发前预算耗尽修复

状态：awaiting_review；实现：complete（本次共享错误边界修复范围）。记录时间：2026-10-16T02:16:27+08:00。作者：/root/r05_shared_generation_predispatch_timeout_fix；独立评审未执行，作者不签 accepted。

工作树：`D:/wt/gen-timeout`；分支：`codex/r05-shared-generation-predispatch-timeout-fix`。基线 `595a13197a2c1bba6ad79957f8fde3750ba2a6c6`；代码冻结 `47c47bc2b5d537166ee47a01c2ab14c035466e3d`。材料提交在代码冻结后单独产生，不改变产品源码。

## 问题、合同与输入输出

依据 AGENTS、恢复 R05/R07/R09、原 T18/T31、03 数据与 05 API 错误合同，并采用 Ponytail 5.2.0 full。输入是已通过来源外发、模型批准、schema 和请求校验的 `GenerationRequest`，整次生成仍使用同一 `RequestDeadline`。输出必须沿用共享客户端的 `GenerationFailure`，保留固定失败码、已有 attempts 和未知费用语义。

原源码 `generation.py:409` 在 `try/finally` 之前调用 `deadline.remaining_seconds()` 来计算 semaphore 等待时间。固定单调时钟 `100 → 103`、预算 `1.0s` 时，这个调用直接抛出 `NetworkTimeoutError`。此时 acquire 未执行、没有 slot、没有 DNS/POST，也没有实际供应商响应用量。调用方只承接 `GenerationFailure`，因此原始底层错误穿透业务边界。新增测试亦检查恰好到期的 `3.0s`，避免依赖真实 sleep 或微秒浮动。

修复给 acquire 周围增加窄 `except NetworkTimeoutError`，抛出 `GenerationFailure("model_network_timeout") from None`。`attempts=()`，不构造假的 attempt、token 用量或 0 元成本。`acquire=False` 继续返回 `model_concurrency_timeout`；slot 尚未获得时没有 release。原取得 slot 后的 `finally` 原样保留。OpenAI、Anthropic 和两个 DeepSeek wire 共用这个分支，编码、模型标识、最大调用、token 与时间上限均未调整。

## 调用影响与边界

官方 WSL portable CBM 0.11.0 对本工作树 `backend/src` 建独立索引，再按官方 schema 查询完整限定名。冻结索引 1340 nodes / 6737 edges；精确 inbound trace 为 `answering.grounding.generate_grounded_answer` → `answering.service.GroundedQuestionService.ask`，共 2 个递归入向调用。初次省略 project 前缀的 trace 真实失败；`search_graph` 的初始 glob 无结果，改用 name/file regex 得到完整限定名。失败日志全部保留，不将失败查询称作成功。

`rg` 交叉检索自己的 models、answering、enrichment、配置和 sibling 冻结候选：QA 的 `grounding.py:215/241` 生成与核验两次调用在 `:261` 转换 `GenerationFailure`；R07 `D:/wt/r07-model-fields-two-root-causes-fix` 的 `model_fields.py:164/179` 将共享失败变为对应维度失败；R09 `C:/Users/yinha/.codex/worktrees/r09-knowledge-cards/dianzi` 的 `card_extraction.py:292/297` 转为 `CardExtractionFailure`。R07/R09 源码不在本基线，只读核对，未复制、修改或计为该包的端到端验证。

其它 models 实现也已检查：`clients.py` 是纯合同校验/fixture；`semantic.py` 使用自己的 `SemanticTimeoutError`、非阻塞 worker 锁与 finally，没有 `RequestDeadline.remaining_seconds()` 同根因漏归一。没有证据支持扩大本轮 models 修改范围。通用 `NetworkGateway` 的预 acquire 超时仍属于其公开 `NetworkTimeoutError` 协议，进入生成调用 attempt 后已有 typed catch；未改通用网络层。

业务改动仅 `backend/src/ai_intel/infrastructure/models/generation.py`（5 行新增、2 行替换）；直接新增 `backend/tests/unit/test_r05_generation_predispatch_timeout.py`（17 参数化案例）。报告、运行脚本、日志与 manifest 均在本报告和专用 run 路径。`.gitattributes` 只精确追加该 run 的字节保留规则，用于可复核原始日志；不禁用代码检查。未改 cards/model_fields/publication/PG/worker/API/domain/schema/locks/deps/auth/progress。

## 实际验证

专用离线环境使用锁文件：`uv sync --offline --frozen --no-install-project --project backend`，随后 `uv sync --offline --frozen --all-extras --no-install-project --project backend`。Python 3.12.13，共 91 installed distributions；无依赖/锁文件变更、无模型下载。以下 pytest 使用 `--no-cov` 跑定向回归，本次没有声明全项目覆盖率。

| 命令 / 证据 | SHA 与结果 |
|---|---|
| `python reports/runs/recovery_r05_generation_predispatch_timeout_fix_20261016/check.py baseline` | 基线 595a131；272 passed，0 fail/error/skip，exit 0 |
| 同脚本 `red` | 原产品源码 595a131；17 cases，9 failed / 8 passed，exit 1；9 个失败均为裸 `NetworkTimeoutError` |
| 同脚本 `green` | 未提交补丁工作树；17 passed，exit 0；该记录 HEAD 仍是基线，不能称为冻结验证 |
| 同脚本 `frozen_regression` | 冻结 47c47bc；289 passed，0 fail/error/skip，exit 0：219 unit、46 contract、24 security |
| 同脚本 `ruff` / `format` | 冻结 47c47bc；models 与新测试，均 exit 0；6 文件符合格式 |
| 同脚本 `mypy` | 冻结 47c47bc；全部 `src`，101 source files，exit 0 |
| 同脚本 `cbm_index_frozen` / `cbm_schema_frozen` / `cbm_trace_frozen` | 冻结 47c47bc；均 exit 0，索引路径/入向调用见各 JSON / log |
| 同脚本 `caller_search_frozen` / `diff_check_frozen` | 冻结 47c47bc；均 exit 0 |

每个运行记录有实际 command array、cwd、开始/完成时间（+08:00）、退出码、SHA、日志与 JUnit 计数。运行脚本会拒绝覆盖已有 evidence label。首次新增测试 Ruff 有 2 个 E501 长行，格式化后修正；该初始终端观察单独留存，最终冻结检查才标 passed。应用 managed worktree 创建因旧报告长路径失败，随后用短路径与单命令 `-c core.longpaths=true` 创建成功；未改变主工作区或全局 Git 配置。

新 17 案例包含四 provider 在已过期/恰好到期前无 acquire、无 release、零 DNS/POST、空 attempts、安全固定异常及同一 client 后续成功（`certain=False` 不丢失）；四 provider 等待返回 False 保留并发超时；四 provider 已取得 slot 后耗尽保留实际 attempt、未知 usage/fee 并只释放一次；QA 把派发前共享失败转换为 `GroundedAnswerFailure`，没有核验第二次调用。复用已有生成/QA回归检查注入仅为 untrusted data、私有外发拒绝、凭据输入/输出脱敏、坏 wire/JSON/schema、两次调用/一次修复上限、共享 deadline 与 token/字节预算、并发占用和 socket fixture 超时分类。只新增缺失的共享根因回归，不改已有期望或独立 reviewer 测试。

## 未运行与评分证据

本次范围 unit/contract/security 为 passed；integration、frontend、e2e、live、manual 都是 `not_run`。没有真实网络、真实 DNS/POST、供应商凭据、真实模型、资产、PG、浏览器或外部费用操作。transport/socket fixture 仅为隔离 security/contract 验证，不计 live。真实模型费用未核实，仍为 unknown；新增失败没有响应用量，不制造成功结果。R07/R09 发布持久化和真实作业不由本补丁验收。

T18/R05 的 F2/F3/A1/E1 超时错误可见与预算边界有本次证据；T31 的 QA 模型不可用失败传播有 unit 证据。R07 单维失败及 R09 卡抽取受共享补丁影响，其完整功能、真实样本/问答/评分、原任务整卡和恢复阶段均不提升。合同与计划无行为放宽；文件所有权要求优先，未更新 root 专属 progress。

下一步由 root 指派全新、未参与实现的 independent reviewer，固定代码 SHA 47c47bc 与材料 manifest 复跑，并在 R09 候选上重放原独立失败案例。作者本轮结束，无 push、自审或 accepted。

未检查真实模型调用和全链路发布；风险限于这些尚无本次运行证据的边界。
