"""Read-only diagnosis of the first two owned harness assertions."""

import ctypes
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from browser_runner import ROOT, RUN, configure_database

configured = configure_database()
engine = create_engine(configured, hide_parameters=True, poolclass=NullPool)
try:
    with engine.connect() as connection:
        observed = {
            "schema": connection.scalar(text("SELECT current_schema()")),
            "head": connection.scalar(text("SELECT version_num FROM alembic_version")),
            "sidecar": connection.scalar(text("SELECT to_regclass('asset_snapshot_sbom_sidecars')")),
            "renamed_sidecar": connection.scalar(text("SELECT to_regclass('r17_owned_unavailable_sbom_sidecars')")),
            "own_other_connections": connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()")),
        }
finally:
    engine.dispose()
boot = json.loads((RUN / "api_boot.json").read_text())
session = ctypes.c_ulong()
ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session))
observed.update({"parent_session_id": session.value, "boot_session_id": boot["session_id"], "factory_within_root": Path(boot["default_factory"]).is_relative_to(ROOT / "backend/src"), "root": str(ROOT)})
(RUN / "runtime_diagnosis.json").write_text(json.dumps(observed, indent=2) + "\n", encoding="utf8")
print(json.dumps(observed))
