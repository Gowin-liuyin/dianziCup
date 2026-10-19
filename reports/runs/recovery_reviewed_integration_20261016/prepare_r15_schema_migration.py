"""Freeze public wire schemas and compile the approved four-table migration from metadata."""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

ROOT = Path(__file__).resolve().parents[3]
AUTHOR = Path("D:/wt/r15-persistent-subscriptions")
sys.path.insert(0, str(AUTHOR / "backend/src"))
from ai_intel.recommendations import persistence_models as models
from ai_intel.recommendations import service_contracts as contracts

target = ROOT / "backend/migrations/versions/0027_recommendation_history.py"
assert not target.exists()
statements = []
for table in models.R15_TABLES:
    statements.append(str(CreateTable(table).compile(dialect=postgresql.dialect())).strip())
    statements.extend(str(CreateIndex(index).compile(dialect=postgresql.dialect())) for index in sorted(table.indexes, key=lambda item: item.name))
statements.extend([
    """CREATE FUNCTION prevent_r15_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
RAISE EXCEPTION 'recommendation history is immutable' USING ERRCODE='23514'; END $$""",
    """CREATE TRIGGER r15_generations_immutable BEFORE UPDATE OR DELETE ON r15_generations
FOR EACH ROW EXECUTE FUNCTION prevent_r15_history_mutation()""",
    """CREATE TRIGGER r15_reports_immutable BEFORE UPDATE OR DELETE ON r15_reports
FOR EACH ROW EXECUTE FUNCTION prevent_r15_history_mutation()""",
    """CREATE FUNCTION protect_r15_subscription() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
IF TG_OP='DELETE' THEN RAISE EXCEPTION 'subscription history is immutable' USING ERRCODE='23514'; END IF;
IF ROW(NEW.id,NEW.tenant_id,NEW.user_id,NEW.created_at) IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.user_id,OLD.created_at)
OR NEW.version<>OLD.version+1 OR NEW.updated_at<OLD.updated_at THEN
RAISE EXCEPTION 'subscription owner or version is invalid' USING ERRCODE='23514'; END IF;
RETURN NEW; END $$""",
    """CREATE TRIGGER r15_subscriptions_owner_version BEFORE UPDATE OR DELETE ON r15_subscriptions
FOR EACH ROW EXECUTE FUNCTION protect_r15_subscription()""",
    """CREATE FUNCTION protect_r15_recommendation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
IF TG_OP='DELETE' THEN RAISE EXCEPTION 'recommendation history is immutable' USING ERRCODE='23514'; END IF;
IF (to_jsonb(NEW)-ARRAY['read_at','current_status','current_reason','current_checked_at'])
IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['read_at','current_status','current_reason','current_checked_at'])
OR (OLD.read_at IS NOT NULL AND NEW.read_at IS DISTINCT FROM OLD.read_at)
OR NEW.current_checked_at<OLD.current_checked_at THEN
RAISE EXCEPTION 'recommendation history is immutable' USING ERRCODE='23514'; END IF;
RETURN NEW; END $$""",
    """CREATE TRIGGER r15_recommendations_history BEFORE UPDATE OR DELETE ON r15_recommendations
FOR EACH ROW EXECUTE FUNCTION protect_r15_recommendation()""",
])
body = '"""Persist approved subscription ownership and immutable recommendation/report history."""\n\nfrom alembic import op\n\nrevision = "0027_recommendation_history"\ndown_revision = "0026_api_key_credentials"\nbranch_labels = None\ndepends_on = None\n\n\ndef upgrade() -> None:\n    """Install the frozen four tables and narrowly mutable current/read overlays."""\n'
for statement in statements:
    body += "    op.execute(" + repr(statement) + ")\n"
body += '\n\ndef downgrade() -> None:\n    """Retain immutable history; recovery uses reviewed forward repairs."""\n    raise RuntimeError("recommendation history requires forward-only recovery")\n'
target.write_text(body, encoding="utf-8", newline="\n")
definitions = {}
for name in ("SubscriptionRecord", "SubscriptionPage", "RecommendationRecord", "RecommendationPage", "ReportReceipt", "ReportPage"):
    schema = getattr(contracts, name).model_json_schema()
    for key, definition in schema.pop("$defs", {}).items():
        assert key not in definitions or definitions[key] == definition
        definitions[key] = definition
    definitions[name] = schema
public_spec = json.loads(json.dumps(definitions["SubscriptionSpec"]))
public_spec["title"] = "PublicSubscriptionSpec"
public_spec["properties"]["minimum_priority"] = public_spec["properties"].pop("maximum_priority_bucket")
public_spec["properties"]["minimum_priority"]["description"] = "Lowest included priority: identical integer maps to internal maximum_priority_bucket; 0 highest only, 3 all."
for name in ("product_keys", "asset_ids", "risk_topics"):
    public_spec["properties"][name]["uniqueItems"] = True
public_spec["anyOf"] = [{"properties": {name: {"minItems": 1}}, "required": [name]} for name in ("product_keys", "asset_ids", "risk_topics")]
definitions["PublicSubscriptionSpec"] = public_spec
definitions["CreateSubscription"] = {"type": "object", "additionalProperties": False, "required": ["spec"], "properties": {"spec": {"$ref": "#/$defs/PublicSubscriptionSpec"}}}
definitions["ReplaceSubscription"] = {"type": "object", "additionalProperties": False, "required": ["expected_version", "spec"], "properties": {"expected_version": {"type": "integer", "minimum": 1}, "spec": {"$ref": "#/$defs/PublicSubscriptionSpec"}}}
definitions["SetSubscriptionEnabled"] = {"type": "object", "additionalProperties": False, "required": ["expected_version", "enabled"], "properties": {"expected_version": {"type": "integer", "minimum": 1}, "enabled": {"type": "boolean"}}}
schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "urn:dianzi:recommendation-api:v1", "schema_version": 1, "$defs": definitions, "x-change-records": ["CR-R15_persistent_subscription_interfaces", "CR-R15_public_workbench_contract"]}
output = ROOT / "contracts/schemas/recommendation_api_v1.json"
assert not output.exists()
output.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
receipt = {"created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "metadata_source": str(AUTHOR / "backend/src/ai_intel/recommendations/persistence_models.py"), "metadata_sha256": hashlib.sha256((AUTHOR / "backend/src/ai_intel/recommendations/persistence_models.py").read_bytes()).hexdigest(), "migration": str(target.relative_to(ROOT)), "statements": len(statements), "schema": str(output.relative_to(ROOT)), "definitions": len(definitions), "pg_executed": False, "accepted": False}
(ROOT / "reports/runs/recovery_reviewed_integration_20261016/r15_schema_migration_preparation.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
