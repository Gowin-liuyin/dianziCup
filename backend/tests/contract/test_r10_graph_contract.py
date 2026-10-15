"""内部图合同与已冻结公共 Relation 的六类枚举一致，结构保持独立。"""

import json
from pathlib import Path

from ai_intel.knowledge.evidence_graph import RELATION_TYPES, GraphSnapshot


def test_internal_graph_does_not_rewrite_public_relation_shape():
    schema = json.loads(
        (Path(__file__).resolve().parents[3] / "contracts/schemas/public_api_v2.json").read_text(
            encoding="utf-8"
        )
    )
    public = schema["$defs"]["Relation"]
    assert set(public["properties"]["relation_type"]["enum"]) == set(RELATION_TYPES)
    assert "source_revision" in public["required"] and "citations" in public["required"]
    internal = GraphSnapshot.model_json_schema()
    assert internal["properties"]["nodes"]["maxItems"] == 200
    assert internal["properties"]["edges"]["maxItems"] == 400
    edge = internal["$defs"]["GraphEdge"]
    assert {"source_revision_ids", "evidence_span_ids", "supporting_claim_ids"} <= set(
        edge["required"]
    )
    assert edge["properties"]["status"]["const"] == "supported"
