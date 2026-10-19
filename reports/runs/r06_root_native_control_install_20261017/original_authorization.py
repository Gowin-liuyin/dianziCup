"""The single new run starts only after exact root, resource and source binding."""

from __future__ import annotations

from pathlib import Path

from run_binding import (
    CORE_NAMES,
    OBSERVER_RELATIVE,
    OBSERVER_SHA,
    verify_live_binding,
)
from run_binding import PRODUCT_SHA as PRODUCT_SHA
from run_binding import TOOL_ROOT as TOOL_ROOT

RUN = Path(__file__).resolve().parent
GATE = RUN / "root_live_authorization.json"
ORIGINAL_OBSERVER_SHA = OBSERVER_SHA
ORIGINAL_OBSERVER_RELATIVE = OBSERVER_RELATIVE
SCRIPT_NAMES = CORE_NAMES


def verify_live_authorization() -> dict[str, object]:
    """Reject absent, unknown or changed binding before environment or product access."""
    return verify_live_binding()
