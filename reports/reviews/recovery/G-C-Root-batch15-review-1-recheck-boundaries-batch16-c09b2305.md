# G-C · Root批次15原两边界问题定向复核

首次创建/写作：2026-10-17T08:16:01.0993845+08:00（实际文件创建时间）。

结论：**原两个finding定向闭合，允许Root集成本窄切片**；不修改Root/R18状态，不登记accepted，不签G-C阶段。本人仍未参与修复。原初审及3fail、R07截止时间原红保留在 `d65ae0a45121b0acb29d5e76d286524a28c21b8c`，没有重写。

源码固定 `36fb2043f4e1a56030864b86d26f0c2cb870746c`，tree `a00d4950f66149b8386f355254067e21d5f1ea60`；adapter修复 `b242d3ac9a423e9fd85a19d0f44db129a3ce7e06`，HTTP修复为上述36fb；比较基线 `0f8c1f6d047387cfca8a62f8dbc352b8c6415b96`。作者材料 `19c5829f58dd03f7bd48a677cb66eccd22dddd33` 只用于定位冻结输入，不据作者172通过或状态文字作结论。

独立工作树 `D:/wt/root-batch15-boundary-recheck1`，分支 `codex/root-batch15-boundary-recheck1`，开始clean。Codex managed创建因两处历史截图Windows长路径失败，失败目录随后不存在；用一次性 `git -c core.longpaths=true worktree add -b codex/root-batch15-boundary-recheck1 D:/wt/root-batch15-boundary-recheck1 36fb2043...` 创建短路径成功，没有改全局配置、清理用户文件或读取作者movingWT来运行。

本轮读AGENTS、执行索引、R18任务卡、公开v2/凭据及HTTP合同、状态和初审。只核四个变更源码/测试及必要调用方，沿用已读Ponytail review和分开的Standards/Spec核查；两个只读协作reviewer均未参与修复。新增内容仅ownreview/ownrun，无业务修改。未触及Root新的App/provider/OpenAPI、R07或其它模块。

## 原问题闭合与兼容性

**Standards：原组件配置借用问题闭合。** 新 `_component_context_evaluation` 用成熟四态 evaluator，对裸组件创建仅保留请求组件的snapshot，将configuration清空、tools/channels/network设None、inventory completeness和declared scope保未知；缓解事实参数沿用空集。混合条件不再借某资产的runtime/config值。实际92case含原77及新15，覆盖配置存在/缺失/true/false、嵌套运行条件、缺版本、不完整范围；AllOf(版本false,未知上下文)仍有证据排除，AnyOf(false,unknown)仍不足，没有以白名单拒绝所有混合树而删除已支持的比较能力。

**Spec：原HTTP凭据渠道违约闭合。** `_bearer_credential` 新两行在DianziClient创建前拒任何query_string或Cookie header，之后仍用原Bearer解析。符合 `CR-R18_api_key_credential_seam.md:18` 的query/重复/混用拒绝；该独立SDK无需导入backend。77case含原66及新11：编码/重复/空query、空/重复/无关cookie均401并零backend calls；纯Bearer及原Host/Origin/失败/取消/client隔离/close路径保持。本地实际loopback TCP case还核混合请求、重复/畸形header拒绝和纯Bearer discovery成功、owned transport全关闭；后端仍是显式fixture，不计真实产品backend/live。

原独立oracle未经改动复制到ownrun，SHA256 `be03356c54e2f69382a85e14babcfdfc4e74c1a09143b073864e5a7f34153d2c`，与初审/作者oracle_manifest相同。原三个node实际3/3通过：裸snapshot config-false的排除借用转insufficient，以及两个MCP query/cookie组合转401且零backend calls。原红输入、期望、阈值、金标没有改变；总172仅为本次三个不重叠组的实际3+92+77，不累计初审/作者/其它版本。

selector兼容只读固定 `36b969bd9b98dcbb53f9eb3a4ffcb4d74cc77df9`。新/初始adapter和selector依赖的 `_rule_targets_only_component` AST逐项相等，未改变private分类。selector第95行调用该helper，第97–105行自身仍将mixed runtime leaf记 `unsupported_component_rule`，本修复没有承诺selector扩大范围。真实PG7属于另一次独审，本人不重计；Root未来集成137case和默认公开入口需在新固定版本另验。

## 本人实际执行

全部证据位于 `reports/runs/g_c_root_batch15_boundary_recheck1_20261017/`。各label `.command.json`保完整argv、cwd、起止、exit、进程身份，`.owned.json`保NativeJob限额、使用量、工具hash，pytest保完整stdout/stderr/JUnit。普通60s，512MiB/process、1GiB/job、CPUrate833/24约2核、进程cap10，所有残余0；没有提高阈值或换成skip。

| label / command | exit | test/failed/error/skipped | Windows峰 |
|---|---:|---|---:|
| original_three_oracles：pytest ownrun/test_review_negative.py --no-cov -q --junitxml | 0 | 3/0/0/0 | 4 |
| adapter_original_and_context：pytest public_write_adapters unit/contract + r18_component_context_boundary --no-cov -q --junitxml | 0 | 92/0/0/0 | 4 |
| http_original_and_channels：pytest test_http_transport + test_http_credential_channels --no-cov -q --junitxml | 0 | 77/0/0/0 | 4 |
| style_four_files：ruff check 四个变更文件 | 0 | 0tests | 5 |
| types_backend_adapter：mypy src/ai_intel/api/public_write_adapters.py | 0 | 1 sourcefile，0tests | 4 |
| types_sdk_transport：mypy sdk/python/ai_intel_client/http_transport.py | 0 | 1 sourcefile，0tests | 4 |
| source_oracle_selector_provenance：provenance.py +固定Git blob/AST | 0 | 0tests | 6 |

源码 `git diff --check 0f...36fb -- backend sdk` exit0。四个源码/test checkout仅CRLF规范化后均等于36fb Git blob；provenance记录raw/blob哈希和selector依赖比较。原be033 oracle raw保持。没有把运行输出、fixture或词表缓存当产品数据。

## CBM和边界

Root安排UI之后本review优先窗口。UI任务completed并由其已保存receipt核同cache `/tmp/dianzi-cbm-root-batch15-review1-20261017`，分别full index两个独立source project，指向本36fb工作树backend/src与SDK源码，不索引秘密、fixture/holdout或reports。

backend 2998nodes/17810edges，SDK 211nodes/900edges，均parse_partial/unusable/skipped/not_indexed=0。两个组各4个CLI命令：index/schema/2条双向trace，全部exit0/isErrorfalse。Windows峰7；guest完整ancestors至PID1峰6，采样峰RSS分别39104512/39112704 bytes，affinity[0,1]，自有残余0。guest GOMEMLIMIT是软限制，未宣称硬内存limit；每组普通60s/原NativeJob预算不变，没有终止共享daemon。

实际trace和源码/rg交叉确认 `stack_current_assessments→_component_context_evaluation→evaluate_condition_tree`，新helper 1caller/14callees；HTTP `_authenticated_request→_bearer_credential`，1caller/2callees，入口host/origin/body/限额及client lifecycle保持。helper trace原始SHA256 `2a9f8903110b74fe35256d10cb5ff84e267d52d7de18fb13eb56ce957da1271a`；SDK凭据trace `f9e4afedc9d7ef64af28af5af1381885804a4fa533e61b0baaa31322184c04f0`。固定index各自保存源码raw snapshot，未复用0f旧trace。selector只读源码/AST依赖核查见provenance，不以CBM不存在的0f caller证明Root新增接线。

真实PG、实际MinIO、Root默认App/公开producer/OpenAPI、跨版本集成、Codex/Claude/OAuth、浏览器、付费模型、live/manual、整仓coverage/类型和G-C检查点本人均not_run。原R07 `.812>.8`失败不由此窄修复消除。权限/事务/幂等/版本/失效的原业务服务及冻结schema未改，新helper只投影请求具有的证据上下文，HTTP只增加早拒绝；没有新增状态库、依赖或抽象平台。当前未发现可证新回归。

评分证据只支持原两个F2/E1/X1边界的修复闭合；下一步由Root在新集成SHA复验默认producer和selector，并按各自授权完成PG/live。定向verdict：本窄修复可集成。此材料不能授予整R18或G-C通过，也不授权push。

封存检查：报告及ownrun脚本的暂存diff-check exit0；全部raw的同检查exit2为保留CRLF行尾，原诊断180523 bytes另存raw_diff_check.stdout.log，不修剪原输出或关闭全局检查。ownrun使用精确文件名-text属性，原be033 oracle也单独标记，保持其字节。材料提交仅ownreview/ownrun。
