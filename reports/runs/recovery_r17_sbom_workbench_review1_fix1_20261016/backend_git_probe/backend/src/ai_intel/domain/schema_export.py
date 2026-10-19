"""JSON Schema 导出: 从领域模型生成稳定合同文件供前端类型来源使用。

职责: 生成结果确定性可复现(排序键、固定版本字段), 重复执行不产生无关漂移。
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_intel.domain.records import (
    SCHEMA_VERSION,
    AssessmentRecord,
    ClaimRecord,
    DocumentRecord,
    EvidenceRecord,
    SourceRecord,
)

SCHEMA_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "contracts" / "schemas"


def build_schema_bundle() -> dict[str, object]:
    """返回包含版本号与各记录 JSON Schema 的确定性合同包。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": "ai_intel.domain.schema_export",
        "schemas": {
            "SourceRecord": SourceRecord.model_json_schema(),
            "DocumentRecord": DocumentRecord.model_json_schema(),
            "EvidenceRecord": EvidenceRecord.model_json_schema(),
            "ClaimRecord": ClaimRecord.model_json_schema(),
            "AssessmentRecord": AssessmentRecord.model_json_schema(),
        },
    }


def render_schema_bundle() -> str:
    """把合同包序列化为稳定文本: 排序键 + 固定缩进, 重复执行字节一致。"""
    return json.dumps(build_schema_bundle(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_schema_bundle(output_dir: Path | None = None) -> Path:
    """写出 schema_bundle.json 到 contracts/schemas 并返回路径。"""
    target_dir = output_dir if output_dir is not None else SCHEMA_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "schema_bundle.json"
    target_path.write_text(render_schema_bundle(), encoding="utf-8")
    return target_path
