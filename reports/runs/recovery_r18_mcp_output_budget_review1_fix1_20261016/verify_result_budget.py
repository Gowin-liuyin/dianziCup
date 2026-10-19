"""Count actual independently received safe errors with the pinned formal tokenizer."""

import json
from pathlib import Path

from ai_intel_client.output_budget import McpOutputBudget
from mcp_types import SERVER_INFO_META_KEY, CallToolResult

RUN = Path(__file__).resolve().parent
budget = McpOutputBudget(
    Path(
        "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/"
        "fb374d419588a4632f3f557e76b4b70aebbca790"
    )
)
rows = []
for protocol in ("handshake", "modern"):
    result = CallToolResult.model_validate_json(
        (RUN / f"unexpected_{protocol}_wire.json").read_bytes()
    )
    assert result.is_error is True
    assert json.loads(result.content[0].text) == {"error": {"code": "backend_internal_error"}}
    assert result.meta[SERVER_INFO_META_KEY] == {
        "name": "dianzi-current-read-tools",
        "version": "0.1.0",
    }
    assert budget.fits(result)
    raw = result.model_dump_json(by_alias=True, exclude_none=True)
    rows.append(
        {
            "protocol": protocol,
            "tokens": len(budget.encoding.encode_ordinary(raw)),
            "utf8_bytes": len(raw.encode()),
            "profile": budget.profile,
            "complete_meta_counted": True,
        }
    )
(RUN / "safe_error_budget_observation.json").write_bytes(
    json.dumps(rows, indent=2).encode() + b"\n"
)
print(json.dumps(rows, indent=2))
