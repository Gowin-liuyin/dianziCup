"""从实际JUnit/命令回执生成准备切片报告并冻结本轮文件哈希，不声明live能力。"""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as xml
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN_DIRECTORY = Path(__file__).resolve().parent
WORKSPACE = RUN_DIRECTORY.parents[2]
REPORT_PATH = WORKSPACE / "reports/tasks/R09-knowledge-cards-preparation.md"
ORIGINAL_BASE = "349c5e3ec27196257b98cdfcb63c75fb50157978"
CONTRACT_BASE = "c5d9080d6a0494a01b1fe26086220365deca7583"
CODE_SHA = "02bea007dec5046458c7f2f1c969f0080ef03889"
CODE_PATHS = (
    "backend/src/ai_intel/enrichment/knowledge_cards.py",
    "backend/src/ai_intel/enrichment/card_extraction.py",
    "backend/tests/r09_card_fixtures.py",
    "backend/tests/unit/test_r09_knowledge_cards.py",
    "backend/tests/contract/test_r09_knowledge_card_contract.py",
    "backend/tests/security/test_r09_card_boundaries.py",
    "backend/tests/contract/test_t22_research_and_document_links.py",
)


def save_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_summary(name: str) -> dict[str, int]:
    suite = xml.parse(RUN_DIRECTORY / f"{name}.xml").getroot().find("testsuite")
    if suite is None:
        raise RuntimeError("JUnit suite missing")
    return {
        attribute: int(suite.attrib[attribute])
        for attribute in ("tests", "failures", "errors", "skipped")
    }


def main() -> None:
    recorded_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
    for path in CODE_PATHS:
        saved = subprocess.check_output(["git", "show", f"{CODE_SHA}:{path}"], cwd=WORKSPACE)
        assert (WORKSPACE / path).read_bytes().replace(b"\r\n", b"\n") == saved.replace(
            b"\r\n", b"\n"
        ), f"code freeze changed: {path}"
    code_receipt = {
        "recorded_at": recorded_at,
        "status": "awaiting_review",
        "scope": "R09 public knowledge card preparation only",
        "original_base": ORIGINAL_BASE,
        "contract_base": CONTRACT_BASE,
        "root_contract_commit": "f62466ff3282c872336288fc42e600e4e2dcc84a",
        "code_sha": CODE_SHA,
        "files": [
            {
                "path": path,
                "worktree_sha256": sha256(WORKSPACE / path),
                "git_blob_sha256": hashlib.sha256(
                    subprocess.check_output(["git", "show", f"{CODE_SHA}:{path}"], cwd=WORKSPACE)
                ).hexdigest(),
            }
            for path in CODE_PATHS
        ],
        "diff_sha256": sha256(RUN_DIRECTORY / "code_diff.log"),
        "layers": {
            "unit": "passed",
            "contract": "passed",
            "security": "passed",
            "integration": "not_run",
            "frontend": "not_run",
            "e2e": "not_run",
            "live": "not_run",
            "manual": "not_run",
        },
        "test_results": {
            name: test_summary(name)
            for name in ("unit_final", "contract_final", "security_final", "focused_freeze")
        },
        "live_call_count": 0,
        "human_gold_count": 0,
        "actual_non_cve_case_count": 0,
        "fixture_mechanism_classes": [
            "prompt_injection",
            "training_data_poisoning",
            "model_extraction",
        ],
    }
    save_json(RUN_DIRECTORY / "code_freeze_receipt.json", code_receipt)
    command_names = (
        "label_red_utf8",
        "extraction_red",
        "unit_first",
        "focused_first",
        "style_first",
        "format_apply",
        "format_apply2",
        "unit_final",
        "contract_final",
        "security_final",
        "style_final",
        "format_final",
        "mypy_first",
        "mypy_final",
        "mypy_recheck",
        "style_freeze",
        "format_freeze",
        "focused_freeze",
        "secret_scan",
        "code_diff_check",
        "cbm_help",
        "cbm_refresh_frozen",
        "cbm_schema_frozen",
        "cbm_trace_frozen",
        "rg_callers",
        "material_compile",
        "material_style",
        "material_format_apply",
        "material_style_recheck",
        "material_style_width_recheck",
        "material_format_check",
    )
    command_rows = []
    for name in command_names:
        receipt = json.loads((RUN_DIRECTORY / f"{name}.command.json").read_text(encoding="utf-8"))
        command_rows.append(
            f"| `{name}` | {receipt['started_at']} → {receipt['finished_at']} | "
            f"{receipt['exit_code']} | [{name}.log](../runs/{RUN_DIRECTORY.name}/{name}.log) |"
        )
    report = f"""# R09 · 公开知识卡准备切片

记录时间：{recorded_at}。本切片 `awaiting_review`，实现 `complete`
限于内部候选抽取边界；整 R09 仍是未完成的工作包，不能据此验收整
R09/T09/T14/T15/T22。

## 输入输出与范围

本地分支 `codex/r09-knowledge-cards`，原始基线
`{ORIGINAL_BASE}`；主控授权引入公共合同 `{CONTRACT_BASE}`（对应 root
`{code_receipt["root_contract_commit"]}`，其中 R11
依赖/锁文件属于主控既有提交）。本实现代码冻结 `{CODE_SHA}`，7
个代码/测试文件，1089 additions / 7 deletions。原主控工作树未提交修改没有修改。

输入复用 `DocumentReadService.document_detail` 已按 ACL 筛选的公开 `DocumentDetailResponse`、现有
`AccessScope` 与 `GenerationClient`。此 DTO 的证据是保存的来源 span，不保证每个 span
覆盖整块/全文；本片没有提供读取任意
URL/SQL/shell 的产品能力，也没有接 tenant 资料外发。调用方应明确选取 <=50 个已验证
span；不得悄悄截断默认 100 项资料页。

输出 `KnowledgeCardDraft` 是待审内部值对象，不是第二套业务存储。论文固定 8
字段：机制、攻击者控制、输入路径、模型/任务、工具权限、作者环境、结论、限制；标准/政策
固定 9 个公共字段加各自推荐/义务字段。每个字段绑定 document/revision/原文
revision number；每个有值候选附 evidence/block、全局 Unicode 左闭右开坐标、原文
quote、quote SHA-256、来源 span
SHA-256 和页面/JSON 定位。span hash 不冒充完整 block/raw-document
hash；原文版本回查仍由既有 PG 完成。

所有值为 `model_hypothesis`，有引用仍为
`candidate`、`semantic_support=unverified`、`confirmation_status=a
waiting_review`、`verification_level=unknown`。缺失字段为 unknown；同字段不同值并列
conflict。摘要与 clause_text
分开，clause_text 必须原样回切引用；标准推荐字段不能放入 policy
卡，法规义务字段不能放入 standard 卡。source
日期精度、草案/正式、发布时间/生效候选独立；不进行法律裁决或资产研判。单次共享客户端、
严格嵌套 schema、无格式重试/模板回退；错误保留真实 attempt 元数据并只暴露固定错误码。

## 改动文件与复用

{chr(10).join("- `" + path + "`" for path in CODE_PATHS)}

重用 `DocumentDetailResponse`/`EvidenceResponse`/`AccessScope`、HTML
parser、`TextBlock`、`locate_evidence_span`、`GenerationClient.generate`、`AttemptMetadata`、受控
gateway 与既有 T22 六例。不修改 research_links、公共
DTO/domain/schema、PG/migrations、设置、worker、API、frontend 或 progress；不自建
repository、缓存、规则结果或模型接口。唯一新业务模块 `card_extraction.py`；fixture
helper 为三层直接测试共享合成输入。

## 语义修复与历史失败

按 [主控 CR-R09](../../docs/decisions/CR-R09_verification_labels.md)，`verification_label(False,Fa
lse)` 改为 unknown，其余布尔语义和 PaperCard/PolicyCard 构造保持。旧 T22-C01…C06
没有减少，仅 C06 错误期待纠正；其业务 red
`label_red_utf8` 为 1 failed / 5 deselected，原错误返回 rule_inferred_for_asset
清晰留存。这不是金标、阈值或计分分母调整。

`extraction_red` 是模块尚未实现的 collection
error，不是环境缺失，也不计业务测试数量。首次 `unit_first` 为 38 passed / 1
failed，测试把既有网关 401 错误码误写为 model_authorization_failed；依据现行
`classify_http_failure` 改正为
model_permanent_auth_error，未改错误实现。`style_first` 8
个长行后格式修正；`mypy_final` 2 个定长元组赋值错误后加
`tuple[str,...]` 显式类型，`mypy_recheck` 0 issues。原日志全部保留。最早 `label_red`
的日志工具打印遇 GBK
UnicodeEncodeError；child exit=1 已写回执，后续显式 UTF-8 重跑 `label_red_utf8`，没有覆盖该原记录。

## 真实检查结果

| 验证层 | 结果 | 实际范围 |
|---|---|---|
| unit | passed | 268 tests, 0 fail/error/skip; R09 38 + shared regressions |
| contract | passed | 76 tests, 0 fail/error/skip; R09 10 + original contract regressions |
| security | passed | 36 tests, 0 fail/error/skip; R09 12 + shared boundaries |
| integration | not_run | 本片没有 PG/worker 接线，未启动隔离服务 |
| frontend | not_run | 未改前端 |
| e2e | not_run | 没有 R09 产品完整链 |
| live | not_run | 0 外部请求、0 真实模型调用、0 真实机制案例 |
| manual | not_run | 0 人工金标/复现/条款适用性裁决 |

三层相关回归共 380 项；最终代码版本 focused 再检 66 passed（60 个新增 fixture tests +
旧 T22 六例），0
fail/error/skip。`--no-cov`
仅用于限定范围回归，没有产生覆盖率或正式性能/准确率声明，配置与阈值未修改。Ruff/format
（7 文件）、mypy（2
source 文件）、git diff --check 均 exit 0。既有 repo secret scanner exit 0，既有 findings
全保留且分类表未改；没有注入凭据，exact_scan=not_run。所有 pytest 和工具运行复用现有
D:/dianzi/backend/.venv/Scripts/python.exe，PYTHONPATH 指向本独立 WT
src/tests，未安装/下载模型或新依赖。

完整命令、cwd、+08 开始/结束和 child 退出码位于各 `.command.json`，JUnit 为同名
`.xml`。原命令参数在回执中逐项保存，没有凭据或原文秘密。

材料脚本检查也保留真实失败：首次 material_style 为 17 个长行，
按 code point 包行后 material_style_recheck 仍有 33 个显示宽度超限；
根因为 Ruff 按中文显示宽度计数，修正材料文字包行后
material_style_width_recheck 与 material_format_check 均 exit 0。
没有修改业务代码或放宽规则，代码冻结断言和材料哈希自检真实执行通过。

| 检查 | 实际 +08 时钟 | child exit | 日志 |
|---|---|---|---|
{chr(10).join(command_rows)}

## CBM、调用方与精确冻结

开工先以真实 portable help/schema 索引现有 src：基线 1292 nodes / 6424 edges。`verification_label`
没有生产调用，rg 补查仅旧 T22；`GenerationClient.generate` 既有调用为 grounding →
question service。本轮冻结后再次
fast 索引/trace，参数和原始输出已保存。CBM 默认配置排除
assets/缓存目录，不能声称是全仓无遗漏图；本片调用方使用 rg 全 src/tests
核对。新的抽取入口没有生产调用者，只有直接测试。

精确 diff：[code_diff.log](../runs/{RUN_DIRECTORY.name}/code_diff.log)；代码文件
worktree 与 Git blob
SHA-256：[code_freeze_receipt.json](../runs/{RUN_DIRECTORY.name}/code_freeze_receipt.json)。整个材料
清单为同目录 `artifact_manifest.json`，其本体 SHA-256 在
`artifact_manifest.sha256`；清单不包含自身与
sidecar，防止循环 hash。材料提交 SHA 在交接中另列。

## 评分证据、偏差与后续

F2：具备带固定原文位置的论文前提候选和标准/政策字段边界；F3/R1：原文/摘要、日期、历史
revision 与缺失/冲突保留、输入注入隔离。这些只证明 fixture
合同实现，不证明三类真实非 CVE 案例或完整问答质量/来源接通。R09
六验收中的原文定位/历史/推荐义务分离/未知边界已有 fixture
证据；真实三类资料、文献语义关系、正确时点问答仍未验收。research_links 原强关联语义与
T22 原案例继续保留，新的关系确认由主控后续切片审查，不以任意非空引文升级。

与授权计划一致：R07 产品发布前置尚待主控接线，本片是安全独立准备，不把 R07 或整 R09
live 改为通过。下一步由全新非作者 reviewer 核对
`{CODE_SHA}`/主控 CR 实际落实、复跑三层测试；随后主控接 PG
候选/审核账本、文献关系与检索/API/界面、官方原文三机制目录和真实模型预算门。模型候选必
须经过单独语义支持/审核才可发布，仍不可自动成为团队复现或当前资产规则。

未检查 integration/frontend/e2e/live/manual；核心风险是本入口尚无生产接线，现有公开投
影不能用于 tenant 内容外发或完整原文缺失结论。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    artifact_paths = sorted(
        [*CODE_PATHS, REPORT_PATH.relative_to(WORKSPACE).as_posix()]
        + [
            path.relative_to(WORKSPACE).as_posix()
            for path in RUN_DIRECTORY.iterdir()
            if path.is_file()
            and path.name not in {"artifact_manifest.json", "artifact_manifest.sha256"}
        ]
    )
    manifest = {
        "schema_version": 1,
        "sealed_at": recorded_at,
        "code_sha": CODE_SHA,
        "scope": "R09 preparation; no full-card acceptance or live verification",
        "files": [{"path": path, "sha256": sha256(WORKSPACE / path)} for path in artifact_paths],
    }
    manifest_path = RUN_DIRECTORY / "artifact_manifest.json"
    save_json(manifest_path, manifest)
    manifest_sha = sha256(manifest_path)
    (RUN_DIRECTORY / "artifact_manifest.sha256").write_text(manifest_sha + "\n", encoding="ascii")
    assert all(sha256(WORKSPACE / item["path"]) == item["sha256"] for item in manifest["files"])
    print(json.dumps({"artifact_count": len(artifact_paths), "manifest_sha256": manifest_sha}))


if __name__ == "__main__":
    main()
