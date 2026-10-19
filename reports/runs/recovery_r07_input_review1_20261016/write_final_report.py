"""Write the final limited verdict only after every required independent receipt passes."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/reviews/recovery/G-C-R07-input-capabilities-review-1.md"
modes = (
    ("unit", "final_5b3869_unit"),
    ("contract", "final_5b3869_contract"),
    ("security", "final_5b3869_security"),
    ("原模型回归", "final_5b3869_regression"),
    ("字段相关回归", "final_5b3869_fieldset"),
    ("Graph unit/contract/security", "final_5b3869_graph"),
    ("独立离线探针", "final_5b3869_probe"),
    ("窄 loader/真实 PG", "final_5b3869_integration"),
    ("独立 PG 探针", "final_5b3869_probe_pg"),
)
receipts = []
rows = []
for label, stem in modes:
    receipt = json.loads((RUN / (stem + ".command.json")).read_text(encoding="utf-8"))
    assert receipt["exit_code"] == 0 and receipt["failed"] == receipt["errors"] == receipt["skipped"] == 0
    receipts.append(receipt)
    rows.append(f"| {label} | 0 / {receipt['tests']} passed / 0 skip | {stem} |")
verified = json.loads((RUN / "author_fix3_material_verification.json").read_text(encoding="utf-8"))
assert verified["all_author_raw_and_fixed_git_lf_verified"]
for stem in ("final_5b3869_static_ruff", "final_5b3869_static_format", "final_5b3869_static_mypy", "final_5b3869_source_diff_check"):
    assert json.loads((RUN / (stem + ".command.json")).read_text())["exit_code"] == 0
recorded_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
graph_union = json.loads((RUN / "owned_graph_case_union.json").read_text())
assert graph_union["exact_missing_testcase_ids_replayed"] and graph_union["final_unique_passed"] == 112
assert graph_union["final_failed"] == graph_union["final_errors"] == graph_union["final_skipped"] == 0
latest_total = sum(receipt["tests"] for receipt in receipts)
assert latest_total == 394
reuse = json.loads((RUN / "fix3_shared_regression_reuse.json").read_text())
assert reuse["all_other_backend_src_git_bytes_unchanged"] and not reuse["new_execution"]
publication = json.loads((RUN / "owned_7aeb85_publication_pg_copies.command.json").read_text())
assert publication["exit_code"] == 0 and publication["tests"] == 34 and publication["failed"] == publication["errors"] == publication["skipped"] == 0
total = latest_total + graph_union["final_unique_passed"] + publication["tests"]
rows.append("| 7a Graph 原断言/自有 PG 副本，hash 不变复用 | 原命令 79 passed/33 setup errors；补 fixture 后原 33 全 pass，精确 ID 并集 112 | owned_7aeb85_graph_pg_copies / owned_7aeb85_graph_pg_copies_retry / owned_graph_case_union.json |")
rows.append("| 7a publication/ACL/rule 原断言/自有 PG 副本，hash 不变复用 | 0 / 34 passed / 0 skip | owned_7aeb85_publication_pg_copies |")
text = f"""# G-C · R07 分类目录与有界证据输入独立初审

What this change does: 本切片为模型字段抽取增加确定的词法预选、原文范围和全部来源版本依赖，并提供固定官方 CWE/legacy ATLAS 目录解析与 PostgreSQL 窄加载器。目录成员性不构成事件映射确认，候选继续保留为 model_hypothesis/pending。

**Verdict: Ship，仅限本次输入切片及已批准的共享必要上下文校验 seam。** 四项初审 Must 已在冻结新版本独立闭合，当前没有该范围内遗留阻断。整 R07、整 T19/T20、九维/default App/G-C 不因此通过；任务状态由主控登记，本审查未写 accepted 或 progress。

记录时点：{recorded_at}，Asia/Shanghai。非作者 reviewer：`/root/r07_taxonomy_selection_first_independent_review`；工作树 `D:/wt/r07-input-review1`，分支 `codex/r07-input-review1`。最终 source `5b3869e4dcdfa16c0ae393cd73acae4cf27efbf9`，material `6705303ab8eaa19d57194f1982819d25b1415d04`。原 `7dae1d82363d8459f3546fee4b92137559dcb5aa` / `eb6daced5f2467dc56ade15857e60a1af9486db0`、中间 `9c4991a218e3d7208d8c314a3992cd6c499e0b4b` 和 `7aeb85ae8277c048fb762dbc705436602cb18f9d` / `4c339e6f56b302a7081ea230382b8b69ad42c10c` 及其全部红例保留。

依据：已读 AGENTS、00 执行图、03/04/06 合同、恢复 CR-R07、T19/T20 精确卡、输入 CR、任务报告和 root 追加的 CR-R07_context_validation_seam；使用 ponytail-review 5.2.0。保留 `ff5aa737` 共享极性规则和 `475dea5c`（root `48b56033` 的本 WT cherry-pick）依赖。root seam 原 raw SHA256 `1e663e40ceca3c6b4cdf266669b36055f6835ebce0d1c2afd39c18ca4fe79d31`，与本 WT LF 逐字相同；只允许三个 validator 末置必要 context 检查和 default-empty typed gaps，未改 URI 信任、支持正则、阈值、预算或 DTO。

## 初审 Must 与独立闭合证据

1. **畸形官方 URL 泄漏原生异常，已闭合。** 原 `taxonomy_inputs.py:80/85` 对坏 port 和未闭合 IPv6 抛 ValueError，真实 PG 保存 revision 也重现。新版本在 URL/port 边界归一 `taxonomy_source_uri_invalid`；原 URI 输入不变，`final_5b3869_probe` 两例及 `final_5b3869_probe_pg` 保存 URI 例通过。旧 `corrected_7dae_probe` / `second_7dae_probe_pg` 红例仍在。

2. **YAML 等价重复键被合并，已闭合。** 原 `metadata: true/True` 两键被 SafeLoader 合并但目录接受。新版本按成熟 SafeLoader 实际构造键判等，原输入仍产生 `taxonomy_yaml_duplicate_key`；非 scalar、非有限 key、custom tag 和 alias 继续拒绝。原独立红和新版成员正控制同时保留。

3. **遗漏条件掩盖虚构 fixed=99.0，已闭合。** 9c4991 在真实 `>=1.0,<2.0` 与省略 `Only when tools enabled.` 的交叉场景错误返回 BLOCKED。批准的共享修复先校验所有 quote/hash/身份/value/boundary/target/limitations，再计算服务端 FieldContextGap；owned 模型层删除复制的 qualifier 正则，只在全部合法 gap 都与 omitted ranges 相交时 BLOCKED。原 false-boundary 输入现在 FAILED；合法未送 span/条件 BLOCKED，假 quote、已见缺条件、混合坏候选、同时已见和未见必要条件均 FAILED，空回答仍 PENDING。独立 27 例还核验 gap 的 UUID/原始 Unicode 坐标、不可变性、默认空 tuple，以及模型自报 context_gaps 的格式拒绝。

4. **SafeLoader 内置标量异常未归一，已闭合。** 原 `!!int nope`、`!!float nope`、`!!bool nope`、`2026-99-99` 泄漏 ValueError/KeyError；7a 的新增 `metadata: !!timestamp nope` 仍泄漏 AttributeError，原 27 例真实 26 pass/1 fail。Fix3 已批准 CR 仅在 ScalarNode 的成熟 SafeLoader.construct_object 入口归一 ValueError/KeyError/AttributeError/IndexError/OverflowError 为 `taxonomy_yaml_invalid`，所有原输入不变重新通过。75 unit 还包含 13 种坏 scalar × key/value、12 种正常 scalar、binary 仍拒绝、业务投影 AttributeError 仍传播的边界控制。既有具体错误码保留，不逐值特判、不广捕业务异常。

新类型和真实调用者已核对：`model_fields._generate_field` 与 `EvidenceGraphReadService._validated_support` 两个直接调用者；图仍在字段校验失败时拒绝有效关系。公开运行时结果为 frozen `ModelFieldResult.input_selections: tuple[FieldEvidenceSelection, ...]`，选择范围、quote 和必要 context gap 均使用原始 Unicode codepoint 坐标，hash 和全部原始 document/revision 依赖继续保留；这不等于旧 job 已持久保存该输入审计。没有 publication 直接重校字段候选的路径，因此不把先前“publication 重验证覆盖 limitation”的猜测记为真实缺陷。模型输出 schema 仍 `r07-model-field-extraction-1`，prompt `r07-model-fields-2`，selection `r07-field-selection-1`；未发布的修复由 root 首次接线使用最终 SHA，不重解释历史任务。

## 真实复跑

最终 source 上新执行 **{latest_total} passed，0 failed/errors/skipped**；另复用 7a 自有 DB/CAS 的共享 Graph 112 与 publication 34 项，共 **{total} 项独立正控制证据**，不将重复执行加进分母，不称 540 项全在最终 source 新跑。`fix3_shared_regression_reuse.json` 逐字核对 131 个相关源码/原测试/依赖、独立资源副本；Fix3 仅 taxonomy parser 与其 unit 测试改变，模型、field_sources、Graph、publication 及其原测试均不变，源码 import 检索结合 CBM 调用链确认这些消费者不直接调用 parser。精确命令、cwd、+08 秒级起止、exit 和 JUnit 计数在以下每组同名 `.command.json/.log/.xml`，目录 `reports/runs/recovery_r07_input_review1_20261016/`。

| 层 | exit / 结果 | 证据前缀 |
|---|---|---|
{chr(10).join(rows)}

每条 pytest 为 `D:/wt/r07-input-capabilities/backend/.venv/Scripts/python.exe -m pytest -q <表内原文件或独立副本> --no-cov --junitxml <本 run 文件>`，cwd=`D:/wt/r07-input-review1/backend`。复用已安装 Python 3.12 和冻结依赖，显式 PYTHONPATH 指向 reviewer WT；四个模块实际 __file__ 已核对，PyYAML 实为 6.0.3。原模型 143=56+41+46，原期待和原测试 Git blobs 未修改。Graph 保留既有 Starlette 弃用 warning；没有新增依赖处理它。

Ruff check/format（8 source/test 文件）、mypy（4 source）、原基线到新 source 的 backend diff-check 均 exit 0。独立通过的范围含 67 blocks 最后证据、稳定词法选择、完整原来源依赖、Unicode/emoji/CRLF 范围分区、50 条/16384 字符/65536 bytes、首 wire 前全维预选、过大输入 0 calls、真未送引用、否定/未知/条件、注入与 egress/budget 拒绝、一次 offline codec/1024 tokens/20s/fee unknown。未改原 roster、块、hash、blocks_complete 或 content_coverage。

真实 PG 检查复跑 source/document/revision ACL、READ_PUBLIC、current、CAS/hash/size、旧 revision/重放和三父行并发共享锁，阻止变更实际 SQLSTATE 55P03。最终使用本审查自有 `test_dianzi_r07_input_review1_*` 数据库。Graph/publication 原夹具强制另一固定库名，依 root 授权在本 run 复制 8 个关联原测试，只替换 4 处数据库安全守卫/临时 CAS 路径；精确 diff 和原 bytes/hash 在 `resource_copy_diff.patch` / `resource_copy_manifest.json` / `original_resource_test_blobs/`，逆转这 4 处后与原 Git bytes 完全相同，业务断言变化 0。Graph CAS 指向本 run 的 owned_r10_fixture_cas，不与共享临时 CAS 共用。原 repo 测试、guard 和数据库未改；不碰 collector DB/Redis15。

过程缺口诚实保留：首次独立 preflight 取错 event fixture；首次 size mutation 未复位污染下一同 hash 用例，均修 reviewer 仪器后新库复跑，不计产品缺陷。9c、7a 及原 parser 的实际业务红完整保留。Graph 112/publication 34 首次在新库均 setup error（固定库守卫），没有业务测试执行；后来原固定库/random schema 复跑 112/34 通过，但开始前未捕获其他 writer 快照，不能补写已核验。最终以自有数据库、独立 CAS 副本复跑作为隔离证明。制作副本的第一次逆转证明因两个目标守卫文本相同而失败，未运行用例；失败脚本快照保留，改为可唯一逆转文本后证明成功。自有 Graph 副本首次还有 33 项因 reviewer conftest 漏导出原秘密失败保护 fixture 而 setup error，补原 fixture 引用后仅重跑精确这 33 项全 pass；原 79 项和该 33 项 ID 不重叠且并集等于原 112 项，71 deselected 不是通过或 skip。没有删除难题、修改金标/阈值、改失败为 skip。自有脚本首次失败的起止未写盘，不补造。

## 原字节、目录与冻结材料

最终 Fix3 raw manifest SHA256 **`7670982f460bb9a1fba97dd708ca283b5f1e8321e9e9edde0944d43f072a150f`** 已独立核对，逐项 11 source/74 新 materials 的作者 raw、reviewer LF、固定 Git blobs/LF 及 4 个已批准仓外公开 CAS 全部匹配；旧 Fix2 的 191 raw 材料在当前窗口逐一仍相同。详见 `author_fix3_material_verification.json` / `author_fix3_raw_manifest.json`。Fix3 CR 按 root 指派授权核验 author/reviewer/固定 Git 字节，主 D:/dianzi 无该 CR 副本；reviewer 首次 verifier 额外假设主目录副本存在而 exit 1，完整 traceback 和失败观察另存，删除这项不存在的前提后真实 exit 0，并未补造初次起止或报业务失败。共享 seam 主目录 CR 仍逐字一致。前窗 Fix2 raw manifest `71d23f1aa47f6e6bdea503d23bbfcd479c000efdb2e6ca494237152d432ce2f9` 已在 7a/4c 窗口独立核对 10 source/191 materials/4 CAS，保留其报告，不要求旧 source raw 与新 parser 相同。原 raw manifest `8138f507572bedf48d57b6c7e81b398e206feb5f0067847e0f727d7a2e52fb84`、8 source/86 materials 的固定 Git LF 与 4 CAS 也已核对并保留；原核验时作者后续 owned 编辑造成 4 处当前 raw 与旧记录不同，`author_7dae_material_verification.json` 如实记录，未称当前 raw 匹配旧 source 窗口。raw 与 Git LF分别记录，未把不同字节哈希当相同。作者 4c 中 fix2_original_test_review_probe.py 实际为 26 cases，06:28 原命令 23 独立保留；Fix3 另冻结并执行 26、新 27 及原前 23 的 -k/3 deselected 控制，没有反改旧材料计数。

CWE 4.19 ZIP 1,883,899 bytes，969 IDs；raw hash `f7a7705971796ac26aed238f62594e24ff028549586b37150da32d9bbd58c554`，XML hash `952e31ada53436bbfc6dab873adeb00d08870eec88d00075b38defd1142b8ddb`。legacy ATLAS deprecated 5.6.0 固定 commit `3259f388d19cbcca11bacf12a0ef97f4198f711b`，raw hash `c9c23971d0db07e2782423d795a20e78d5c2c9bcdc78fc67e24530657daaec41`，170 唯一成员/170 原始 identifier Unicode 行坐标逐项独立通过。只读 fixed CAS，无新 GET、无下载模型或付费 API。原批准网络 6 GET 与旧组织 404 仍按其历史材料；不称最新或现代 v6。

同 commit 官方完整 schema hash `17349bf6127b69a2b366aa6c18a8a9d0034545c88186e8120269f94b51f263f1`，独立实际 exit 1、126 errors，`independent_official_schema_observation.json` 保留。窄成员性通过不等于 full schema 通过。原 595 NVD 四子 job budget/0 wire 红例不变。原材料7dae→eb diff-check 独立重现 actual git exit 2，原始日志/XML尾空白与 CBM EOF 不剪；外层 PowerShell tool 显示 exit 1，helper 记录真实 git 2，不计通过。最终作者 raw 材料 diff-check 仍 2，不冒称通过。reviewer 自有 run 的 `.gitattributes` 仅对 `.log/.xml` 使用定向 blank-at-eol/blank-at-eof 白名单；这两类和作者 raw manifest、review manifest/指纹/回执、历史 source blobs、原测试资源 blobs/副本、自有合成 CAS 使用 -text 保留 bytes，尤其避免 Windows checkout 改 CAS hash。未全局禁检查或改作者 attrs。reviewer 自有指纹/回执首次切 -text 后暴露 Windows CRLF 的 cached diff-check actual 1，编排没有据该退出码阻断本地材料 commit；随后 post-commit diff-check 真实 2，完整 raw 输出在 review_raw_metadata_crlf_diff_check.log/json 保留。修的是自有 seal 输出明确 UTF-8 LF bytes，不剪旧输出、不更改作者材料；最终再查 staged 和最终材料 diff。最终 reviewer report/raw list/hash/source blobs 由 seal_review.py 逐项验证，见 review_manifest.json、review_manifest_fingerprint.json、review_seal_receipt.json；本页不写自引用哈希。

## 调用链与未通过的整系统门

CBM 实际 WSL portable CLI，独立 cache/name 与 backend/src fast index；最终 1,530 nodes/8,006 edges，排除 assets 与 __pycache__，schema/双向 trace 原输出保留。首轮源码浏览早于首 index 的顺序差异明确记录；未因此编辑业务，随后重新作 index、trace 和源码核对。`--json --help` 实为 unknown tool/exit 1，不能记帮助成功。最终 validator trace 两个 hop-1 caller 与源码 rg 相同；缺边不单独证明无路径。

固定外部 `595e42a91a830f78fd11d0e4fc7a79a1aaf767cb` 四个 job source blob/hash 与当前 reviewer caller 核对在 caller_audit JSON：policy 尚无 prompt/selection version，job 仅保存 generated.model_attempts 并 return generated.attempts[0]，step 不存 input_selections。默认 EnrichmentContext 未提供 valid_cwe_ids/valid_atlas_ids 有效集合，taxonomy loader 无业务 caller，新组织 URI 仍被旧 field_sources 信任边界拒绝。正式 collector/roster/context 容量、策略 fingerprint、全原依赖和覆盖摘要持久审计仍需另一个有界接线切片；publication 的 current/ACL 提交复查与候选限制审计应在该接线中实际验证。没有推断已发生限制丢失，不修改 job_service。

这些缺口阻止整 R07/T19/T20/九维/default App/G-C 验收；pending/hypothesis 不豁免它们。F2/P2 证据仅为有界真实输入、可追溯假设、目录成员性基础，E1 仅为已实测输入/权限/CAS/锁边界；没有准确率、召回率、性能、持续时长或盲测分数。frontend/e2e/live 模型、现代 v6、默认 App/collector、manual 产品及全九维仍 not_run/blocked_live；full schema failed，费用 unknown。未 push、未 spawn、未编辑 progress/accepted/公共 schema/limits/依赖/gold；自有数据库释放收据在 owned_pg_release.json，共享库和服务不删除。

下一任务建议：root 按本限定意见登记并保存最终 source/material，再独立接策略指纹和 durable input selections/全原依赖，随后处理固定目录来源注册和正式 context/URI 支持。不得将本页替代该接线或 live 验收。

Verdict: Ship, within the stated slice only. Not checked: 真实模型、现代 ATLAS v6、正式持久接线/default App/自动采集、整九维和人工产品验收。
"""
assert "952e31ada53436bbfc6dab873adeb00d08870eec88d00075b38defd1142b8ddb" in text
REPORT.write_text(text, encoding="utf-8")
(RUN / "final_verification_summary.json").write_text(json.dumps({"recorded_at": recorded_at, "source_sha": "5b3869e4dcdfa16c0ae393cd73acae4cf27efbf9", "material_sha": "6705303ab8eaa19d57194f1982819d25b1415d04", "verdict": "Ship scoped", "passed_evidence_cases": total, "newly_executed_on_final_source": latest_total, "reused_unchanged_shared_regressions": 146, "failed": 0, "errors": 0, "skipped": 0, "receipts": receipts, "reuse_receipt": "fix3_shared_regression_reuse.json", "live_model": "not_run", "default_app": "not_integrated", "official_full_schema": "failed"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"verdict": "Ship scoped", "passed": total, "report": str(REPORT), "recorded_at": recorded_at}))
