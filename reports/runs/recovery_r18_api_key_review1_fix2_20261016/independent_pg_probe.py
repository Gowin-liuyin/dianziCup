"""Real owned PostgreSQL concurrency and lock-wait probes with no secret output."""

import hashlib
import json
import os
import secrets
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from pydantic import SecretStr
from sqlalchemy import create_engine, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.dev import require_isolated_test_database
from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.credential_models import api_key_rate_buckets, api_keys
from ai_intel.api.credentials import (
    ApiKeyCredential, ApiKeyRateLimitedError, InvalidApiKeyError, PgApiKeyService,
    SessionCredential, consume_api_key_rate_limit, lock_authenticated_principal,
)
from ai_intel.knowledge.models import metadata, users


def main():
    configured = make_url(require_isolated_test_database())
    schema = "r18c_" + uuid4().hex
    engine = create_engine(configured, poolclass=NullPool, hide_parameters=True,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=12000 -c lock_timeout=8000"},
        execution_options={"schema_translate_map": {None: schema}})
    now = datetime.now(UTC)
    user_id = "reviewer-" + uuid4().hex
    session = SessionCredential(SecretStr(secrets.token_urlsafe(32)))
    observations = {"database": configured.database, "schema": schema,
                    "started_at": datetime.now().astimezone().isoformat()}
    created = False
    failure = None
    try:
        with engine.begin() as connection:
            actual = connection.execute(text("SELECT current_database(),current_user")).one()
            assert actual[0] == configured.database and actual[1] == configured.username
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            metadata.create_all(connection, tables=[users, auth_sessions, api_keys, api_key_rate_buckets])
            connection.execute(insert(users).values(user_id=user_id, username=user_id,
                password_hash="synthetic-not-for-login", tenant_id="reviewer-original", role="analyst", created_at=now))
            connection.execute(insert(auth_sessions).values(
                session_hash=hashlib.sha256(session.token.get_secret_value().encode()).hexdigest(),
                user_id=user_id, csrf_token="reviewersynthetic", issued_at=now,
                expires_at=now + timedelta(hours=1), revoked_at=None))
        created = True
        service = PgApiKeyService(engine)
        issued = service.issue_key(session, frozenset({"read:public", "read:asset"}))
        asset = service.issue_key(session, frozenset({"read:asset"}))
        key = ApiKeyCredential(issued.token)
        at = datetime.now(UTC)

        def ask_once(_):
            try:
                with engine.begin() as connection:
                    consume_api_key_rate_limit(connection, key, at, operation="ask")
                return "committed"
            except ApiKeyRateLimitedError:
                return "limited"

        with ThreadPoolExecutor(max_workers=3) as executor:
            outcomes = list(executor.map(ask_once, range(12)))
        assert outcomes.count("committed") == 10 and outcomes.count("limited") == 2
        with engine.connect() as connection:
            assert connection.scalar(select(api_key_rate_buckets.c.request_count).where(
                api_key_rate_buckets.c.key_id == issued.metadata.key_id,
                api_key_rate_buckets.c.operation == "ask")) == 10
            row = connection.execute(select(api_keys).where(api_keys.c.key_id == issued.metadata.key_id)).mappings().one()
            assert row["resource"] == "urn:dianzi:api:v1" and row["user_id"] == user_id
            assert row["token_hash"] == hashlib.sha256(issued.token.get_secret_value().encode()).hexdigest()
        observations["quota"] = {"threads": 3, "attempts": 12, "committed": 10, "limited": 2,
                                 "hash_owner_resource_verified": True}

        def wait_auth(credential, changes, expires_at=None):
            reader = {}
            with engine.begin() as holding:
                holding.execute(changes)
                with ThreadPoolExecutor(max_workers=1) as executor:
                    def authenticate():
                        with engine.begin() as connection:
                            reader["pid"] = connection.scalar(text("SELECT pg_backend_pid()"))
                            reader["passed_now"] = datetime.now(UTC)
                            try:
                                scope = lock_authenticated_principal(connection, credential, reader["passed_now"])
                            except InvalidApiKeyError:
                                reader["outcome"] = "denied"
                                return None
                            reader["outcome"] = "authorized"
                            return scope
                    future = executor.submit(authenticate)
                    deadline = time.monotonic() + 4
                    while time.monotonic() < deadline:
                        if "pid" in reader:
                            with engine.connect() as observer:
                                event = observer.scalar(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"), reader)
                            if event == "Lock":
                                reader["actual_lock_wait"] = True
                                break
                        time.sleep(0.01)
                    assert reader.get("actual_lock_wait") and not future.done()
                    if expires_at is not None:
                        delay = (expires_at - datetime.now(UTC)).total_seconds() + 0.1
                        if delay > 0:
                            time.sleep(delay)
                    holding.commit()
                    scope = future.result(timeout=6)
                    reader["received_at"] = datetime.now(UTC)
                    if scope is not None:
                        reader.update({"role": scope.role.value, "tenant": scope.tenant_id,
                                       "permissions": sorted(scope.permissions)})
            reader.pop("pid", None)
            for name in ("passed_now", "received_at"):
                reader[name] = reader[name].isoformat()
            return reader

        role_result = wait_auth(key, update(users).where(users.c.user_id == user_id).values(
            role="viewer", tenant_id="reviewer-current"))
        assert role_result["role"] == "viewer" and role_result["tenant"] == "reviewer-current"
        assert role_result["permissions"] == ["read:public"]
        observations["role_and_tenant_during_wait"] = role_result
        try:
            with engine.begin() as connection:
                consume_api_key_rate_limit(connection, ApiKeyCredential(asset.token), datetime.now(UTC))
        except InvalidApiKeyError:
            observations["asset_scope_after_downgrade"] = "denied"
        else:
            raise AssertionError("downgraded asset-only key authorized")
        revoke_result = wait_auth(key, update(api_keys).where(api_keys.c.key_id == issued.metadata.key_id).values(
            revoked_at=datetime.now(UTC), version=api_keys.c.version+1))
        assert revoke_result["outcome"] == "denied"
        observations["revocation_during_wait"] = revoke_result
        first = service.revoke_key(session, issued.metadata.key_id)
        assert service.revoke_key(session, issued.metadata.key_id) == first
        observations["revoke_idempotent"] = True

        expires_at = datetime.now(UTC) + timedelta(seconds=3)
        expiring = service.issue_key(session, frozenset({"read:public"}), expires_at=expires_at)
        expiring_key = ApiKeyCredential(expiring.token)
        expired_result = wait_auth(expiring_key, update(users).where(users.c.user_id == user_id).values(
            tenant_id="reviewer-current"), expires_at)
        expired_result["expires_at"] = expires_at.isoformat()
        try:
            with engine.begin() as connection:
                lock_authenticated_principal(connection, expiring_key, datetime.now(UTC))
        except InvalidApiKeyError:
            expired_result["fresh_call_after_wait"] = "denied"
        else:
            expired_result["fresh_call_after_wait"] = "authorized"
        observations["expiry_during_wait"] = expired_result
        assert expired_result["outcome"] == "denied", "key expired during actual lock wait was authorized"
    except Exception as error:
        failure = type(error).__name__
        observations["failure_type"] = failure
    finally:
        if created:
            with engine.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        engine.dispose()
    observations.update({"ended_at": datetime.now().astimezone().isoformat(),
                         "schema_dropped": created, "status": "failed" if failure else "passed"})
    (RUN / "independent_pg_observation.json").write_text(json.dumps(observations, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"status": observations["status"], "schema_dropped": created,
                      "expiry_outcome": observations.get("expiry_during_wait", {}).get("outcome")}))
    return int(failure is not None)


if __name__ == "__main__":
    raise SystemExit(main())
