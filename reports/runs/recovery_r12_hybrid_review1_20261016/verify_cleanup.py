"""Check only this review's resource prefixes and verify frozen business files remain intact."""

import json
import os

import httpx
from sqlalchemy import create_engine, text

from review_runner import RUN, audit, git, services, stamp


def main() -> None:
    services()
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    with engine.connect() as connection:
        schemas = list(connection.scalars(text("SELECT nspname FROM pg_namespace WHERE nspname ~ '^test_r12_review1_[a-f0-9]{32}$' ORDER BY nspname")))
    engine.dispose()
    with httpx.Client(base_url="http://127.0.0.1:29200", timeout=5, follow_redirects=False) as client:
        response = client.get("/_cat/indices/dianzi_test_r12_review1_*", params={"format": "json", "h": "index"})
    assert response.status_code in {200, 404}
    indices = [] if response.status_code == 404 else [row["index"] for row in response.json()]
    assert all(name.startswith("dianzi_test_r12_review1_") for name in indices)
    business_diff = git("diff", "--", "backend/src", "backend/tests", "backend/pyproject.toml", "backend/uv.lock", "config", "progress")
    assert not business_diff and not schemas and not indices
    audit()
    receipt = dict(checked_at=stamp(), remaining_owned_schemas=schemas, remaining_owned_indices=indices, scoped_search_status=response.status_code, business_diff="empty", test_database="retained_for_reproduction", status="passed")
    (RUN / "cleanup_verification.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
