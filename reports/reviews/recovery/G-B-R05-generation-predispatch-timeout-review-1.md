# G-B · R05共享生成预派发超时独立审查1

记录时间：2026-10-16T02:31:41+08:00（实际UTC时钟换算）。新非作者reviewer：`/root/r05_generation_predispatch_timeout_independent_review`。
本次意见：**限定 Ship，仅共享生成预派发异常归一修复；不登记accepted，不替代G-B全阶段复验或R09原reviewer复核。**

What this change does：合法请求在申请并发槽之前耗尽整次预算时，返回既有固定
`GenerationFailure("model_network_timeout")`，保留空attempts。已占槽请求仍按原finally释放；
并发等待返回False仍是`model_concurrency_timeout`。没有新增重试、重定向、模型后备或预算放宽。

## 冻结版本、权限与改动范围

基线：`595a13197a2c1bba6ad79957f8fde3750ba2a6c6`；作者代码：
`47c47bc2b5d537166ee47a01c2ab14c035466e3d`；材料：
`df0faafb64327be190803089f0058f9b5dc2427b`。
独立短工作树：`D:/wt/gen-tmo-r1`，分支`codex/r05-generation-predispatch-timeout-review-1`，
HEAD始终df0fa，HEAD tree为`0560b4778e079a333e40314921e036bd22227cea`。
开始clean，未在作者工作树实施或复跑。主仓库已有未提交状态与大量证据，未改动它们。

读AGENTS、00执行索引、03数据合同、05 API错误合同、恢复R05/R07/R09、原T18/T31、
固定task_state与交接，并采用指定Ponytail review 5.2.0。
输入/前置是合法批准模型、严格schema、通过外发策略的GenerationRequest；
本片验证固定错误协议，不重新验收R04实时链、R05真实生成/embedding/rerank、R07/R09整卡。
原任务C01–C06、金标、计分分母、依赖版本和合同均保持。

业务diff只有generation.py的5行新增/2行替换及新增17例测试141行：

- `backend/src/ai_intel/infrastructure/models/generation.py`
- `backend/tests/unit/test_r05_generation_predispatch_timeout.py`

47c到df0fa的src/tests/config/contracts/progress/docs/pyproject/lock差异为空。
两业务文件逐Git blob核对相同；generation blob为`7999f1ec29cf025b800cc7b8987dc92e3ba879ba`，
LF blob SHA-256为`400c6a23f373e12ec77748108006e55ce30d8aec62bad10d88f014309d3e475b`，
本Windows checkout CRLF raw为`08d26f0bc5ea4987a51ae4b499d1771c06eab6ec249945aa30080a7eca4ee1e3`。
不把两种字节hash混用。本review只新增本报告及专属run；独立组合工作树仅有明确授权的共享模块叠加实验。

managed创建本次成功，未用于复跑；为满足短路径要求另建上述短树。
未使用的clean managed树已通过archive_worktree归档，list_artifacts确认archived_worktree；
没有修改全局ACL或Git配置。工具生命周期原回执在run。

## 根因、调用方与修复结论

原`generation.py:409`在try之前计算`deadline.remaining_seconds()`。
`network.py:118–121`在remaining <= 0直接抛NetworkTimeoutError。
固定clock100→103、合法1秒预算可确定复现裸底层异常，且并未申请槽、DNS或POST。
修复版`generation.py:409–413`只捕获该网络超时，使用既有码和`from None`；
默认`attempts == ()`、finish_reason为空，没有伪造响应、token或0费用。
`generation.py:546–547`原finally仅在获得槽之后执行，未获得槽时不会release。

**Must fix：本次限定diff未发现。Should fix / Nice to have：没有带具体复现的新增问题。**
最小修法已经在共享层落实，无需给各调用方增加特殊catch。

CBM为本短树backend/src建立专属fast index，使用专属WSL缓存，随后真实schema与完整qualified名查询：
1340 nodes / 6737 edges，0未索引、partial或unusable；默认排除assets目录，不宣称全仓图。
`r05-timeout-review-1.ai_intel.infrastructure.models.generation.GenerationClient.generate`
入向为grounding.generate_grounded_answer（hop1）与GroundedQuestionService.ask（hop2）。
再用rg全src交叉追踪QA构造和两次generate，没有将图结果当作全部动态caller证明。

QA `grounding.py:215/241`调用生成和核验，`:261–262`承接GenerationFailure并拼接已有attempts；
`service.py:346–349`记录typed失败的attempts与code，其他异常会变question_processing_failed。
新增独立QA第二次调用预派发失败例证明：只保留第一次成功的fixture attempt，1次POST，
固定model_network_timeout，核验没有派发或额外修复。

本base没有新R07 model_fields或R09 card_extraction候选，作者声明正确。
只读核对sibling `D:/wt/r07-model-fields-two-root-causes-fix@ef24758bd8e9e3e1e8e24760d330a9ffe62af341`：
`model_fields.py:164/179–186`把GenerationFailure转为对应维度failed并保留attempts；
未知与失败并未变空成功。没有在该sibling运行或修改代码，不称R07调用链已动态复验。
只读R09作者树`ed217564e9cf3571b430d0fe7caa4d3999c7320b`的
`card_extraction.py:292/297–298`承接GenerationFailure为CardExtractionFailure。

models/clients.py为协议/fixture校验；semantic.py的worker锁为非阻塞取得，使用自身SemanticTimeoutError
及finally，不使用这条remaining_seconds预派发分支。通用NetworkGateway公开协议本来是NetworkTimeoutError，
生成attempt内部已有typed归一，因此没有扩大修改网络层或其他模型模块。

## 独立负例与R09组合树

45个最终自拟R05/QA例由当前脚本字节复跑通过：四provider的恰好到期/过期、零DNS/POST、
零acquire/release、真实semaphore占槽/恢复、过期请求不能释放另一请求名额、实际等待False并发错误、
未知acquire异常原样传播、同private请求优先外发拒绝、repair第二次预算耗尽保留两attempt且无第三次，
以及四provider×connect/TLS握手/body read/DNS的16个真实transport代码超时负例。
transport测试使用现有隔离socket/DNS fixture，不发真实请求；失败后同client可成功复用slot，
HTTP POST/TLS/SNI仍经实际代码执行。原289回归另外覆盖已有线程占槽与预算/注入/schema/凭据边界。

R09原独立报告的Must1未冒称在ed版本被修复。另建本人组合树`D:/wt/gen-card-r1`，
分支`codex/r05-timeout-card-combination-review-1`，HEAD仍ed217564，原HEAD tree
`c11d34918c25e05ac8b1bb42e1224925ec9ce4dc`。
把原reviewer最终17例文件按原始bytes复制到本run，SHA-256两边均为
`76ca4d4064f65bfd08846a6e57a2c4fde087a10d6422d563094b412890058bbf`。
叠加前独立重现16 passed/1 failed，裸NetworkTimeoutError路径与原Must一致。

仅把47c47bc的generation.py Git blob叠到本人的组合树，实际tracked diff只有该文件。
独立临时Git index计算组合tree为`b036c1b800c60405e97a7346ee6d327b00e3754a`；
没有修改真实index或创建组合业务commit。原bytes17例全部转绿；因原用例只断言允许错误码与<=1 attempt，
另增精确例确认CardExtractionFailure.code恰为model_network_timeout、attempts为空、0 gateway calls且slot可复用。
最终精确例1 passed。combo_tree_binding及最终命令回执明确记录实际执行模块路径、raw hash与组合tree，
不把HEAD原tree冒称执行树。

原R09报告仍needs_changes；本实验是共享修复的调用边界证据，不能代替原reviewer对正式合入freeze的复核，
不能签R09 66/380回归、PG、生产caller或完整卡验收。

## 真实命令与结果

专属环境实际`uv sync --offline --frozen --all-extras --no-install-project --project backend`，
Python3.12.13/91 packages，退出0；无锁/依赖修改或模型下载。
命令入口为`backend/.venv/Scripts/python.exe reports/runs/recovery_r05_generation_predispatch_timeout_review_1_20261016/run_check.py <label>`。
每条实际argv、cwd、+08开始/结束、exit、HEAD/tree和JUnit数见同名.command.json、stdout/stderr及
command_index.json。pytest均`--no-cov -q -p no:cacheprovider`，临时目录/JUnit指向本run，不修改默认覆盖门。

| 标签/检查 | +08实际开始→完成 | cwd | exit及结果 |
|---|---|---|---|
| regression：原272+新17 | 2026-10-16T02:22:41→02:22:54 | gen-tmo-r1/backend | 0，289 passed；219 unit /46 contract /24 security；0fail/error/skip |
| independent初版 | 02:24:04→02:24:07 | 同上 | 0，44 passed |
| qa_second_timeout | 02:26:32→02:26:33 | 同上 | 0，1 passed |
| independent_final（格式后当前字节） | 02:29:10→02:29:12 | 同上 | 0，45 passed |
| r09_original_red | 02:26:32→02:26:35 | gen-card-r1/backend | 1，16 passed/1 failed，0error/skip；原tree |
| r09_combo_green | 02:26:57→02:27:00 | 同上 | 0，原17 passed；上述组合tree |
| r09_combo_exact_final | 02:29:15→02:29:16 | 同上 | 0，1 passed；上述组合tree |
| ruff / format | 02:24:48→02:24:48 | gen-tmo-r1/backend | 均0，models+原新增测试共6文件 |
| mypy src | 02:22:41→02:22:55 | 同上 | 0，101 source files |
| CBM index/schema/qualified trace | 02:22:41→02:25:41各独立命令 | 同上 | 分别0；非连续运行测量 |
| audit / callers / diff_check | 02:24:48→02:24:54各独立命令 | audit在gen-tmo-r1，其余backend | 分别0 |
| 新自拟tests Ruff / format最终 | 02:28:39→02:28:39 | gen-tmo-r1/backend | 均0，3自拟文件；原R09 bytes复制文件未格式化 |

45是44+QA1的再跑，不与前轮累加。原272及新17全含在289中；R09 red/green为同17案例重放，
精确card1重复复跑只计1个自拟案例。不同版本、重复运行和调用层次不合并为新的统计分母。
本表秒级展示，原回执保留小数；未捕获时点的初始化读取只作工具观察，不冒充逐命令测试回执。

作者原red仍为9 failed/8 passed，全部原raw/JUnit保留；green当时HEAD是基线而有未提交补丁，
本review不把它当冻结测试。本reviewer新自拟tests初次Ruff有12项import/长行/raw regex问题，
窄范围修import后仍9项长行，format后通过；两个失败回执和输出均保留，再跑45+card1绑定最终字节。
没有修改原tests、减阈值或skip。

## 原材料与新材料封存

作者manifest本体raw及Git blob SHA-256均为
`37305c851f70c9c1058e660146c28b2a236a22ddc622424aebb706aaf6ea6ea4`。
49项逐blob/raw/期望hash/bytes/EOL分列检查：49逐字节相同，49匹配期望，0仅EOL差异，0未解决；
manifest本体另计，不写50项业务材料。来源源码LF/checkout CRLF区别另列，不修改字节。
原managed长路径失败、CBM省project前缀的function-not-found、初始search为空及作者E501失败
都在已核对的原材料中保持。作者initial_observations明示部分早期subcommand退出码未单独捕获；
本次没有补造这些值。

新run的artifact_manifest.json封存本报告、脚本、请求、逐条回执、原始输出、JUnit、
作者材料audit和组合tree证据；本体hash见artifact_manifest.sha256。
manifest本体/sidecar、缓存/temp和临时Git index不列入自身；seal及封存后校验回执另存并引用本体hash，
避免循环。封存核验检查主review tracked diff为空、新文件均属允许路径、原R09测试bytes未变，
组合树tracked diff仍只是一份授权模块叠加。

## 八层状态、评分边界与交接

| 验证层 | 本review状态 | 证据/未覆盖 |
|---|---|---|
| unit | passed | 219相关及45独立R05/QA；R09组合17/精确1为fixture |
| contract | passed | 46相关；原错误协议与wire/schema |
| security | passed | 24相关，独立0外发/未知异常/真实transport代码fixture |
| integration | not_run | 0 PG/worker/API/发布事务复验；SQLite只是R09原直接query fixture |
| frontend | not_run | 未建前端/页面 |
| e2e | not_run | 未建立或重跑完整产品链 |
| live | not_run | 0真实DNS/外网/凭据读取/真实模型/来源/资产操作 |
| manual | not_run | 0人工金标/法规裁决/团队复现 |

没有费用开销、性能、吞吐、准确率或连续运行测量；fee保持unknown，空attempts不伪造0费用。
本片为T18/R05的F2/F3/A1/E1共享超时可见与受控预算边界、T31的模型不可用传播提供代码级证据。
不提升真实样本、embedding/rerank、R07单维发布、R09持久化/候选生产接线、整T或阶段评分结论。
源代码与作者文档在本限定行为上一致，未发现需新公共合同或计划变更的偏差。

下一步：主控按冻结47c/df0fa集成此片，在新集成freeze运行G-B相应全阶段回归；
R09原reviewer保留原red并核验正式新freeze，再处理原报告Must1状态。
本review不更新progress，不push，不接受任务，不修改他人工作树，不再spawn。

Not checked：真实并发负载/调度概率、真实模型/费用、PG/认证API/worker、browser、正式R07/R09发布链、
原整卡验收与G-B整阶段复验。

**Verdict: Ship（仅本共享生成错误边界修复）。**
