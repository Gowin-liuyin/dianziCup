"""Seal the two-line MCP security fix and its unchanged independent inputs."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as element_tree
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
SOURCE = "c691a0d5d0e06a4cc52567e1e816cd49cb0b1e7f"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


if __name__ == "__main__":
    report = ROOT / "reports/tasks/R18-mcp-output-budget-fix1.md"
    manifest_path = RUN / "artifact_manifest.json"
    assert not report.exists() and not manifest_path.exists()
    current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
    assert current.decode().strip() == SOURCE
    suite = element_tree.parse(RUN / "full_original_and_independent.xml").getroot()[0]
    assert suite.attrib["tests"] == "296"
    assert all(suite.attrib[key] == "0" for key in ("errors", "failures", "skipped"))
    protected = []
    records = (
        (
            "r18-client-sdk",
            "recovery_r18_client_sdk_20261016",
            "artifact_manifest.json",
            "c381854c08a66ccf0f5e22644e3e852e7aa3a17cd4a1ab1eaeccf9663089e6fb",
            "artifacts",
            "raw_sha256",
            86,
        ),
        (
            "r18-sdk-client-review1",
            "recovery_r18_sdk_cli_review1_20261016",
            "artifact_manifest.json",
            "03ff1575004f98269b25397653b54930096e21d57146681d7ee8b42c31faa687",
            "artifacts",
            "raw_sha256",
            83,
        ),
        (
            "r18-sdk-client-fix1",
            "recovery_r18_sdk_client_fix1_20261016",
            "artifact_manifest.json",
            "265539c8e9978eb28c36f8e017d323e4f91707dec8819f7a9b10b5166b387558",
            "files",
            "sha256",
            110,
        ),
        (
            "r18-mcp-adapter",
            "recovery_r18_mcp_adapter_20261016",
            "artifact_manifest.json",
            "ec8a015d3c645688efe906980538ae5b155663230a39b2d4d226493d2783f05c",
            "files",
            "sha256",
            89,
        ),
        (
            "r18-mcp-output-budget",
            "recovery_r18_mcp_output_budget_20261016",
            "artifact_manifest_material.json",
            "a8d0fff9f413188b5143f11b169a566e3c392f08a2b0b7e0cb63d42301a02b93",
            "files",
            "raw_sha256",
            91,
        ),
        (
            "r18-mcp-output-budget-review1",
            "recovery_r18_mcp_output_budget_review1_20261016",
            "artifact_manifest.json",
            "e8b75e1ad8f83075a29c7f8dcf772ee5bea20102967976bbb1ded68a896ef28a",
            "files",
            "raw_sha256",
            86,
        ),
    )
    for directory, run_name, name, expected, field, hash_field, count in records:
        original_root = Path("D:/wt") / directory
        raw = (original_root / "reports/runs" / run_name / name).read_bytes()
        assert digest(raw) == expected
        entries = json.loads(raw)[field]
        assert len(entries) == count
        for entry in entries:
            assert digest((original_root / entry["path"]).read_bytes()) == entry[hash_field]
        protected.append({"manifest_sha256": expected, "count": count, "raw_unchanged": True})
    (RUN / "protected_upstream.json").write_bytes(
        json.dumps({"observed_at": now(), "protected": protected}, indent=2).encode() + b"\n"
    )
    started = now()
    body = [
        "# R18 · MCP 未预期异常边界修复 1",
        "",
        "文档首次创建/本次写作开始：" + started,
        "写作结束/更新时间/证据截止：见文末真实时点。",
        "作者：/root/r18_protocol_sdk_contract_preparation；主控：/root。",
        "状态awaiting_review；当前修复片complete，整R18仍partial；未push/accepted。",
        "WT D:/wt/r18-mcp-output-budget-fix1；分支codex/r18-mcp-output-budget-fix1。",
        "基线f246815bd678c624a11f784de5dc2b3c83981cde；已测/冻结source " + SOURCE,
        "source tree9980da61338eb7b2b9202f98aa0c1055af1f9f70；已审修复待定向复核。",
        "产品编码逐编辑时间未单独记录，不由mtime/test duration推算。",
        "",
        "## 1. 具体触发与范围",
        "",
        "R18/G-E，T04/T32/T35/T51切片，A1/E1/X1。公开DianziClient的MockTransport",
        "注入RuntimeError合成credential marker。原legacy initialize将异常文本放wire",
        "及stderr；modern discover的wire为generic错误但stderr仍泄漏marker。",
        "这是当前边界Must1，0实际秘密；不把合成故障叫实际产品凭据泄漏。",
        "原非作者报告G-E-R18-mcp-output-budget-review-1.md，SHA",
        "5b2f13314c2b595a193b20b96f50a0d186d95a3017b0898af0f3995c5fe317d4。",
        "review manifest e8b75e1...86成员逐raw核验，非作者needs_changes保留。",
        "",
        "## 2. 修复、复用与调用关系",
        "",
        "仅mcp_adapter.py共享工具callback末尾增加2行catch Exception，返回既有",
        "_tool_error固定backend_internal_error。无str/repr/trace/headers/query/key/cookie",
        "或异常日志；官方SDK收到合法isError=true结果，无须处理/打印该异常。",
        "先保留ClientInputError/ApiError/TransportError/ResponseContractError/native",
        "tokenizer分类；输入ValidationError原边界不动。不catch BaseException，不吞",
        "KeyboardInterrupt/SystemExit/CancelledError，不假成功或悄悄重试。",
        "复用现错误构造和serverInfo meta；两个实际结果均60tokens/229UTF8B，完整",
        "正式r18-output-budget-1预算通过。无新依赖/抽象/DTO或另一套业务事实。",
        "图project dianzi_r18_mcp_output_budget_fix1_20261016，仅sdk/python，首次改前",
        "index/architecture/rg0；冻结后刷新和trace0，源码交叉核实共用ask/check路径。",
        "真实链：官方ClientSession→stdio→shared callback→DianziClient DI故障",
        "→固定安全ToolResult→官方transport。PG/model/live不在该测试链。",
        "",
        "## 3. 原输入、原红与独立复核",
        "",
        "same2 final probeff45fa3f...、fixture8c448aa9...逐字复制，输入/断言未改。",
        "reviewer封存前修正原pytest.raises诊断形式以允许合法ToolResult，安全条件",
        "不放宽：wire/stderr markerFalse且固定backend_internal_error；旧仪器在review保留。",
        "本WT修改前亲跑2fail/exit1，6个wire/stderr/observation先逐bytes复制before_fix_*，",
        "之后原命名观察由同测试生成新绿，不覆盖redcopies。修改后逐字same2 2pass。",
        "cancelc7ab01e0...与independentc2902104...也逐字复制，immutable4文件SHA见",
        "same2_frozen_input_hashes.json/independent_regression_input_hashes.json。",
        "本作者未替自己签accepted；原非作者在新冻结版本定向复核，由root登记。",
        "",
        "## 4. 实际验证与时间/资源限度",
        "",
        "冻结296/296，0fail/error/skip；原280+same2两+cancel两+独立protocol12去重。",
        "10:14:15–10:14:44+08，XML26.262s；mypy7/style/format/staged check各0。",
        "实际ClientSession旧握手/现代discover、ASCII/中文/emoji、7999/8000/8001、",
        "完整meta/reference、cache/no implicit download/native边界及HTTP拒绝仍绿。",
        "实际queue cancel未调度backend；4已执行IO继续占worker，late result未返取消者。",
        "queue cancellation0.125s；slowstream question IOtimeout0.1s，实际0.312s完成。",
        "完整wall deadline和中止已发IO仍缺口，root指定后续SDK/runtime修，不在本批扩补丁。",
        "unit/contract/security本片passed；integration仅合成stdio/loopback/ASGI passed；",
        "frontend/e2e/live/manual not_run。PG0/产品模型0/测绘0/外部付费调用0，编码费用unknown。",
        "",
        "## 5. 文件、合同与回滚",
        "",
        "唯一product文件adapter；必要probe快照/newrun helper和精确run-local binary attrs。",
        "SDK core4、词表/token/byte阈值、oldv2/publicschema/HTTP未绑定策略、包装/locks/",
        "backend/progress/根attrs全部未改。原91、368、review86=545材料记录raw未改。",
        "无评分/金标/分母/阈值/失败skip变化，无新增重大决策。回滚只回退该2行，保留",
        "全部历史/raw；无DDL/drop/downgrade。没有用安全修复冒充6tools/分页/PG鉴权/live。",
        "",
        "## 6. 问题台账、评分与下一步",
        "",
        "Must1：未预期IO异常交给SDK通用异常处理，rootcause缺安全收口；2行修复，",
        "same2与完整296绿，待原非作者复核。没有新增首红业务问题；原2红完整保留。",
        "A1/E1/X1边界证据在run和probe；正式P1/P2/P3指标not_run。下一步root安排",
        "原非作者新WT审fixed source/material；整体deadline/正式PG身份/6tools/分页另批。",
        "",
        "## 7. 实际命令",
        "",
        "| 标签 | argv | cwd | 开始 / 结束(+08) | exit | 日志 |",
        "|---|---|---|---|---|---|",
    ]
    for path in sorted(RUN.glob("*.json")):
        receipt = json.loads(path.read_bytes())
        if not isinstance(receipt, dict) or "exit_code" not in receipt:
            continue
        values = [path.stem, " ".join(receipt["command"]).replace("|", "\\|"), receipt["cwd"]]
        values.extend(
            [receipt["started_at"] + " / " + receipt["finished_at"], str(receipt["exit_code"])]
        )
        values.append("../runs/" + RUN.name + "/" + receipt["log_path"])
        body.append("| " + " | ".join(values) + " |")
    report.write_bytes(("\n".join(body) + "\n").encode())
    with report.open("ab") as target:
        target.write(
            ("\n## 8. 文档修订\n\n首次完整写作结束/更新时间/证据截止：" + now() + "。\n").encode()
        )
    files = [*sorted(path for path in RUN.rglob("*") if path.is_file()), report]
    entries = []
    for path in files:
        raw = path.read_bytes()
        mode = "exact_raw" if path.suffix in {".log", ".xml", ".raw"} else "LF"
        blob = raw if mode == "exact_raw" else raw.replace(b"\r\n", b"\n")
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": len(raw),
                "raw_sha256": digest(raw),
                "git_byte_mode": mode,
                "git_blob_sha256": digest(blob),
            }
        )
    manifest = {
        "created_at": now(),
        "source_sha": SOURCE,
        "source_tree": "9980da61338eb7b2b9202f98aa0c1055af1f9f70",
        "report_sha256": digest(report.read_bytes()),
        "member_count": len(entries),
        "files": entries,
        "protected_upstream": protected,
        "status": "awaiting_review",
        "excluded": ["artifact_manifest.json", "post-seal/commit receipts"],
    }
    manifest_path.write_bytes(json.dumps(manifest, indent=2).encode() + b"\n")
    print(json.dumps({"members": len(entries), "protected_records": 545}))
