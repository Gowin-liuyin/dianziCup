# R07 · Fix3 成熟标量构造边界

状态：awaiting_review；该修复实现complete，整R07/default App接线partial。未accepted、未push、未spawn。source `5b3869e4dcdfa16c0ae393cd73acae4cf27efbf9`，WT D:/wt/r07-input-capabilities，分支codex/r07-input-capabilities。前source7aeb85ae/material4c339e6f及其run和manifest不动；本轮所有新日志位于独立recovery_r07_input_capabilities_fix3_20261016，不把新增红项追记成旧输入已通过。

改动3文件、91 additions/1 deletion：taxonomy_inputs.py仅新增ScalarNode成熟构造入口6行、直属unit新增42案例、独立CR-R07_fix3_scalar_constructor_boundary.md。原33unit断言/fixture保持。没有修改model_fields、field_sources、evidence_selection、inputs、公共schema/context、依赖、source目录/collector、网关、API、worker、settings、数据库迁移/锁、progress或评分/阈值。raw官方bytes仍仓外CAS，未请求新网络/模型/测绘/付费调用。

实证原红：独立reviewer于2026-10-16T06:46:37.486–06:46:42.770+08执行原27探针，26 passed/1 failed；新增metadata: !!timestamp nope使PyYAML6.0.3.construct_yaml_timestamp的regexp match=None后调用groupdict，泄漏AttributeError。原XML/log/command与精确输入已无损另存original_*，manifest保存rawhash；未改reviewer文件。作者在旧7a源码上06:49:09.405–06:49:14.178复现同一26/1红，independent_original_064909。新增有界13种坏scalar×key/value矩阵先unit_064952：exit1、74 cases/12 failed/62 passed。12红包括三种无匹配timestamp与空int、单sign int、空float的原生AttributeError/IndexError；原4Must已有实质通过，新边界没有计入旧通过窗口。

根因修复：在已检查类型/tag/大小/深度/节点的ScalarNode→成熟SafeLoader.construct_object唯一调用周围，将ValueError、KeyError、AttributeError、IndexError、OverflowError转taxonomy_yaml_invalid，from None，无原文回显。业务投影、PG/来源/对象层没有新增AttributeError catch；额外unit模拟非constructor的投影AttributeError，确认仍传播。成熟库处理时间/int/float/bool转换，没有自制YAML parser、时间regex或逐坏值特判。解析外层原alias/duplicate/tag/budget码保留，semantic key碰撞、NaN/Inf key、别名/customtag、depth64/node100000/字节界限不放宽。正常/坏binary均仍taxonomy_yaml_tag_forbidden，不从调查成熟binary构造推导本系统已支持binary。

安装成熟库源码已核：constructor.py rawhash90d8247da78b524c10618fd0e857f54f3d97570fe91b5c5513d024ef3faf88b0。独立scalar_constructor_before/after.json记录13种坏标量、12种正常控制及3种binary的原生错误类别/返回类型、key/value parser结果。before通过Git取原7a源码原bytes在独立命名模块离线重放，after是随后冻结5b完全相同源码；不是把新代码观察标成旧观察。timestamp无匹配是AttributeError，合法regex但非法month/year0/timezone是ValueError，空int/float是IndexError，bool坏值是KeyError；binary库错误是ConstructorError，本parser保持不接受该tag。native观察脚本第一次因直接运行找不到本WT tests模块ModuleNotFoundError，未冒称业务失败；修正本WT明确导入路径后记录观察，其首次完整起止未写盘，not_recorded。

CBM先于业务编辑，06:50:04.282–06:50:25.194+08，对自己WT backend/src独立r07_inputs_fix3_src index/schema/architecture/parser与loader trace，加rg全部src/tests。各exit0，cbm_before_commands.json保存真实命令/起止。parser静态trace报告caller0；rg源码可见load_taxonomy_catalogue以kind条件表达式分发至parser，此动态调用不能因静态0忽略。生产src未发现其它直接caller/default App注册；模型与Graph不直接调用此parser。新窄loader仍须PG source/document/revision ACL/current/CAS校验，本次成功不等于默认App接通。

实际命令主入口 `backend/.venv/Scripts/python.exe reports/runs/recovery_r07_input_capabilities_fix3_20261016/check_inputs.py <mode>`；helper JSON保存完整pytest命令、cwd、+08起止、exit、隔离test库与JUnit计数。作者只读独立reviewer原脚本复跑，不代替非作者审查。

| 范围 | exit / 真实结果 | 材料 | +08起止 |
|---|---|---|---|
| unit：原33+新增42 | 0 / 75 passed，0skip | unit_065327 | 06:53:27.368–06:53:29.606 |
| contract | 0 / 11 passed，0skip | contract_065059 | 06:50:59.459–06:51:01.935 |
| security | 0 / 7 passed，0skip | security_065059 | 06:50:59.527–06:51:01.727 |
| 原模型回归 | 0 / 143 passed，0skip | regression_065327 | 06:53:27.539–06:53:34.206 |
| 四字段相关回归 | 0 / 102 passed，0skip | fieldset_065327 | 06:53:27.414–06:53:29.695 |
| 作者复跑当前原27探针 | 0 / 27 passed，0skip | independent_original_065059 | 06:50:59.007–06:51:03.053 |
| 作者复跑原PG7 | 0 / 7 passed，0skip | independent_pg_065327 | 06:53:27.998–06:53:32.518 |
| realPG输入/来源完整67块 | 0 / 12 passed，0skip | integration_065327 | 06:53:27.996–06:53:33.690 |
| 冻结26原inputs | 0 / 26 passed，0skip | fixed_original_23（命名遗留，JSON确为26） | 06:58:26.882–06:58:30.077 |
| 原23函数集合原inputs | 0 / 23 passed，3 deselected/0skip | fixed_first_23 | 06:59:07.548–06:59:12.633 |
| Ruff/check、format、mypy4sources、source diff | 各0 | static_commands_065327.json | 06:53:27.519–06:53:29.436 |

计数纠正：4c冻结的fix2_original_test_review_probe.py实际在冻结时已有原23加后来3条status/gap控制，共26；此前06:28原23执行结果仍有独立记录。这一快照不能叫23，本文据真实JUnit报26。check_fixed_23.py最初不加过滤完整运行，保留其真实26日志原名；然后用明确-k排除仅新增三控制重跑原23，inputs值不改。没有skip失败，当前27全部运行包含三控制和新timestamp。原模型143仍56/41/46，不改full-input断言；坏quote/boundary/混合候选/客户端gap仍FAILED，合法遗漏才BLOCKED，empty PENDING。

PG仅用专用test用户创建的新隔离test库，连接密钥只在内存，日志脱敏。原PG7同时核taxonomy source的真实URI/ACL/current；原recorded NVD67经原worker保存入PG，offline codec 1wire/1024/empty→unknown，未称live模型成功。当前27探针包括固定CWE4.19的969成员/原ZIP+XMLhash、ATLAS deprecated legacy5.6.0@3259f388d19cbcca11bacf12a0ef97f4198f711b的170成员与170 exact Unicode原行，未改控制。新正常scalar控制覆盖日期/闰日/时区、int十六进制、float/.nan/.inf值、bool/null/str；非有限key继续拒绝。

历史限制继续：旧官方组织两404、原595四模型子job budget exhausted/0wire、官方完整legacy schema126错误/exit1仍保留，不改schema/rawbytes或称latest。新组织URI只被本parser接受，共享field_sources信任规则未改；现代v6未支持。本次没有重新运行官方完整schema、Graph/sharedPG全套（其依赖代码不变且上轮独立实测通过），记录not_run_this_fix；原结果保持历史。frontend/e2e/live模型/manual均not_run，默认App/collector/context/policy指纹/durable覆盖审计仍由root接线，fee unknown。

版本/兼容：prompt r07-model-fields-2、selection r07-field-selection-1、输出schema原r07-model-field-extraction-1均不改。非法未接受source错误由原生异常变安全码，正常目录结果不变；无迁移/回填/历史重算。root首次正式接线须新source SHA，不拿新算法改写旧任务。回滚只退本成熟标量预构造与新增单元矩阵，其余共享context seam和有界选择保持。无新增调用和评分结果，只有R07/F2/P2/E1可核输入边界证据。

材料另冻fix3_frozen_code_manifest/artifact_manifest/material_fingerprint，保存当前11累计owned source/test/CR的raw/LF/Gitblob hash，以及新日志/原Must副本与4仓外CAS hash。验证旧4c191材料的原hash保持，不覆写旧artifact_manifest/fingerprint。源码cached diff-check0；原始错误栈/JUnit含尾空白和CBM EOF，新材料staged diff-check于07:01:21.814–07:01:21.901+08实际exit2，fix3_material_diff_check.log/command.json保存真实结果。保留原bytes，不擅改公共attributes或裁剪红日志，不伪报材料格式检查通过。

下一步：原非作者reviewer对5b新source执行原27/26/23/PG7及成熟scalar边界独立复核；root确认材料/接线。状态仅awaiting_review，不在此切片扩展其它模块。
