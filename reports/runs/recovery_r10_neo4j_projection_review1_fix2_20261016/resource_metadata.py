"""Read actual service metadata; cleanup only this review's registered namespace prefix."""

import json
import re
import sys

import neo4j
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError
from sqlalchemy import create_engine, text

from review_runner import DATABASE, MARKER, RUN, now, resources

url, resource = resources()
driver = GraphDatabase.driver(resource["NEO4J_TEST_BOLT_URL"],
    auth=(resource["NEO4J_TEST_USERNAME"], resource["NEO4J_TEST_PASSWORD"]),
    connection_timeout=2, connection_acquisition_timeout=2, max_connection_pool_size=4,
    max_transaction_retry_time=0, telemetry_disabled=True)
try:
    driver.verify_connectivity()
    with driver.session(database="neo4j") as session:
        components = session.run("CALL dbms.components() YIELD name,versions,edition RETURN name,versions,edition").data()
        settings = session.run("SHOW SETTINGS YIELD name,value WHERE name='dbms.usage_report.enabled' RETURN name,value").data()
        namespaces = session.run("MATCH(n) WHERE n.namespace STARTS WITH $prefix RETURN DISTINCT n.namespace AS namespace ORDER BY namespace",
                                 {"prefix": "r10_review1_fix2_"}).data()
        assert components[0]["versions"] == ["5.26.32"] and components[0]["edition"] == "community"
        assert settings == [{"name": "dbms.usage_report.enabled", "value": "false"}]
        names = [entry["namespace"] for entry in namespaces]
        assert all(re.fullmatch("r10_review1_fix2_[0-9a-f]{32}", name) for name in names)
        mode = "metadata"
        if "--cleanup" in sys.argv:
            mode = "cleanup"
            for namespace in names:
                session.run("MATCH(n) WHERE n.namespace=$namespace DETACH DELETE n", {"namespace": namespace}).consume()
            assert not session.run("MATCH(n) WHERE n.namespace STARTS WITH $prefix RETURN n LIMIT 1", {"prefix": "r10_review1_fix2_"}).data()
    rejected = GraphDatabase.driver(resource["NEO4J_TEST_BOLT_URL"], auth=(resource["NEO4J_TEST_USERNAME"], "review-invalid-not-a-secret"),
        connection_timeout=2, connection_acquisition_timeout=2, max_connection_pool_size=1,
        max_transaction_retry_time=0, telemetry_disabled=True)
    try:
        try:
            rejected.verify_connectivity()
        except AuthError:
            auth_enforced = True
        else:
            raise AssertionError("invalid authentication accepted")
    finally:
        rejected.close()
    engine = create_engine(url.set(database=DATABASE), connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            identity = connection.execute(text("SELECT current_database(),current_user")).one()
            assert identity == (DATABASE, url.username)
            marker = connection.execute(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=:name"), {"name": DATABASE}).scalar_one()
            assert marker == MARKER
            schemas = connection.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'test_r10r1f2_%'")).scalars().all()
            assert not schemas
    finally:
        engine.dispose()
    receipt = {"observed_at": now(), "mode": mode, "resource_id": resource["resource_id"],
               "deadline": resource["deadline"], "components": components, "settings": settings,
               "driver_version": neo4j.__version__, "driver_telemetry_disabled": True,
               "invalid_authentication_rejected": auth_enforced, "owned_pg_database": DATABASE,
               "owned_pg_marker_verified": True, "remaining_owned_pg_schemas": schemas,
               "owned_neo4j_namespaces": names, "namespace_count": len(names),
               "graceful_shutdown": "not_tested_here_current_graceful_check_owned_by_independent_resource_review"}
    (RUN / ("resource_" + mode + "_receipt.json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"mode": mode, "namespace_count": len(names), "metadata_guard": True}))
finally:
    driver.close()
