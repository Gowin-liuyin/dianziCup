# R07 · 输入切片独立评审 Must 修复材料

状态：awaiting_review；输入切片实现 complete，R07/default App 接线 partial。未 accepted、未 push。source SHA `7aeb85ae8277c048fb762dbc705436602cb18f9d`，WT `D:/wt/r07-input-capabilities`，分支 `codex/r07-input-capabilities`。原 source `7dae1d82363d8459f3546fee4b92137559dcb5aa`、原 material `eb6daced5f2467dc56ade15857e60a1af9486db0`、中间状态修复 `9c4991a218e3d7208d8c314a3992cd6c499e0b4b` 和历史红项保留。本文是新的修复报告，原报告描述其冻结窗口，不能把新结果拼到旧窗口计通过。

本轮改动6文件：field_sources.py、model_fields.py、taxonomy_inputs.py、test_r07_input_capabilities.py、原输入CR补充及新CR-R07_context_validation_seam.md。新source commit 214 additions /136 deletions。累计本切片4个source、4个直属测试、2个CR。原evidence_selection有界选择和source全文/roster不改。root依赖48b56033仍使用exact PyYAML6.0.3和types6.0.12.20260906，本轮未编辑依赖/公共schema/settings/worker/gateway/catalogue/API/migrations/locks/progress。

唯一共享文件field_sources.py是root明确新增授权：采用root创建2026-10-16T06:22:44+08:00的CR原字节版本，已更正调用者为EvidenceGraphReadService._validated_support，raw SHA256 `1e663e40ceca3c6b4cdf266669b36055f6835ebce0d1c2afd39c18ca4fe79d31`。源代码rg与自己WT CBM索引确认仅model_fields._generate_field和该Graph方法直接调用；field_candidates.py不存在，publication不直接调用。此前关于publication重验证覆盖limitation的猜测已撤回，不记缺陷。持久input_selections缺口仍真实，由root接线。

根因修复：原完整原文PyPI widget >=1.0,<2.0，遗漏必要Only when tools enabled且模型伪造fixed=99.0时，validator先context_missing短路，旧owned层把它当选择缺口BLOCKED，掩盖坏boundary。现在所有quote/hash/身份/value/boundary/target/limitations先通过，再由唯一共享规则计算FieldContextGap(revision/block/原block-relative Unicode start/end)。FieldEvidenceError新增default-empty typed gaps，原str/code接口不变；owned模型层删除复制正则。只有selection.incomplete且全部服务端gap确与omitted ranges相交才BLOCKED。合法但模型未见的quote使用field_evidence_outside_selection/BLOCKED；可见必要条件、伪造quote/ID/boundary/混合bad候选仍FAILED，empty仍PENDING。支持规则、URI信任、状态枚举、schema、50条/16384字符/65536 bytes、单维1024 tokens/20s/1wire不变；没有升级候选为事实。

Parser公共构造边界修复：urlsplit/parsed.port遇坏port和未闭合IPv6只抛taxonomy_source_uri_invalid，无原URI回显。YAML用成熟SafeLoader构造scalar key后判等，true/True、true/1、1/1.0、null/~重复全部拒绝；非scalar/customtag/alias与NaN/Inf key拒绝。解析阶段先保留TaxonomyInputError的alias/duplicate/budget/tag等具体码，再将成熟scalar构造ValueError/KeyError及既有解析错误归一taxonomy_yaml_invalid；不捕任意业务异常。!!int nope、!!float nope、!!bool nope、2026-99-99经同一个入口处理，无逐值特判。

冻结版本继续使用PROMPT_VERSION=r07-model-fields-2、SELECTION_VERSION=r07-field-selection-1、输出schema=r07-model-field-extraction-1。本行为尚未正式接线；root首次策略fingerprint须使用最终source SHA和这两个常量，不能复用旧持久job。shared seam与owned判断必须作为同一行为单元回滚，数据库无迁移/回填，旧历史不重解释，raw CAS不删除。未改阈值/gold/probe inputs/评分分母。

实际复跑命令入口为 `backend/.venv/Scripts/python.exe reports/runs/recovery_r07_input_capabilities_20261016/check_inputs.py <mode>`。helper JSON保存完整pytest路径参数/cwd/Asia-Shanghai起止/exit/独立test库，日志和JUnit保存真实计数。`check_review_probe.py`只读原reviewer文件，PYTHONDONTWRITEBYTECODE防修改其缓存；这属于作者复跑，独立结论须原reviewer另给。

| 层 / mode | exit / 计数 | 原始材料 | +08 起止 |
|---|---|---|---|
| unit | 0 / 33 passed，0skip | unit_062751 | 06:27:51起，详细JSON |
| contract | 0 / 11 passed，0skip | contract_063100 | 06:31:00.699–06:31:03.156 |
| security | 0 / 7 passed，0skip | security_063100 | 详细JSON |
| integration真实PG+完整来源67 blocks | 0 / 12 passed，0skip | integration_063544 | 06:35:44.085–06:35:49.943 |
| 原模型regression | 0 / 143 passed，0skip | regression_062906 | 详细JSON |
| fieldset四字段相关 | 0 / 102 passed，0skip | fieldset_063100 | 详细JSON |
| Graph unit/contract/security | 0 / 10 passed，0skip | graph_062906 | 详细JSON |
| 原reviewer23探针原inputs | 0 / 23 passed，0skip | independent_original_062802 | 06:28:02.596–06:28:05.646 |
| 原reviewer真实PG原inputs | 0 / 7 passed，0skip | independent_pg_062953 | 详细JSON |
| shared PG Graph/source coverage/publication/ACL/rule | 0 / 81 passed，0skip | shared_pg_062953 | 06:29:53.060–06:31:34.692 |
| Ruff check/format、mypy4sources、source diff | 各0 | static_commands_062906.json | 06:29:06.470–06:29:08.020 |

原143构成为model_fields56、single_model_dimension41、model_field_root_causes46，不按旧122摘要报数。shared PG使用原fixture明确断言的专用test_dianzi_r06_catalog_r10_graph_20261016库，先核专用test用户所有权，fixture各自UUID schema；其余PG使用新隔离test库，不接生产。敏感连接仅内存读取，输出脱敏。Graph现有Starlette弃用warning保留，非本次依赖变更。实际67-block来源由原recorded NVD经原source worker入PG；测试只用标记offline codec，1wire/1024/空回答→unknown，不称live模型正确。

新增失败过程全部保留：independent_original_062751为19 passed/4 failed，删除复制helper后旧调用仍传4参数造成TypeError，改为typed(error,selection)后23通过。shared_pg_062906为34 passed/47 setup errors，临时新test库名未满足原Graph fixture固定库断言；只改运行helper使用其原专用test库并核owner，原fixture不改，81通过。independent_pg_062906为缺少原integration测试模块的collection error，补本WT正常测试模块路径后7通过。replace_context_classifier.py首次默认GBK读UTF-8失败，修脚本encoding；CBM初猜_graph_field_supported不存在的输出也保留，更正实际_validated_support。初始fix1某些contract/assertion红和所有此前原红均有各自日志/XML，不覆写为绿。

最新版source离线重放同一CAS：replay_fix2.py于06:35:19.255–06:35:23.320+08执行replay_catalogues_fix2.py，exit1。CWE4.19仍969 IDs，ATLAS deprecated legacy5.6.0@3259f388d19cbcca11bacf12a0ef97f4198f711b仍170 IDs/170可引用原Unicode identifier行；对同commit旧dist/schemas完整schema仍126 anyOf errors。没有修改原bytes/schema，也没有把窄parser成员性与官方完整schema通过混为一谈。catalogue_replay_fix2_observation.json保留两者原hash与具体错误。旧组织YAML/schema404、原595e42a9四个NVD子job budget exhausted/0wire保留；现代官方组织只被本parser接受，共享field_sources旧信任URI未改。

本轮网络/付费/模型/测绘调用均0，全部真实公开采集仍只原批准6GET：API200、旧YAML404、旧schema404、CWE200、新YAML200、新schema200；fixed大小/90s及追加45s、redirect0、DoH固定Cloudflare/2s限制保留。原bytes只在仓外D:/dianzi-private/r07-taxonomy-cas，manifest保存4对象hash和精确URI。Attempt fee仍unknown，不能把离线mock说成零费用live。

材料：本轮独立fix2_frozen_code_manifest.json核4source/4test/2CR原bytes、LF和Gitblob hash；fix2_artifact_manifest.json与fix2_material_fingerprint.json另冻，不覆写原artifact_manifest.json（rawSHA8138f507572bedf48d57b6c7e81b398e206feb5f0067847e0f727d7a2e52fb84）。旧tracked helper的新运行扩展可从原eb6daced取原bytes，原red/raw日志未改。原材料diff-check因真实失败log尾空白及CBM原输出EOF空行仍exit2；本次新材料staged diff-check也于06:37:36.628–36.713+08返回exit2，完整日志及独立命令记录fix2_material_diff_check.log/fix2_material_diff_command.json。源码cached diff-check exit0；不修剪raw日志、不擅改公共attributes，root决定范围精确的日志attrs例外。该真实材料格式未通过项不伪写成源码问题或通过。

未运行/仍缺：frontend、e2e、live模型、manual均not_run；真实taxonomy默认App/collector/context公共字段、现代URI正式support、policy fingerprint、durable coverage metadata由root另接。parser/PG窄loader已经校验ACL/current/CAS，但不是默认全taxonomy能力验收。官方完整schemafailed，不绕过；live原blocked不计通过。评分仅提供R07/F2/P2的有界词法输入/可回溯假设与E1边界测试材料，没有准确率、性能、持续时间或盲测分数。

下一步：原非作者reviewer在最新source SHA独立复核原23+PG7+真假未见span/falseboundary；通过后root统一接线。保持awaiting_review，此切片不自行继续其它任务。
