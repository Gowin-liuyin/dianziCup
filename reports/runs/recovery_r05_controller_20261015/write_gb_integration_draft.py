"""保留旧阶段全文，按当前证据重写可审查的九节阶段草稿。"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
run = Path(__file__).resolve().parent
target = root / "reports/stages/recovery/G-B.md"
archive = run / "G-B_prior_to_integration_draft.md"
assert not archive.exists()
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
previous = target.read_bytes()
archive.write_bytes(previous)
first_created = next(line.split("：", 1)[1] for line in previous.decode("utf-8").splitlines() if line.startswith("文档首次创建时间："))
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
content = f"""# G-B · 真实来源、原文证据与模型问答

文档首次创建时间：{first_created}
本次写作开始时间：{started}
本次写作结束时间：__WRITING_END__
最后更新时间：__WRITING_END__
阶段实际开始/结束时间：历史未单独记录，首个来源GET观测为2026-10-15T11:53:40+08:00，不能冒称阶段起点 / 尚未结束
本报告证据截止时间：{started}
主控/实现Agent：/root；各作者、工作树、文件所有权与冻结版本见progress/recovery_workstreams.md及任务报告
独立审查Agent与报告：下列专项已封存；新的整阶段独立审查尚未发生
阶段状态：in_progress
实现状态：partial（阶段功能候选已接通，整合安全检查仍有未分类命中待核）
各层验证状态：unit passed；contract passed；integration passed（所列隔离PG范围）；security failed（全仓精确分类待收口）；frontend passed；e2e/live passed（所列Windows单事件范围）；manual not_run（不以Agent或模型充当人工金标）
工作分支：codex/full-delivery-recovery
已测代码SHA：dc014c960f19605c20e0d8e98a93e7c217f94cc6真实API/页面，799028ef637b61547683b7d210d2ca5df93bb1bc PG新增测试与纯回归；当前候选{head}
已审代码SHA：dc014问答事务、a0a94f1007dfdb1811df327ca2f931034af33a2e前端、c83e1a03f2ffc474ba1a0365473a5eae1945f45c来源限流及下列早前专项；未用组件Ship替整阶段意见
提交/推送结果：G-B尚未阶段push；G-A远端fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4，2026-10-15T15:41:48+08:00已核对；实际台账reports/push/recovery_push_log.jsonl

## 1. 本阶段要解决的用户问题与验收范围

R04把真实NVD和vLLM厂商公告从共享网关接到原文库、解析、永久证据、PG事实、任务/游标及浏览器列表/详情。R05把一个当前公开事件的证据接到真实E5、pgvector、重排和两轮生成/支持核验，用户可打开固定revision证据并重读已保存答案。覆盖F1/F2/F3/A1/E1/D2/R1当前切片；U01发现、U02证据详情、U06单事件首答、U10来源操作有部分路径证据，不能签九维完整、深度多跳或全部运维场景。

原T09/T10/T12/T17/T40/T41及T18/T20/T30/T31/T43只完成本阶段映射切片，整T卡继续等待全部映射、前置与验收共同满足。R05不是R12，问答明确拒绝asset、conversation、多事件、known_at/valid_at和investigate，返回422；R17完整资产、图谱、推荐、报告与Agent工作台仍未完成。R06八类九通道调研在独立准备包推进，未计为本阶段产品来源。

## 2. 当前真实状态与修改

原有问题包括默认入口未装配、伪PDF文本层标记、NVD真实wrapper/cvssData失配、模型无真实IO、内存事实/游标、失败仍推进游标、前端骨架。G-A已建立真实PG/API/auth/worker/outbox；本阶段复用这些实现，没有另建事实数据库。

- 解析：pypdf受控子进程读取真实文本层、页号与Unicode位置；JSON严格拒绝重复键/非有限/孤立代理/NUL，保留解码字段原文及RFC6901路径。扫描PDF准确报告缺文本层，不伪称OCR。官方四页PDF独立实际parsed，3882字符、四页位置均可回切；不将单次解析耗时计问答性能。
- 来源：NVD Ollama固定查询与vLLM公开公告，经可信网关、MinIO原文、不可变response/member和PG源版本入库。厂商按真实Link的after游标分页；保存事实、回执、cursor、job/outbox同事务。首次数字page重复同10条的错误及其旧回执不删除。2026-10-15T17:10:08+08:00前向迁移核对105事件、434证据及证据身份hash完全保留。
- 问答：真实本地E5固定官方ONNX/分词器与模型空间384维写PG，真实mmarco重排；PG派生块不能扩大可见范围或复活撤回事实。只取当前公开、validated support、有效claim的证据，精确子串引用；两轮真实GenerationClient分别生成与核验，不执行模型工具。完成前重查原文/hash/epoch与权限。
- 持久化/权限：必需幂等key；PG唯一预约、420秒有界失效、owner与expiry CAS，重放不重付费；同事务FOR SHARE锁会话和用户，保证先撤销拒绝、已持锁则撤销等待答案提交。旧无lease pending需受控人工恢复，不猜付费结果；实际试验库新段启动前无旧pending。
- 前端：暗色青绿研究工作台、低亮动态拓扑背景、pointer-events:none、键盘焦点、reduced-motion；真实列表/详情/证据/来源控制/问答。加载、匿名、无权限、空、过期、部分失败、模型缺失和结果未知分别显示。问答POST预算90秒，其他请求10秒；预算不是P3达标。未知提交保留同body/key，禁止自动换key重发。

必要新增是source writer/page job、只读投影、真实模型wire/本地受控推理、单事件检索和答案生命周期及页面。复用PG、认证、网关、永久证据、标准库与现有UI组件。pypdf、pgvector、onnxruntime/tokenizers/numpy各为真实PDF/向量/模型必需；固定缓存约975MB在仓外，不执行pickle或remote code，没有哈希向量/内存产品库/模板成功页。

## 3. 并行执行与独立审查

主控独占共享schema/迁移0014/锁/状态/集成/Git。来源、解析、只读API、生成wire、语义、前端、grounding及PG测试各在独立worktree按指定文件交付。每个初审为未参与实现的新Agent，固定commit；作者仅awaiting_review。四槽滚动执行，详细所有权与交付SHA见各报告，未向其他用户聊天或协作软件发消息。

| 冻结范围 | 独立证据与结论 |
|---|---|
| PDF/JSON解析48ad907 | reports/reviews/recovery/G-B-R04-parsing-review-1.md：原两Must与数值覆盖缺口关闭，官方四页实际校验；组件限定通过 |
| API7af、来源8f6 | G-B-R04-api-review-1-recheck-2.md、G-B-R04-pipeline-review-1-recheck.md：ACL/版本/事务及after分页限定通过；原失败保留 |
| 生成31c、语义1e77、基础3ab | generation/semantic/vector-foundation专项报告：真实接口、模型空间、子进程锁/float32边界限定通过；不代替产品链 |
| grounding b151 | G-B-R05-grounded-answer-review-1.md：原跨主体未知误拒关闭，47独立探针、113核心/合同、29安全；第二模型不是人工金标 |
| 来源c83 | G-B-R04-rate-limits-review-1-recheck.md：906unit、421相关、19既有PG、40自拟；超长/过多/重复限流头不提前重试。RFC850日期边界P3仍为非阻断债务 |
| 问答UI a0a94f1 | G-B-R05-question-frontend-review-1.md：254前端、9原fixture浏览器+11独立检查；原12秒请求被10秒取消红例保留并复验关闭 |
| 问答事务dc014 | G-B-R05-question-pipeline-review-1.md：3 Must关闭；1007unit默认66.68%原60门、32PG、24新PG、8独立进程/事务反例、126核心/合同，mypy/Ruff通过 |

当前候选与真实运行dc014的backend/src tree均6b91c2c318ec75c0f9625a3f86a52460bfe0dd36，frontend/src tree均740566274dc282ebafd12ef3fe8f42ab85becc4a；后续差异仅新测试/报告/精确分类。新的阶段reviewer尚未签整合版，不能因上表逐项Ship自动过门。

## 4. 问题台账

每项精确发现/修复/复验时刻、输入、行号与命令在引用专项报告/原始receipt；历史没有记录的时刻不按mtime补写。下表不覆盖其原红例。

| 问题 | 触发、实际影响与根因 | 修复/状态与证据 |
|---|---|---|
| R04分页 | GitHub数字page两页实际hash相同，重复同10条并误触页上限 | 改Link after、兼容拒绝旧非首数字cursor，8f6独立关闭；旧回执保留，后5页新增40而非重复计数 |
| R04原文 | JSON二次转义/孤立代理导致精确引用失败 | 48ad907关闭，真实Unicode roundtrip与官方四页证据见解析报告 |
| R05引用换行 | 2026-10-15T15:04:28+08:00至15:04:34+08:00两wire HTTP200，但模型CRLF改LF，引用不支持 | 原失败留档；单行v2另两次成功，之后产品仅精确单行派生片段，不能抹原两次失败 |
| R05 float32 | 1e-50转float32全零、极端平方范数产生NaN | 3ab按真实float32与平方范数校验，独立20PG/126相关关闭；初红全保留 |
| R05缺key | d7无key连续POST两前缀各200、总4模拟wire；违反原写入合同 | dc014在预约前422 invalid_key，0模型/0答案；原两名独立测试红例与复核保留 |
| R05中断 | 真实child os._exit后pending永不终结，重启只409 | dc014预约expiry/owner和完成CAS；独立进程与到期/late writer复验关闭，新预约不重付费，实际费用未知保留 |
| R05撤销竞态 | 最终事务外scope已取后先logout/迁租仍200 completed | dc014锁auth_sessions/users与答案同事务；真实PG先撤销拒绝、pg_blocking_pids证明后撤销等待，独立关闭 |
| UI等待 | 真12秒fixture被共享10秒取消；实际首个冷产品完整17.009秒 | a0a94f1仅问答POST90秒，默认10秒不变；独立12秒/90秒/abort/同键复核关闭，实际修复版浏览器10.213秒 |
| 综合安全扫描 | 2026-10-15T17:35:27+08:00至17:36:59+08:00，1419中1安全失败：未分类credential形状 | 初扫70命中/58文件：55/48来自两个已退役venv，15/10待逐条fixture来源核验。venv原样搬仓外，4857/6532文件before/after hash完全一致；不放宽规则/目录忽略。精确分类收口仍待完成，security保持failed |
| PG回归环境 | 2026-10-15T17:40:36+08:00至17:40:39+08:00，10setup errors：run_id未包含新库随机后缀 | 仅更正子进程运行ID与同一已分配隔离库名称一致；2026-10-15T17:41:28+08:00至17:41:40+08:00，10pass；没有改隔离校验/业务/门槛 |

未解决/非阻断：RFC850完整50年日期边界会保守误blocked（非提前重试）；容器semantic extra/内存/受控出网待部署接线；Linux来源出网未由Windows成功替证；正式持续窗口、质量/速度/盲测及人工金标未完成。源时间缺时区/缺发布时间保留未知，不拿采集时刻补齐。

## 5. 实际验证

完整argv/cwd/起止秒/exit/计数/配置与SHA以原始JSON/JUnit为准。默认覆盖门仍60%，没有改分母、删题或把失败skip；重复fixture与live绝不累加成准确率。历史工具UTC记录单独标注，文档本地时刻统一+08。

| 范围/命令 | 时间、退出码与结果 | 原始证据 |
|---|---|---|
| root backend pytest tests/unit tests/contract tests/security -m 'not real_pg' -q | 2026-10-15T17:35:27+08:00至17:36:59+08:00；exit1；1007unit+218contract+194security=1419，1418pass/1安全fail，另10PG明确deselected后单独运行；73.77%原60门 | reports/runs/recovery_r05_controller_20261015/gb_pure_regression.json/.log/.xml |
| root隔离PG问答/route/contract | 2026-10-15T17:33:08+08:00至17:33:42+08:00；exit0；37pass，0skip；显式synthetic模型，只计接线 | questions_api_pg_fenced_integrated.json/.log/.xml |
| root原PG权限/任务/退避 | 2026-10-15T17:41:28+08:00至17:41:40+08:00；exit0；10pass，0skip；新库test_dianzi_gb_security_20261015_76c8ab35，未升级旧G-A库 | gb_pg_security_recheck.json/.log/.xml；原setup错误gb_pg_security.* |
| 新问答前端作者+独立 | 固定a0a94f1，254pass；typecheck/lint/build通过，原9fixture浏览器与新增11检查；精确时段见各receipt | R05-question-frontend.md、G-B-R05-question-frontend-review-1.md |
| root修复版真实浏览器 | 2026-10-15T17:30:22+08:00至17:30:38+08:00；exit0；1完整业务test/13.1秒测试执行，完整单问客户端10212.6966ms，服务端10135ms；无route mock，真实HTTP登录/PG/模型 | product_live_dc014c9/browser.json、browser_artifacts/actual_question.json及桌面/390PNG |
| root首条冷产品API | 2026-10-15T17:12:18+08:00至17:12:36+08:00，23c HTTP200；完整客户端17008.697ms，真实两轮生成，GET/同key重放成功，无新增模型调用 | product_live_23c1878/question_end.json/answer_read_and_replay.json/pg_answer_trace.json |
| 真实模型次数/费用 | 31c两种wire共4次（2精确引用失败、2成功），23c产品2次，dc014浏览器2次，总8实际供应商调用；真实usage逐attempt留档，费用unknown | 两supplier run与两产品PG trace；不是8道正式金标题 |
| 实际来源/页面 | 8f6五页after新40；afe桌面1366/390列表→详情→原文→刷新2pass、管理员一页提交→PG partial1pass；具体开始/结束见两浏览器receipt | recovery_r04_source_jobs_20261015/real_browser_segment6*.json及live_segment_5_after_quota_reset/ |
| 提交真实秘密检查 | 已核对217作者证据、9秘密参考/321全值与8字节片段，gzip解压64,278,013B也扫，0命中；最终阶段全提交仍须另扫 | recovery_r01_controller_20261014/r05_author_evidence_archive_scan.json |

真实运行段：23c API为2026-10-15T17:10:56+08:00至17:22:30+08:00，requested_stop；dc014 API与Vite为2026-10-15T17:29:17+08:00至17:44:17+08:00，deadline。Windows受控terminate进程exit1如实记录，不伪称自然退出0或业务请求失败；两段都只有API、未启动worker/beat，ready可degraded。此前afe来源worker段独立记录。MinIO段2于2026-10-15T16:55:49+08:00到期，段3自16:57:02+08:00起7200秒，同对象/身份但中断73秒。不同代码/中断不拼持续运行。

dc014的新段复用同E5空间20个既有派生块，query embedding、rerank与双轮生成重新执行，不能称冷索引。17.009秒与10.213秒属于不同代码/缓存条件，不拼P50/P95/max，不声明≤5秒或质量达标。问答超时、错误JSON、拒绝/权限负例主要为明确隔离contract/security，真实供应商故障未逐个强造。

not_run/未满足：正式准确率/召回率/完整性能分母、同条件基线/消融、人工双人金标、完整Linux容器新模型/来源、最终版本连续6h窗口、OCR、R12完整多跳与R17后续工作台、R23干净环境复现。没有拿首字/202/缓存命中替完整回答完成。

## 6. 合同与计划差异

按已批准CR-R04逐条补实现合同：R04_document_parsing、source_persistence、source_jobs、read_api_projection、R05_model_post与R05_question_commit；新增必需key与权限锁是落实既有05 API条款、修复偏差，不改变身份、公开字段、角色/租户、模型费用许可或评分。R05_question_commit仍awaiting_review登记，其准确落实已由独立dc014复核说明，整阶段审查后方登记。

0014前向新增retrieval_chunks/grounded_answers，旧105事件/434证据和身份hash不变；不做破坏性downgrade。API内部ask/read新增keyword-only session_token，当前产品调用方均question_routes已核对，不进模型/日志。回滚是停止新POST/模型调用并保留历史、用量、失败，前向修复，不回退fixture。

没有新范围削减、评分分母/阈值或盲测原则变更。R05单事件切片不等于T20/T30/T31/T43全部accepted；R06准备和R20部署缺口不包装为前置已完成。

## 7. 评分和场景证据

F1/R1/E1：两固定真实源的原文→PG事实/游标/任务→列表/证据与失败/partial可见；未声称八类来源完成或时效优秀。F2/A1：真实E5/pgvector/rerank和生成支持核验；九维富化全落地仍R07/R08。F3/U06：指定事件的引用首答与持久重读，缺支持拒绝，未知不自动否定；多轮多跳、资产/历史在R12。D2/U01/U02：真实浏览器操作、背景动态/减少动画与原文修订；完整演示/视频与U14未完成。P3本轮17.009/10.213秒如实记录，未达到≤5秒样本，不能自评满分。

U03–U05/U07–U09/U11–U14当前仅原规划与部分骨架/准备，不由本阶段反推已完成。正式13要求逐项最终证据在R22–R24闭合，本阶段只给上述切片。人工金标与FOFA授权资产范围仍缺，PPT用户后置；独立部分继续做，不拿blocked/awaiting_human_label作成功。

## 8. 阶段结论和下一步

已证明真实来源原文/PG/页面、两兼容wire、本地语义、单事件引用回答、历史读/幂等与新预约/权限事务、浏览器业务路径。旧三Must在限定dc014批次独立关闭，原失败未删。整合安全扫描精确分类仍未收口，新的整阶段review未发生，本报告不能过G-B门，不能阶段push或改整R04/R05 accepted。

下一步：关闭精确fixture分类/缓存收口的安全失败，最终源码/回归/文档冻结→新的阶段Agent独立复跑来源/问答/权限路径并核对状态与本文→依据其意见登记阶段与R切片、显式文件提交→检查origin/fetch/秘密/大文件→普通push codex分支并核对远端SHA、追加实际receipt。通过后继续R06–R10；准备包可以先做但不越过live门。R20补semantic镜像/容量/固定出网与恢复，R19人工金标候选/双人裁决工具，最终R22/R24-A/R23/R24-B顺序保持。

## 9. 文档修订记录

首次创建时间保留{first_created}。本次{started}至__WRITING_END__由/root按实际冻结源码、专项独立报告与raw收据重整九节，将旧全文原字节归档reports/runs/recovery_r05_controller_20261015/G-B_prior_to_integration_draft.md，SHA256 {hashlib.sha256(previous).hexdigest()}；Git历史同样保留。旧报告中的进行中缺陷/组件状态是当时事实，不覆盖本次限定复核结论。没有按mtime伪造历史编写时间、没有把编写/测试/采集观察混为持续运行。
"""
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
target.write_text(content.replace("__WRITING_END__", ended), encoding="utf-8")
(run / "gb_integration_draft.json").write_text(json.dumps({"started_at": started, "ended_at": ended, "head": head, "prior_document_sha256": hashlib.sha256(previous).hexdigest(), "new_document_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "stage_status": "in_progress", "phase_accepted_or_pushed": False}, indent=2), encoding="utf-8")
print(json.dumps({"started_at": started, "ended_at": ended, "stage_status": "in_progress"}))
