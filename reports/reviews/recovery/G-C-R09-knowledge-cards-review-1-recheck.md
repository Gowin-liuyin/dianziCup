# G-C · R09知识卡准备片原Must1冻结组合定向复核

记录时间：2026-10-16T03:05:01+08:00。原独立reviewer：
`/root/r09_knowledge_cards_preparation_independent_review`。
意见：**限定Ship；初审唯一P2 Must在本组合代码版本关闭。**
不改原needs_changes报告或旧manifest，不签整R09/T09/T14/T15/T22/G-C，不登记accepted。

What this change does：将预派发预算耗尽的底层网络超时在共享生成器边界转成既有GenerationFailure。
原知识卡捕获逻辑自然包装为固定CardExtractionFailure，保持空attempts和零调用；未给知识卡增加特判。

## 固定版本与本轮边界

新短工作树 `D:/wt/r09-cards-review2`，分支
`codex/r09-knowledge-cards-review-1-recheck`，开始clean，HEAD固定：
`b5ca278d739feac5dba9ca3e693d538a5a8d475e`（组合材料）。
执行代码：`dd36cf78c3d15138683d09c12ea867c0055b9674`，代码tree：
`f0ba5dbe822d828ffaa642ce1f0f047a1b725f27`。
没有在作者活动目录D:/wt/r09-combo-fix内审查、运行或修改。

相对原材料 `ed217564e9cf3571b430d0fe7caa4d3999c7320b`，业务/测试只有两文件，146 additions/2 deletions：

- `backend/src/ai_intel/infrastructure/models/generation.py`
- `backend/tests/unit/test_r05_generation_predispatch_timeout.py`

二者固定Git blob均与共享源提交 `47c47bc2b5d537166ee47a01c2ab14c035466e3d` 完全相同。
原知识卡7个source/test文件和原90项材料的base/组合Git blob保持相同。
dd36到b5ca的160个材料变化仅为作者组合报告、专属run和.gitattributes；该属性diff只有4条精确材料路径，
没有影响业务源文件、默认测试门或全局关闭检查。原docs/progress/contracts/pyproject/lock零差异。

沿用已读AGENTS、00执行索引、03/04合同、恢复R09、原T09/T14/T15/T22及主控
CR-R09_verification_labels；固定组合没有改变这些依据。采用指定Ponytail review5.2.0追踪共享调用边界。
本轮只写本报告和 `reports/runs/recovery_r09_knowledge_cards_review_1_recheck_20261016/`。
未改业务、原tests、schema、依赖、原报告/manifest或progress；未spawn、提交或push。

## 唯一P2的复核闭环

初审触发：合法整次预算1秒，monotonic为100→103，在申请槽前已耗尽。
原 `generation.py:409` 直接抛NetworkTimeoutError，越过原卡入口只承接GenerationFailure的边界。
本组合 `generation.py:409–413` 只在槽申请边界窄捕获NetworkTimeoutError，转为
`GenerationFailure("model_network_timeout") from None`。默认attempts为空，未造token、响应或费用。

原卡源码 `card_extraction.py:292/297–298` 未改；独立精确例实际断言：

- 异常实际类型为CardExtractionFailure。
- code严格等于model_network_timeout。
- attempts严格为`()`, gateway calls严格为0，无卡成功返回。
- `__cause__ is None`，没有泄露来源/模型正文。

精确例1 passed。原17例逐字节复制后17 passed，其中初审预派发失败例转绿；
派发后超时仍保留1个fixture attempt及固定错误码。
共享新17项也独立通过，覆盖四provider、恰好到期/已过期、0 acquire/release、
后续slot可用、取得槽后仅释放一次和QA包装。
槽申请返回False仍是model_concurrency_timeout，没有释放未取得的槽、重试或模板回退。
没有吞并全部Exception，现有预算/等待时限没有放宽。

**Must fix：本限定组合未发现。Should fix / Nice to have：没有带具体复现的新增问题。**
初审Must1仅对本新冻结组合关闭；ed上的原失败结论仍有效，原报告/原red未改写。
本轮没有重复扩大补丁或修改业务实现。

## 独立环境、命令和测试

专属环境为本run的`.venv`。实际执行
`uv sync --frozen --offline --no-install-project --python D:/dianzi/backend/.venv/Scripts/python.exe --link-mode copy`，
exit0，离线从既有缓存安装79个锁定包，Python3.12.13，没有依赖或模型下载。
随后所有pytest/static/audit都用本run独有Python，sys.prefix和实际card/generation模块路径断言通过。
PYTHONPATH只指向本短工作树src/tests/tests-unit，DATA_MODE为fixture，使用白名单环境字段，未取秘密值。

命令真实argv、cwd、+08开始/结束、exit和raw stdout/stderr均在同名回执，
[command_index.json](../../runs/recovery_r09_knowledge_cards_review_1_recheck_20261016/command_index.json)
按实际JUnit汇总。pytest cwd为本WT/backend，使用`--no-cov -q -p no:cacheprovider`，
JUnit/basetemp均在专属run，没有改覆盖门、金标或分母。

| 命令标签 | +08实际开始→完成 | child exit/结果 |
|---|---|---|
| independent_17 | 03:01:15.876155→03:01:19.908172 | 0，17 passed |
| exact_card_timeout | 03:01:15.810180→03:01:18.018921 | 0，1 passed |
| focused | 03:01:55.819508→03:02:01.523096 | 0，66 passed |
| unit_regression | 03:01:55.832028→03:02:06.218931 | 0，268 passed |
| contract_regression | 03:01:55.668145→03:02:04.296144 | 0，76 passed |
| security_regression | 03:01:55.827506→03:02:01.494048 | 0，36 passed |
| original_t22 | 03:01:55.827506→03:02:00.474775 | 0，6 passed，原C01–C06 |
| shared_17 | 03:01:55.820504→03:02:01.029267 | 0，17 passed |

上述JUnit均0 failed/error/skip。相关268+76+36经case身份去重确为380；
focused66及原T22六例全部包含在380内，不能再相加为446或452。
原17、共享新17和精确1例分别列出，不把同一个baseline/after重放变成新的独立分母。

before证据来自本人旧封存：`independent_boundaries_sqlite_final.xml`为17例、16通过/1失败，
唯一失败是`test_expired_client_deadline_is_error_with_one_attempt`。本轮逐hash核验原封存，不重新运行before，
没有拿组合作者的通过报告替代独立after执行。
原17文件raw SHA-256仍为
`76ca4d4064f65bfd08846a6e57a2c4fde087a10d6422d563094b412890058bbf`，未格式化或放宽断言。

原17和36 security回归继续覆盖私有三层记录不可读且0模型调用、缺权限、模型嵌套注入、格式错、
HTTP401/429及坏引文整卡失败；partial/缺范围、草案与正式、建议与义务、引用存在≠语义支持继续保留。
内存SQLite只是原直接query fixture，不是PostgreSQL集成。共享GenerationClient执行的是fixture wire，不能算live。

Ruff/format对原7文件+共享2文件均exit0；mypy对generation/card_extraction/knowledge_cards三source文件exit0；
source diff --check exit0。材料审计、模块绑定、rg、CBM各命令exit0，封存命令准确时钟另见回执。
没有本轮失败或skip被改写，没有性能、吞吐、准确率或连续运行指标。

## 当前调用链与尚未接线的范围

官方portable工具实际运行在WSL Ubuntu-22.04 root，专属缓存
`/tmp/dianzi-cbm-r09-cards-recheck-20261016`，专属project `r09-card-recheck-b5ca-src`。
真实help、fast src index、schema和完整qualified trace都有原始输出；1314 nodes/6550 edges，
0 not-indexed/partial/unusable。默认排除assets/缓存，不声称全仓图。

qualified追踪card/generation/grounding/candidate，再用rg全src/tests核对。
GenerationClient入向有grounding、extract_knowledge_card、GroundedQuestionService.ask；
build_knowledge_card只有extract调用，卡入口生产caller仍为0，rg也只找到定义和直接tests。
实际可见链为已有QA→grounding→共享generate，以及本片直接测试extract→共享generate。
没有把图中存在节点、测试调用或共享修复Ship当成R09生产能力。

verification_label(False,False)仍为unknown，字段保持model_hypothesis/candidate/unverified，
无自动资产推断。既有research_links的语义强关系发布缺口和原R09真实资料/PG/问答接线仍未完成；
没有新增发布、检索或资产调用，也没有因安全独立准备而建议删除功能。

## 四套原材料核验和新封存

[materials_audit.json](../../runs/recovery_r09_knowledge_cards_review_1_recheck_20261016/materials_audit.json)
逐项保存raw/Git blob hash、大小、schema与EOL区别，四套清单分开核对：

| 清单 | 实际成员键/数量 | 本体raw SHA-256 | 独立结果 |
|---|---|---|---|
| 原R09作者 | files/90 | 816eaf1ae985e07c35c1fee5753576d6e7ca43f6bd526cbe756dbc7914fb790f | 90固定base/组合blob相同，0未解决 |
| 原本人R09review | files/121 | d8eb2e34edf1199224778c58b31a13622715854014907b59ea315e9fc8631fba | 121原raw全部匹配，原报告/17/red保留 |
| 另一独立共享Genreview | artifacts/121 | 6b4a9062c1aeb9fb042b58e8ead1b30c4c63798a2b5dbb79361cdd3b33b260f0 | canonical121原raw全部匹配 |
| 组合作者 | files/129 | a851dbef8b38575aadf13ca08cae099418d051c11004adc2a98d9747422e28ac | 129原raw全部匹配 |

共享Genreview121与本人旧R09review121是不同证据包，不能混称或相互替代。
原作者90项中，83项checkout与Git只差CRLF、7项逐字节相同；期望hash有84匹配checkout raw、
13匹配固定Git blob（其中7项同时匹配，不能相加成97）。全部已有原始字节/hash依据，未重写或清洗。
原作者manifest固定Git blob hash为8bdb12d91307f643e10d3e5a8ea2246f2ddb0cf8e2aee9bc13fd7adef59f93d5，
与raw816e不同仅是换行表示。
组合129项中128项raw/Git逐字节相同、1项CRLF区别；129全部直接匹配其manifest raw期望。
没有把LF/CRLF或历史广义diff日志尾空白当作源代码篡改，源码diff检查另行通过。

共享generation固定LF blob SHA-256：400c6a23f373e12ec77748108006e55ce30d8aec62bad10d88f014309d3e475b；
本checkout CRLF raw：08d26f0bc5ea4987a51ae4b499d1771c06eab6ec249945aa30080a7eca4ee1e3。
二者47c/dd36/b5ca的Git blob完全一致，卡源码Git blob保持原02bea/ed版本。

新run的artifact_manifest.json封存本报告、脚本、回执、raw输出、JUnit、调用图和四包审计；
本体hash见artifact_manifest.sha256。自身/sidecar、venv/cache/pytest temp不入自身清单；
seal及封存后核验回执另存并引用本体hash。封存再次检查tracked diff为空、新文件均属于本报告/run，
原17bytes及旧报告/manifest仍保持，HEAD仍固定b5ca。

## 状态、评分边界与下一步

| 验证层 | 本组合复核 | 范围 |
|---|---|---|
| unit | passed | 268相关、共享新17、原17及精确1，fixture |
| contract | passed | 76相关、原T22六、focused66，去重关系如上 |
| security | passed | 36相关与原17私有/注入/错误边界 |
| integration | not_run | 0 PG/worker/认证API；SQLite不计PG |
| frontend | not_run | 0 browser/页面 |
| e2e | not_run | 未建立R09产品完整链 |
| live | not_run | 0外网、0真实模型/来源/机制案例，未取凭据 |
| manual | not_run | 0人工金标、0团队复现、0法规适用裁决 |

仅为F2/F3/R1候选引用和共享失败合同提供代码级证据，无计分提升或生产可用声明。
合同/计划没有新增偏差；不能按原聚合pending反推无实现，也不能按本片Ship把整R09置accepted。
下一步由主控按本固定组合/清单整合，再推进真实官方正文/三机制目录、PG候选审核账本、文献语义关系、
正确时点检索问答和界面；这些仍需相应独立验收。

Not checked：真实PG/网络/模型/费用、browser、资产执行、服务运行、真实负载性能、人工标注、holdout及整卡/阶段验收。

**Verdict: Ship（仅固定dd36cf78/b5ca278上的知识卡准备组合；关闭原P2 Must1，不签整R09/T22/G-C）。**
