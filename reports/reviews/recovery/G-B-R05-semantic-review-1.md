# G-B / R05 semantic-runtime 与共享资源限额 · 独立初审 1

**最新定向复核：`1e77c0d83a95f22ffd6457c2bb432eb2c0538f9e` 的 Must 1 已独立关闭，模型运行包与未变 helper/PDF 的本次范围可 Ship；仍 `not_integrated`，不签整 R05/G-B。** 下文保留 bfea9fe 初审红例，最新命令与边界见文末复核附录。

本变更新增真实本地 E5 embedding 与多语种 CrossEncoder 重排，以固定文件哈希、模型空间版本和短生命周期进程隔离输入与输出；PDF 改用同一原生资源限额。**结论：先修复 Must 1。** 冻结包建议 `needs_changes`；本报告不修改状态，也不签整 R05、T18、G-B 或任何评分档次。

审查者：`/root/r05_semantic_independent_review`，未参与实现；使用 Ponytail 5.2.0 full 与 review。证据窗口：2026-10-15T15:41:44–15:53:36+08:00。主控唯一负责集成、状态与 push。

## 固定范围与隔离

| 项目 | 实际值 |
|---|---|
| 被审代码 SHA | `bfea9fe95ae14211948cd3fdcc505ae22e77ad24` |
| tree | `27fb635dc41dee6734b48f22520b9eba8a2968c8` |
| 共享 helper SHA | `77add6074e44be63244f2c5790fd74389afbcd79` |
| 基线 | `31c2866ff19227e5f6ee24f1f966660c0d4ba383` |
| 独立 Codex 工作树 | `C:/Users/yinha/.codex/worktrees/r05-semantic-independent-review/dianzi` |
| 独立 venv / uv / coverage / mypy / pytest | `C:/Users/yinha/.codex/cache/dianzi/r05-semantic-independent-review/` |
| 只读复用 verified 权重 | `C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime/` |
| 最终 CBM 独立 cache | `/tmp/r05-semantic-independent-review-20261015/cache` |
| 本报告与证据唯一写入范围 | `reports/reviews/recovery/G-B-R05-semantic-review-1.md`、`reports/runs/recovery_r05_semantic_review_1_20261015/**` |

读取了 AGENTS、执行索引、R05 恢复任务卡、T18、架构、API/模型/资源合同、task_state 与交接；实际枚举 CR 目录，相关记录为 `CR-R04-R05_model_post.md`，没有猜造新的 CR 编号。检查原 `clients.py` / `generation.py`、新的 `semantic.py` / `process_limits.py`、`_pdf_worker.py` 与 `pdf_text.py` 调用方及对应测试。基线到代码共 7 个源码/测试文件、1009 行新增/76 行删除；没有审核作者后来仅封存报告的提交内容。

独立工作树最终 `git status --short` 为空，`git diff --check 31c2866 HEAD` 退出 0，SHA/tree 未变。没有改主工作树、作者工作树、依赖锁、业务、状态、合同、金标或指标分母；没有访问产品账号、模型付费接口、来源采集 GET、DB/Redis/MinIO 或服务端口；没有复制、删除或修改约 1 GB 的权重。

## Must fix

1. **[P2] Pipe 初始化失败会永久占用语义模型容量** — `backend/src/ai_intel/infrastructure/models/semantic.py:232–242`。

   职责：`_run_worker` 先取得全模块并发锁，再创建 spawn 上下文、Pipe 和 Process，最后才进入 `try/finally`。操作系统 Pipe 创建可能因句柄/内存等资源耗尽而抛 `OSError`。

   触发 API：`LocalSemanticModels(可信绝对路径).embed_query("synthetic private question")`；独立测试仅把 `multiprocessing.get_context` 换成 `Pipe(duplex=False)` 抛 `OSError` 的故障上下文。预期：安全失败、容量释放，资源恢复后下一次调用可以运行。实际：异常离开第 235 行，清理块未进入，`_WORKER_LOCK.locked()` 保持 True；后续 embedding/rerank 都持续返回 `already busy`。这是初始化生命周期缺陷，不是模型缺失或质量问题。

   独立证据：[最小复现](../../runs/recovery_r05_semantic_review_1_20261015/test_independent_semantic.py)、[失败输出](../../runs/recovery_r05_semantic_review_1_20261015/independent_semantic.stdout.log)、[JUnit](../../runs/recovery_r05_semantic_review_1_20261015/independent_semantic.xml)、[逐字命令与秒级时间](../../runs/recovery_r05_semantic_review_1_20261015/independent_semantic.command.json)。`test_pipe_creation_failure_releases_capacity` 实际失败；同一次 18 项中另 17 项通过，0 error/skip。测试的 finally **由审查者显式释放泄漏锁**以免污染后续测试，不代表产品自行恢复；没有改失败为 skip 或删除断言。

   最小修复：将 acquire 后的全部初始化纳入保证释放锁的生命周期；只有成功创建的 Pipe/Process 才清理，保留已有 terminate/join/kill/close 和安全异常。直接回归覆盖 context/Pipe/Process 初始化失败与失败后的再次调用，不新增服务层或长期进程。未修复的影响是一次瞬时本机资源故障使该应用进程的全部语义能力持续不可用，需重启才能恢复。

   作者已收到精确 probe、日志和触发 API；本初审不包含任何未来补丁，也没有实际复验修复。

## 独立实际检查

日志根为 `reports/runs/recovery_r05_semantic_review_1_20261015/`。下表每个名称对应 `<名称>.command.json`（完整 argv、cwd、+08 秒级起止、退出码）及 stdout/stderr；测试数量来自 JUnit，不把重复命令累加成通过数。除特别说明外 cwd 是独立工作树的 `backend/`。

| 命令/日志名 | +08 开始 → 结束 | 退出与实际结果 |
|---|---|---|
| `environment`：`uv sync --frozen --offline` | 15:41:44 → 15:41:45 | 1；独立空 uv cache 缺 wheel，业务测试 0，环境缺失 |
| `environment_locked`：`uv sync --frozen` | 15:42:08 → 15:44:16 | 0；Python 3.12.13，冻结项目依赖安装成功；未改 lock |
| `semantic_runtime_install`：独立 venv 固定 runtime 包 | 15:44:44 → 15:45:07 | 0；onnxruntime 1.24.4、tokenizers 0.22.2、numpy 2.4.2；psutil 7.2.2 仅审查工具 |
| `full_unit`：`python -m pytest tests/unit -q` | 15:44:44 → 15:45:29 | 0；749 passed，0 failed/error/skip；原 60% 覆盖门保持，实际 66.05%；1 条既有 Starlette 弃用 warning |
| `related_contract`：R05 semantic、原 T18、原 T09 | 15:47:31 → 15:47:33 | 0；17 passed，0 failed/error/skip |
| `independent_semantic`：独立故障/真实模型测试 | 15:47:31 → 15:47:45 | 1；1 failed（Must 1）+17 passed，0 error/skip |
| `actual_concurrency`：两线程真实调用 | 15:51:12 → 15:51:15 | 0；1 passed，首个真实 worker 运行时第二调用明确 busy，随后释放容量与回收子进程 |
| `ruff`：7 个变更文件 | 15:47:55 → 15:47:55 | 0；无 lint 错误 |
| `ruff_format`：同 7 文件 | 15:49:08 → 15:49:08 | 0；格式检查通过 |
| `mypy`：`--cache-dir <独立cache> src` | 15:47:55 → 15:48:04 | 0；74 源文件无类型错误 |
| `windows_pdf_cpu`：真实 `_bound_memory()` 后忙循环 | 15:49:08 → 15:49:27 | 0；打印 LIMIT_APPLIED 后原生终止，child exit 3221225540，wall 18.969 秒，无 Traceback；父 30 秒兜底未触发 |
| `linux_helper_limits`：WSL 标准库小子进程 | 15:49:08 → 15:49:09 | 0；2 个 probe；100 MiB 拒绝 200 MiB allocation，exit 1/MemoryError；CPU 1 秒 child exit -9、wall 1.012 秒 |
| `seal_snapshot`：版本/哈希/结果封存 | 15:52:15 → 15:52:20 | 0；固定 SHA/tree、干净工作树、6 个模型文件 hash 和 JUnit 数量在 `final_snapshot.json` |

运行命令的后续审查 runner 在启动子进程前应用 Windows 2 GiB/CPU 30 秒原生限额，设置 OMP/OpenBLAS/MKL/Rayon 2 线程；Linux probe/图用 `prlimit --as=2147483648 --cpu=30` 与线程限制。环境准备的首次两条安装命令在该 runner 原生限额补入前执行，不能把它们声明为有完整限额测量；它们不属于模型推理结果。模型每次内部自己的 2 GiB/CPU 30 秒限制真实保留，PDF 的 512 MiB/CPU 15 秒保持。原资源 unit 也实际包含 Windows 100 MiB 拒绝大 allocation、CPU 1 秒忙循环终止与 PDF 内存负例。

WSL 真实 Python 为 **3.10.12**，仅通过 importlib 加载标准库 helper，证明 Linux 原生限制有效；未作为项目 Python 3.12、ONNX 或 PDF 全栈 Linux验收。Windows CPU 时间不是 wall 时间；不能将 PDF 的 18.969 秒或作者 CPU 1 秒结果称为超时值失效。

## 真实模型、边界与回归结果

只读缓存的 6 个文件独立重新计算 SHA256，值与固定源码/作者 verified receipt一致，完整值在 `final_snapshot.json`；实际加载的权重和 tokenizer 每次还经过 worker 的 size/hash 检查。固定 E5 修订为 `614241f622f53c4eeff9890bdc4f31cfecc418b3`，CrossEncoder 为 `1427fd652930e4ba29e8149678df786c240d8825`；未重新 GET 官方模型、未加载 pickle/remote code。模型来源取得与许可核验沿用作者留档，本次对本地实际字节和调用结果独立核验。

- 独立合成文本与作者 smoke 不同：中英租户证据访问控制及无关园艺正文。真实 E5 返回 384 维、有限 float、L2 归一化；同正文单项与混合长度 batch 的结果在 1e-5 数值精度内一致，重复正文在原顺序中保持相同向量。没有哈希向量或固定答案后备。
- 真实重排保留全部原始索引及重复正文，结果 `[0,3,1,2]`；0/3 同分 3.510960102081299 并按原 index 稳定排序；英文相关正文 3.3030545711517334、无关正文 -9.028312683105469。这里没有准确率、质量阈值、正式金标或 BGE 对比结论。
- 真实 tokenizer 含 `passage:` 和 special tokens 的恰好 **512 token ×8** batch成功，完整 hash/加载/推理调用 3.594 秒；513 token 明确 `SemanticInputError`，无悄悄截断。不是冷机器 SLA、吞吐指标或正式性能结论。
- 缺 cache 的真实 spawn 失败返回安全 `ModelNotConfiguredError`，不回显 synthetic private marker；0.001 秒父 deadline 的真实 worker 被回收，锁释放，没有推理继续或 active child 残留。实际同进程并发负例通过；跨进程应用级并发尚未集成，未宣称 host 全局单并发。
- 独立 malformed 输入覆盖 None/bool/int/bytes/list/坏 Unicode；坏输出覆盖 bool/int/NaN/±Infinity；原 unit 另覆盖空/零/非归一化/维度和计数错、稳定同分、模型空间变化、批次/前缀、错误 envelope/EOF/超时。
- 同大小小型 synthetic 错误 cache 的 checksum 拒绝及真实 Windows 目录 junction 指向 cache 外拒绝均通过；没有用被篡改的真实 470 MB 权重测试或修改 verified cache。
- 原 PDF/JSON/TextBlock/证据定位 unit 与 T09合同实际回归；官方四页中文 PDF、缺页 partial、无文本/加密/损坏/页数/内存限制、JSON 歧义及 Unicode边界保留。共享调用者只新增 native helper委托，没有新增 pypdf 到语义 worker。

源码交叉核实：先 resource limit 后 hash 与重库 import；ONNX CPU provider、最多两 inference线程、关闭 fallback/telemetry；只有本地固定文件，无 custom op 注册、hub downloader或网络调用。向量先严校有限纯 float、384 维和 norm，再调用原仅校维度/数量的 `validate_embedding_batch`；没有假设未来公共加强补丁已存在。模型空间指纹涵盖 repo/revision、权重/tokenizer、FP32、query/passage、masked mean、L2、512上限及维度。

## CBM 架构图与源码交叉

实际 portable `codebase-memory-mcp 0.11.0` 的 help/index_repository/get_architecture/trace_path 执行，不把图当事实合同。最终索引仅独立 WT `backend/src`，不索引权重、密钥、fixtures 或 holdout。

| 证据 | +08 起止 | 实际结果 |
|---|---|---|
| `cbm_index_isolated` | 15:44:03–15:44:09 | exit 0，995 nodes/4705 edges，0 skipped/partial/unusable，独立 CBM_CACHE_DIR |
| `cbm_architecture_isolated` | 15:44:44–15:44:47 | exit 0，models 范围 78 nodes/232 edges |
| `cbm_trace_resources` | 15:47:05–15:47:08 | exit 0，helper inbound 指向 `_bound_worker_memory` / `_semantic_worker` 与 PDF `_bound_memory` / `main` |
| `cbm_trace_semantic` | 15:47:05–15:47:12 | exit 0，embed_query → `_embed` / `_run_worker` / 数值校验 / 既有结果合同 |
| `cbm_help` | 15:52:56–15:52:56 | exit 0，实际版本与 CLI tools |

图中 semantic → helper 的一跳属于 heuristic/0.38低置信度；已用源码 import、rg 全调用方、真实限额和既有 PDF 回归交叉确认。图不会完整解析 spawn 回调，因此 `_semantic_worker`、hash、tokenizer和ONNX边界另逐行读取并用真实调用确认。

审查工具自身第一次使用 XDG_CACHE_HOME 未建立独立 CBM cache，随后改用其实际 CBM_CACHE_DIR并重索引；第一次 `--aspects '["overview"]'`被 CLI当成未知 aspect，exit 1，最终正确命令通过。初始非独立图不作为最终证据，其仅属于本审查创建的 `r05_semantic_review_bfea9fe`项目已用 `delete_project` 精确删除（`cbm_remove_initial_own_index`，15:53:33–36，exit 0）；其他项目未动。失败日志保留，没有把工具参数错误记成业务失败。

## 未覆盖、集成前置与交接

本次安全结论仅覆盖本地模型输入输出、文件完整性、进程资源和生命周期；**Must 1 未关闭**。固定 SHA 的 `pyproject.toml/uv.lock` 尚未声明 ONNX runtime能力；独立 venv显式安装用于真实验证，不能说默认锁定部署已能调用模型。依赖/模型配置与批准的 BGE候选改为多语种 MiniLM的合同登记仍由主控完成；此包明确 `not_integrated`，该缺口是集成前置，未当成模型业务失败。

未执行 PG/pgvector写入、租户ACL召回、版本有效性、生成API、检索融合、引用回答、前端/e2e、正式性能/质量、人工标注、BGE对比、冷机启动、全栈Linux或 host跨进程全局容量测试；这些均 `not_run`，不折算为通过。没有正式测评数据、人工金标或已批准阈值的改动。真实模型 smoke 支持 F2/F3/A1 的 T18接口能力证据，不能签 F3/P3、整T18/T30/T31或 G-B。

子进程的超时、缺模型、成功和并发路径均实际核对 active children恢复到调用前；native probe子进程全部已退出，所有 exec测试session结束。本次留存独立 WT、venv/cache与报告供定向复跑，未清理他人服务、权重或工作树。快照的进程清单只含封存命令自身，不能据此推断全机无其他合法进程；不声称取得独立 RSS峰值。

下一动作：作者冻结仅修 Must 1 的代码 SHA；同一独立审查者在独立 WT定向复跑生命周期最小失败例及语义/资源回归，再由主控据意见集成并登记。当前 **Verdict：fix 1 first**；没有风格/删行建议，未修改业务代码。

## 定向复核附录 · 2026-10-15T16:00:34+08:00

主控再次明确授权定向复核，在干净的审查者自有 WT切换到固定 `1e77c0d83a95f22ffd6457c2bb432eb2c0538f9e`，tree `0461a78f4993bfe83bd953bbaf89faa75237e89d`。修复提交本身只改 `semantic.py` 与直接 unit测试，136 行新增/23 行删除；前一提交另有作者报告/日志封存，因此 bfea9fe 到修复 SHA的完整树差异不只有两个文件。helper 与 `_pdf_worker.py` 业务字节和 77add60 相同，初审的 Windows/PDF/Linux实际限制证据继续适用；没有把作者修复日志当独立结论。

修改将 acquire 后的上下文/Pipe/Process/start与 sender close纳入清理保护，尚未创建的对象用 None表示；初始化失败转固定安全 `SemanticRuntimeError`。清理尽量逐个关闭连接、terminate/join、kill/join并关闭 process；无论清理结果都释放锁；有原异常时保留原分类与固定 cleanup note，成功路径清理失败显式报错，没有伪造成功。读了完整 diff及连接代码，并独立新索引/trace交叉核对。

**Must 1：closed。** 原封存失败测试未修改断言、未删/skip，直接复跑通过。新增独立清理故障注入同时令 receiver close和 terminate抛含 synthetic私有标记的异常：实际继续执行 kill与 process close，释放容量；成功分支显式安全 cleanup失败，超时分支保留 `SemanticTimeoutError` 与固定 note；敏感细节不回显。原直接 unit另外实测 context/Pipe/Process/start的 OSError/RuntimeError共8种初始化路径及下一次健康调用。

| 独立复核命令/日志名 | +08 起止 | 退出与结果 |
|---|---|---|
| `recheck_full_unit`：原 `pytest tests/unit -q` | 15:58:26–15:58:58 | 0；759 passed，0 failed/error/skip，原 60%门保持，66.21%，1条既有弃用 warning |
| `recheck_independent`：原18项+真实并发1项+新增清理2项 | 15:58:26–15:58:43 | 0；21 passed，0 failed/error/skip；原 red→green |
| `recheck_contract`：相同 semantic/T18/T09合同 | 15:59:08–15:59:10 | 0；17 passed，0 failed/error/skip |
| `recheck_ruff` / `recheck_format` | 15:58:26–27 / 16:00:34–34 | 各0；两修复文件 lint/format通过 |
| `recheck_mypy`：独立 cache的全 src | 15:59:08–15:59:09 | 0；74源码文件通过 |
| `recheck_cbm_index` / `recheck_cbm_trace` | 15:59:08–14 / 15:59:29–32 | 各0；独立cache src索引995 nodes/4705 edges，追踪 `_run_worker` 入出调用；源码确认新 finally释放路线 |
| `recheck_snapshot` | 15:59:29–15:59:34 | 0；新 SHA/tree、干净 WT与6文件hash单独封存，不覆盖原 `final_snapshot.json` |
| `recheck_source_diff` | 16:00:34–16:00:34 | 0；修复源码/直接测试 `git diff --check`通过 |

所有逐字 argv/cwd/秒级时间/退出码和 stdout/stderr仍在同一日志根，以 `recheck_`名称区分。`recheck_snapshot.json`包含旧红例 XML和新绿例 XML的不同键，旧失败保留不计入本轮通过；完整历史证据树 `diff_check=2`仅来自作者留档 `download_sdk.py:37` 的空白行 trailing whitespace，新业务两文件检查为0。本次未改历史下载证据，也不把该空白问题扩成业务阻断。

真实模型复核采用同一组只读 verified权重、独立 venv，调用代码来自修复 WT：中英实际 E5与实际重排、混合长度 padding一致、重复正文/原index/稳定同分、8×512 batch与513拒绝、0.001秒真 timeout回收、两线程真 busy与容量恢复全部通过。8×512完整调用本次3.766秒；结果仅数值/资源smoke，没有质量阈值或指标提升声明。没有新下载、模型替换或源/付费调用；本轮检查约2分钟，原初审与后续明确授权复核分别有界，均未做长时间批处理。

复核完成所有测试 session退出，真实子进程成功/错误/超时/并发后 active children恢复到调用前；未修改任何业务、共享状态、锁文件、合同或他人工作树。**最终 Verdict：Ship（仅此本地 semantic runtime + 未变共享限额/PDF范围）。** 主控仍需锁定 runtime依赖/配置、记录批准的模型选择并完成 PGvector与引用回答接线；原报告列出的产品整链、正式质量/性能、人工与全栈Linux等未覆盖项保持 `not_run`。本审查者不写 accepted或push，主控按新冻结版本和这些证据登记。
