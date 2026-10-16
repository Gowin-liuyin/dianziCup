"""Fresh application process verifies only restored marked synthetic records, no output content."""

import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.pool import NullPool

from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.knowledge.models import content_objects, document_revisions, evidence, job_runs

engine = create_engine(
    os.environ["R20_RESTART_DATABASE_URL"], poolclass=NullPool, hide_parameters=True,
    connect_args={"connect_timeout": 5, "options": "-csearch_path=r20_backup_data,public -cstatement_timeout=5000"},
)
try:
    with engine.connect() as connection:
        comment = connection.scalar(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()"))
        assert comment.startswith("dianzi-rehearsal:r20_backup_")
    auth = AuthenticationSessionService(
        DatabaseUserDirectory(engine), ("https://example.invalid",), False,
        state_store=PgAuthenticationStateStore(engine),
    )
    authenticated = auth.validate_session(os.environ["R20_RESTART_SESSION_TOKEN"]).tenant_id == "tenant_a"
    store = ContentStore(Path(os.environ["R20_RESTART_CONTENT_DIRECTORY"]))
    with engine.connect() as connection:
        history = len(connection.execute(select(document_revisions.c.revision_id)).all())
        evidence_count = len(connection.execute(select(evidence.c.evidence_id)).all())
        status = connection.scalar(select(job_runs.c.status))
        objects = connection.execute(select(content_objects.c.content_hash)).scalars().all()
        for digest in objects:
            assert hashlib.sha256(store.read_verified(digest)).hexdigest() == digest
    print(json.dumps({"authenticated": authenticated, "history": history, "evidence": evidence_count, "job_status": status, "objects_verified": len(objects)}))
finally:
    engine.dispose()
