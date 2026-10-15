# R05-semantic-runtime-preparation · 实施报告

状态：`awaiting_review`；本独立包实现 `complete`。整个R05仍 `partial`，本报告不签整T18/T30、阶段或产品验收。基线31c2866；共享限额代码77add60；语义代码bfea9fe。独立分支codex/recovery-r05-semantic-runtime，未push。

## 最新Must1修复候选 · 2026-10-15

当前代码1e77c0d，状态awaiting_review；原bfea9fe首次独立初审发现初始化锁泄漏，不能按下方原自检结果登记accepted。修复交原初审者定向复核，作者不签关闭。公共helper/PDF仍77add60未改；详细新证据见报告末尾。

## 范围与授权

读取AGENTS、执行索引、R05 manifest、T18/T30及架构/模型/资源/测试合同；使用Ponytail 5.2 full。主控冻结接口并授权本机真实中英模型、仓外缓存和依赖。本轮新增semantic.py及unit/contract/live测试；后续主控唯一委托新增process_limits.py、PDF原限额函数改为共享委托及直接资源测试。没有修改锁文件、settings、公共schema、进度、PG、认证、生成模块或前端。

CBM v0.11.0在本WT backend/src和独立仓外cache索引：首次958nodes/4496edges；新增语义模块后992nodes/4649edges。源码rg确认既有validate_embedding_batch无业务调用方，本适配器成为新调用方；旧T18回归实际复跑。公共严格向量校验由主控另行处理，本适配器先严校再复用EmbeddingResult。

## 固定模型、来源与接口

选择官方FP32 ONNX，避免下载pickle或执行remote code。BGE-base官方ONNX约1.112GB，因本轮2GiB进程约束由主控批准改为较小官方多语种CrossEncoder；不是宣称其与BGE等效，也没有降低正式指标或分母。

| 模型 | 官方修订 | 图大小/许可 |
|---|---|---|
| [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3) | 614241f622f53c4eeff9890bdc4f31cfecc418b3 | 470268510 bytes；MIT |
| [cross-encoder/mmarco-mMiniLMv2-L12-H384-v1](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/tree/1427fd652930e4ba29e8149678df786c240d8825) | 1427fd652930e4ba29e8149678df786c240d8825 | 470883696 bytes；Apache-2.0 |

官方模型卡明确E5中英/多语种、query: / passage: 前缀、masked mean pooling和L2 normalization；CrossEncoder卡包含中英语言、query/passage pair和logits。真实图已核实：E5 int64 input_ids/attention_mask/token_type_ids，输出float [B,S,384]；CrossEncoder int64 input_ids/attention_mask，输出float logits [B,1]。两个官方tokenizer的pad_id均1，中文token实际编码非空。官方卡基准没有记为本系统指标。

图和tokenizer按官方LFS SHA256/size核验；两个config按官方Git blob核验并记录实际SHA256。全部6文件975319142 bytes，详见artifacts_verified.json。缓存、venv、CBM、mypy位于C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime；2026-10-15T15:34:54+08:00已占1405461099 bytes（含残留partial及依赖），权重未进仓库。

冻结接口：LocalSemanticModels(Path可信固定cache根, timeout_seconds=30)；embed_query(str)、embed_passages(tuple[str,...])返回既有不可变EmbeddingResult；rerank(query,tuple)返回本模块RerankResult和RankedPassage(index,score)。批次1..8，空/无效Unicode/字符超限拒绝；真实tokenizer含前缀与special tokens或pair超过512就拒绝，不截断。向量有限、纯float、非零、384维、L2和条目数严格；raw logits有限，稳定降序，保留重复文本与所有原始索引。

model_version为repo@精确revision;space=SHA256(space_description)，长度142/154；description固定权重/tokenizer SHA、FP32 codec、prefix/pooling/normalization、512上限及维度。模型/分词器/codec改变必须新空间与新索引。

每次调用使用spawn和内存Pipe，单并发，整次30s包含SHA校验、模型加载和推理；错误分输入、不可用、超时和worker失败，无fixture后备。仅从已验hash的固定本地文件加载，关闭ONNX telemetry，无hub下载或网络模型调用；不引入可执行remote loader。进程入口在import重库之前应用2GiB和CPU30s硬限，ONNX线程<=2、并行tokenizer关闭，调用后子进程回收。

共享bound_process_resources严格拒bool/超限数；Linux使用RLIMIT_AS/CPU，Windows复用原Job结构与0x100/0x2000，加0x2 user CPU限额。PDF保留512MiB/15s入口，Windows新增CPU硬约束是本轮明确收紧。微软原生CPU检查具有周期性：[官方结构说明](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information)。

## 实际检查与结果

日志根：reports/runs/recovery_r05_semantic_runtime_20261015/。命令与+08起止/退出见各command.json；pytest数量来自XML，不合并重复复跑数量。

- `project-python -m pytest tests/unit/test_r05_semantic.py tests/contract/test_r05_semantic_contract.py tests/contract/test_t18_model_clients.py -q --no-cov --junitxml=.../semantic_regression.xml`：57 passed，exit0。其中47新语义unit、4新contract、6既有T18；包括真实spawn缺权重/修改文件fail-closed和回收。
- `project-python -m pytest tests/unit/test_r05_process_limits.py tests/unit/test_r04_real_parsing.py -q --no-cov --junitxml=.../resources_windows.xml`：49 passed，exit0（16资源测试与33既有解析回归）。
- `project-python reports/runs/.../probe_process_limits.py`及`wsl -e env PYTHONPATH=<WT>/backend/src python3 <WT>/reports/runs/.../probe_process_limits.py`：Windows与Linux真实小进程内存/CPU负例各2项，命令exit0。Win100MiB拒200MiB allocation子进程exit1 MemoryError；CPU1s原生终止exit3221225540、wall7.453s，8s父兜底未触发。Linux memory exit1；CPU exit-9、wall1.112s。WSL实际Python3.10.12只证明共享标准库限额，不是项目Python3.12全栈Linux验收。
- `ruff check`和`ruff format --check`覆盖7个源码/测试文件：exit0；`mypy --cache-dir <仓外cache>/mypy src`：74源码文件通过、exit0。
- 冻结bfea9fe之后，`project-python -m pytest -o addopts= tests/live/test_r05_semantic_live.py -q -s --junitxml=<log根>/live_final.xml`：3 passed、0skip，15:32:17.039510–15:32:27.725273+08，pytest9.53s。实际完整调用中文query1.766s、英文query1.718s、3正文batch1.735s；4候选重排1.906s。真实512超限embedding/rerank均拒绝。采样进程家族RSS峰1265991680 bytes；每推理原生2GiB限额真实实施。
- 重排原始索引[3,0,2,1]，0/2重复正文同分保留；中文同义证据2.00285、英文同义证据-0.25060、无关正文-6.94195。这里只展示一次小样本行为，没有准确率、召回率或质量阈值。
- graph_e5.json / graph_mmarco.json含真实图签名、固定空间和分词器。图检查家族RSS分别910098432/844267520 bytes。

完整调用是每次重载模型，操作系统文件缓存已温热；不宣称冷机器启动、全系统QA SLA或生产吞吐达标。unit/contract/security只在文件完整性、输入输出与限额子进程范围passed；跨租户、全链路安全、PG写入、检索融合、QA、前端和e2e全部not_run；manual not_run。

## 失败、中断与资源事实

初始stdlib官方单流下载停在4MiB后由本Agent停止，命令exit1，停止精确时间没有独立receipt，不编造。随后成熟官方huggingface_hub1.33.0/hf-xet1.7.0逐文件固定修订下载，token=False、TLS未关闭、无整仓下载。第一SDK段15:13:52.355013–15:26:52.096164+08达到780s监督截止、exit1；保留partial。主控明确批准在原30min范围内同SDK恢复，第二段154.593s、15:31:22.773311结束、exit0，全部hash核验；第二段家族RSS峰320847872 bytes，未留下下载worker。整个下载及实测从15:07:53到15:32:54，约25min内。

第一SDK监督RSS只覆盖Windowsvenv launcher，不能用其5799936 bytes当真实峰值；graph_e5_launcher_only.json同属无效峰值历史。发现后修正为全部owned descendants并重新取得graph/live家族峰值；这些初始值不进入最终性能证据。第一cache-venv live pytest因缺项目conftest所需pydantic，exit4、未执行测试，是环境问题；随后使用项目Python3.12.13加仓外隔离runtime依赖，真实live通过。失败日志未删除、未改skip。

产品运行依赖建议独立optional组固定onnxruntime==1.24.4、tokenizers==0.22.2、numpy==2.4.2；psutil7.2.2/pytest8.4.2仅证据与测试。全部实际传递依赖版本见runtime_versions.txt。主控尚未锁入与接线，本包状态明确not_integrated，不能声称默认产品已支持语义检索。

## 交接与评分证据

本包为F2/F3/A1提供真实embedding/rerank接口与T18边界、小批次live资源证据；没有证明整个F3/P3/T30/T31或任一评分档次。报告/阶段/依赖合同由主控新CR及新非作者审查确认，作者不写accepted。

下一步由主控统一锁入依赖和模型配置，再对冻结helper与语义接口做新独立review；随后在PG事实/tenant过滤、版本模型空间隔离和真实QA链路接线并验证。当前不需要新服务账号或付费模型；后续缓存或模型变更继续单独核准和核验。

## Must1定向修复与复跑

初审固定bfea9fe，独立探针D:/dianzi/reports/runs/recovery_r05_semantic_review_1_20261015/test_independent_semantic.py::test_pipe_creation_failure_releases_capacity确证：锁取得后Pipe初始化抛OSError，原代码try/finally尚未进入，后续所有调用都busy。初始独立日志1failed+17passed由reviewer持有，作者未修改。

本轮只修改semantic.py与直接unit，代码先冻结1e77c0d，再封存本证据；helper/PDF、模型文件、锁文件、公共schema/settings、progress及其他模块均未修改。

acquire之后的get_context/Pipe/Process/start全部进入保护范围，初始化异常转固定安全错误；尚未赋值的资源不操作，未start的已构造Process也关闭。finally无条件释放容量；两端Pipe和Process分别清理，清理失败不覆盖原安全错误而增加固定说明；原本成功的路径遇清理失败明确报SemanticRuntimeError，没有伪成功或空结果。Windows PipeConnection/Unix Connection均以标准库共同base表达类型，没有Any/cast/ignore。

新增四个初始化位置×OSError/RuntimeError共8负例，每例同时检查安全消息、容量释放、已取得资源关闭及下一次合成正常query可用；另2例检查清理错误保留主错误/成功路径显式失败。原代码初始作者红测10failed（must1_red.log/XML保留，其中末例受前一清理泄锁污染；不是10个独立根因），修复首次隔离绿测10passed/47deselected。首次绿测未独立捕获墙钟起止，不编造时间。

冻结1e77c0d后的完整`pytest tests/unit/test_r05_semantic.py tests/contract/test_r05_semantic_contract.py tests/contract/test_t18_model_clients.py -q --no-cov --junitxml=.../must1_regression.xml`为67passed/0skip、exit0（57当前语义unit、4新contract、6旧T18）；精确+08起止/command见must1_regression.command.json。Ruff与format覆盖两修改文件exit0；全74源码mypy再次通过，详情must1_static.command.json及各日志。

同一verified cache、同一模型空间且无重新下载，真实live3passed/0skip、exit0；2026-10-15T15:57:07.284604–15:57:19.591483+08，完整进程家族RSS峰1251942400 bytes。子进程原生2GiB/CPU30s约束保持；must1_live.log/XML/command.json保留实际中英embedding、稳定重复index重排及512超限拒绝。该复跑验证新初始化/清理可以完成真实调用，不新增准确率/召回率或产品SLA声明。CBM再次索引本WT backend/src，记录must1_cbm_index.log。

不重跑未修改的共享helper/PDF资源集，原49项仅为历史证据；本包仍not_integrated，PG/QA/UI/E2E/manual仍not_run。修复已发送主控及原reviewer/root/r05_semantic_independent_review，待其新冻结版本定向意见。
