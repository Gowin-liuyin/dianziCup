"""独立Python进程真实读取/并发发布, 只输出身份和测试事实值。"""

import json
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, Role
from ai_intel.knowledge.persistence import ClaimSubmission, KnowledgeRepository

request = json.load(sys.stdin)
submission = ClaimSubmission.model_validate(request["submission"])
engine = create_engine(os.environ["TEST_DATABASE_URL"], connect_args={"connect_timeout": 5})
try:
    with Session(engine) as session, session.begin():
        scope = AccessScope.for_authenticated_user("test-process", None, Role.SYSTEM_ADMIN)
        repository = KnowledgeRepository(session, scope)
        if sys.argv[1] == "publish":
            receipt = repository.publish(
                request["key"],
                submission.record.scope,
                (submission,),
                created_at=datetime(2026, 10, 15, tzinfo=UTC),
            )
            print(json.dumps({"receipt_id": receipt.receipt_id}))
        elif sys.argv[1] == "read":
            record = repository.get_claim(submission.record.claim_id.value)
            print(
                json.dumps({"claim_id": record.claim_id.value, "object_value": record.object_value})
            )
        else:
            raise ValueError("unsupported fixed probe mode")
except Exception:
    print("isolated process probe failed", file=sys.stderr)
    raise SystemExit(1) from None
finally:
    engine.dispose()
