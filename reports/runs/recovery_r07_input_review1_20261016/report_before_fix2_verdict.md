# G-C · R07 分类目录与有界证据输入独立初审

What this change does: 本切片为模型字段抽取增加确定的词法预选、原文范围与全输入版本依赖，并提供固定官方 CWE/legacy ATLAS 目录解析和 PostgreSQL 窄加载器。目录成员性与候选引用校验不构成事件映射确认；候选继续保留为 model_hypothesis/pending。

记录时点：2026-10-16T06:22:09+08:00，Asia/Shanghai。审查人：`/root/r07_taxonomy_selection_first_independent_review`，非作者。工作树：`D:/wt/r07-input-review1`，分支 `codex/r07-input-review1`。本页是截至状态修正 `9c4991a218e3d7208d8c314a3992cd6c499e0b4b` 的初审发现；已告知主控，等待后续修复冻结后复验。状态 `needs_changes`，尚不签最终切片。

审查基线：原代码 `7dae1d82363d8459f3546fee4b92137559dcb5aa`，原材料 `eb6daced5f2467dc56ade15857e60a1af9486db0`。依赖保留 `ff5aa737` 共享极性规则与 `475dea5c`（主控 `48b56033` 的本分支 cherry-pick）；未更改其合同。依据已读取 AGENTS、执行图、03/04/06 合同、恢复 CR-R07、T19/T20 精确卡、输入切片 CR 和任务报告，采用 ponytail-review 5.2.0。主仓现有修改未触碰；只写本页及 `reports/runs/recovery_r07_input_review1_20261016/` 自有探针和证据，未改业务、原测试、schema、limits、依赖、金标、进度或 accepted；未 push、未调用真实模型或付费接口、未派生子审查者。

## Must fix

1. **畸形官方 URL 没有转为安全错误码**（`taxonomy_inputs.py:80`、`:85`）。目录校验会解析 canonical_uri；`https://cwe.mitre.org:bad/data/xml/cwec_v4.19.xml` 和未闭合 IPv6 直接抛原生 ValueError，未返回 TaxonomyInputError/taxonomy_source_uri_invalid。前者已在真实隔离 PG 的保存 revision 路径重现。最小修复是在 URL 解析及端口取值边界捕获其 ValueError，并转为该安全码；否则未来调用方不能按已声明的分类错误处理无效来源。证据：`corrected_7dae_probe.xml` 两项红、`second_7dae_probe_pg.xml` 一项红。

2. **YAML 按字符比较键，漏掉实际重复键**（`taxonomy_inputs.py:192`）。ATLAS 合法夹具附加 `metadata: {true: first, True: second}` 的等价缩进写法后，SafeLoader 将两者合为同一 bool 键，目录却被接受。明确合同要求拒绝重复键；最小修复是限定目录 mapping 键为字符串，或按 SafeLoader 的实际键值查重复，并补语义重复测试。否则不受支持的键可被无声覆盖。证据：`corrected_7dae_probe.xml::test_semantic_yaml_duplicate_keys_are_rejected`。

3. **遗漏必要条件会掩盖另一处虚构字段**（`model_fields.py:139` 的 `_omitted_required_context`，`9c4991`）。原文合法版本行为 `PyPI widget affected versions: >=1.0,<2.0;`，随后 `Only when tools enabled.` 被预选遗漏，模型却同时给出 `fixed=99.0`。原 validator 先在缺条件处短路；新 helper 只证明有遗漏 qualifier，结果变成 BLOCKED，未排除其它错误值。最小修复是在升为 BLOCKED 前完成剩余字段的原文支持检查；无法证明只有选择缺口时保留 FAILED。否则坏模型输出被误归为输入缺失。证据：`status_9c4991_probe.xml::test_omitted_required_context_does_not_hide_other_invalid_fields[false_boundary]`；同组合法遗漏、假 quote、无缺条件的假边界及混合候选对照均通过。

4. **SafeLoader 内置标量的格式异常未转为类型化错误**（`taxonomy_inputs.py:293`）。合法 ATLAS 夹具附加 `metadata: !!int nope`、`!!float nope`、`!!bool nope` 或 `2026-99-99`，解析器分别泄漏内置 constructor 的 ValueError/KeyError，而不是 TaxonomyInputError。最小修复是在成熟库的标量构造边界归一这些预期格式异常，先保留本模块已产生的具体 TaxonomyInputError；否则未来窄 loader 对无效数据无法沿安全失败路径返回。2026-10-16T06:26:09+08:00 独立补测 `scalar_9c4991_probe.xml` 为 15 passed/8 failed，新增四个业务红例；原固定目录正控制仍通过。

## 已核验的范围与运行

独立原版本复跑：unit 18、contract 6、security 7、real PG integration 12、原模型 143、字段相关 102，均 exit 0、0 failed/errors/skipped，共 288 passed。实际命令均为 `D:/wt/r07-input-capabilities/backend/.venv/Scripts/python.exe -m pytest -q <原测试文件> --no-cov --junitxml <本审查运行目录>`；cwd=`D:/wt/r07-input-review1/backend`，精确参数、Asia/Shanghai 秒级起止与结果在各同名 `*.command.json`/`*.log`/`*.xml`。复用作者已安装的 Python 3.12 与冻结依赖，显式 PYTHONPATH 指向独立 WT；三个模块的实际 __file__ 均在审查 WT，PyYAML 实为 6.0.3。未安装新模型或追加下载。

9c4991 新合同 11 与原模型 143 定向复跑通过。独立离线探针初次 9 passed/4 failed，其中预选探针取错 fixture 是审查工具问题；修为 taxonomy 文档后 10 passed/3 业务失败。9c4991 增加真假与混合候选探针后 15 passed/4 业务失败。独立 PG 初次 6 passed/1 failed 因 size 修改污染共享同 hash 夹具，是审查工具问题；增加 finally 复位并创建新独立库后 6 passed/1 业务失败，真实重现 Must 1。两次工具错误和全部初次日志保留，未改 skip 或减去难例。

独立通过的边界包括：67 blocks 最后一条证据、稳定选择与原来源版本依赖、未选择来源仍在依赖里、Unicode code point/CRLF/emoji 原始范围完整分区、完整记录的字符与字节预算、原 blocks_complete/content_coverage/hash 不变、冻结 dataclass、真实未送 quote 拒绝、全维预选在首 wire 前失败且 0 calls、费用 unknown/一次有界 offline codec、原文否定与未知不产生正向候选、注入和 egress/budget 拒绝。PG 仅读已有 current revision；source/document/revision ACL 和 READ_PUBLIC、CAS/hash/size、旧版本与重放已复跑，三父行并发修改均实际 SQLSTATE 55P03。所有 PG 数据库为本审查新建 `test_dianzi_r07_input_review1_*`，未访问生产数据库。

Ruff check、format check、三 source mypy、原 source diff-check 均 exit 0；不以 pytest 总数代替正式性能、准确率或评分。

## 原材料与目录事实

原 raw manifest SHA256 `8138f507572bedf48d57b6c7e81b398e206feb5f0067847e0f727d7a2e52fb84` 已从作者原字节独立核对并留存。本审查逐项验证原 8 个 code Git blobs、86 个材料的固定 Git LF 与审查 WT LF、4 个仓外公开 CAS 的长度/hash，详见 `author_7dae_material_verification.json`。作者后续 4 处 owned 文件 raw 已变化，记录为后续变化，未冒称匹配原 raw；固定 Git blobs 仍匹配。raw 与 Git LF 分别核对。

直接只读已批准 fixed CAS，独立得 CWE 4.19 ZIP 1,883,899 bytes、969 IDs，ZIP hash `f7a7705971796ac26aed238f62594e24ff028549586b37150da32d9bbd58c554`，解压 XML hash `952e31ada53436bbfc6dab873adeb00d08870eec88d00075b38defd1142b8ddb`。legacy ATLAS `5.6.0` 固定 commit `3259f388d19cbcca11bacf12a0ef97f4198f711b`，raw hash `c9c23971d0db07e2782423d795a20e78d5c2c9bcdc78fc67e24530657daaec41`，170 唯一成员与 170 原始 identifier 坐标逐项通过。未作新的 GET，不称 latest 或现代 v6 支持。固定同 commit 官方完整 schema 独立探针实际 exit 1/126 errors，`independent_official_schema_observation.json` 留存；不能称 full schema 通过。原旧组织 404、595 首次 NVD input budget 红例、作者 material diff-check exit 2 与后续串联提交问题均保留，不将最后 PowerShell exit 0 当前序检查通过。

## 调用链及合并门

CBM 使用实际 WSL portable CLI、独立 cache/name、`backend/src` fast index；schema、architecture、双向 trace 均有真实日志，初始 1,527 nodes/7,989 edges，assets 排除 1 项。CLI `--json --help` 实为 unknown tool/exit 1，是工具接口观察；有效 index/查询可运行。首次源码浏览早于 index，顺序差异明确保留；未在此之前改业务，完成 index 后重新作调用链与源码核对。图没有 caller 不单独证明没有路径：源码 rg 及固定外部 `595e42a9` 四份 job source blobs 的行号/hash另在 `caller_audit.json`。

本独立 WT 中 selector 已由 model_fields 调用，但 taxonomy loader 尚无业务 caller。固定595 policy 未含 PROMPT_VERSION/SELECTION_VERSION；job_service 仅存 generated.model_attempts、返回 generated.attempts[0]，step 仅编码 DimensionAttempt，未持久保存 input_selections。默认 EnrichmentContext 无 valid_cwe_ids/valid_atlas_ids，新组织 ATLAS URI仍不被旧 field_sources 信任边界接受。正式 collector/roster/context容量、策略幂等指纹、全原依赖与覆盖摘要持久审计、publication 的限制保留与原文/current/ACL复核必须在另一个有界接线切片处理。此类未完成工作阻止整 R07/T19/T20/九维/default App/G-C 验收；pending/hypothesis 不会豁免上层缺口。本次不修改 job_service 或 field_sources，也不签这些路径。

评分证据仅支持 F2/P2 的有界证据输入和成员性基础、E1 的输入校验与 PG/CAS/锁边界；没有正式准确率、召回率、性能或持续运行结果。frontend/e2e/live 模型/默认 App/collector/manual 产品与整九维均 not_run/blocked_live，外部费用 unknown。下一步先修 Must 1–3 并复跑同独立负例，取得新 frozen source/material 后只签本切片；随后主控处理上述接线门。

Verdict: fix 1, 2, 3 and 4 first. Not checked: 真实模型、现代 ATLAS v6、自动采集、正式持久接线与整九维。
