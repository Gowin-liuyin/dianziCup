"""Forward frozen recovery DDL; historical rows retain authority.

Revision ID: 0023_enrichment_input_audit
Revises: 0022_sbom_sidecars
"""

from alembic import op

revision = "0023_enrichment_input_audit"
down_revision = "0022_sbom_sidecars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add only the approved fields, sidecars and integrity guards."""
    op.execute(
        """
ALTER TABLE enrichment_job_steps ADD COLUMN input_audit_payload jsonb
        """
    )
    op.execute(
        """
ALTER TABLE enrichment_job_steps ADD COLUMN input_audit_sha256 text
        """
    )
    op.execute(
        """
ALTER TABLE enrichment_job_steps ADD CONSTRAINT ck_enrichment_step_input_audit CHECK
((input_audit_payload IS NULL AND input_audit_sha256 IS NULL) OR
(jsonb_typeof(input_audit_payload)='object' AND octet_length(input_audit_payload::text)<=4194304 AND
input_audit_sha256 ~ '^[0-9a-f]{64}$' AND
input_audit_sha256=encode(sha256(convert_to(input_audit_payload::text,'UTF8')),'hex') AND dimension
IN ('atlas','versions','literature','poc') AND model_call_reserved_at IS NOT NULL AND
model_call_completed_at IS NOT NULL AND jsonb_array_length(model_trace)=1 AND
input_audit_payload->>'audit_version'='r07-input-audit-1' AND input_audit_payload->>'job_id'=job_id
AND input_audit_payload->>'workflow_id'=workflow_id AND input_audit_payload->>'dimension'=dimension
AND input_audit_payload->>'input_fingerprint' ~ '^[0-9a-f]{64}$' AND
input_audit_payload->>'execution_policy_sha256' ~ '^[0-9a-f]{64}$' AND
input_audit_payload->>'model_version'=model_trace->0->>'requested_model' AND
input_audit_payload->>'provider'=model_trace->0->>'provider' AND
input_audit_payload->'model_input_versions'->>'prompt_version'=model_trace->0->>'prompt_version' AND
input_audit_payload->'model_input_versions'->>'schema_version'=model_trace->0->>'schema_version' AND
jsonb_typeof(input_audit_payload->'input_selections')='array' AND
jsonb_array_length(input_audit_payload->'input_selections')=1) IS TRUE)
        """
    )
    op.execute(
        """
CREATE FUNCTION guard_enrichment_input_audit() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE frozen_input text; frozen_policy text; frozen_versions jsonb;
    BEGIN
        IF TG_OP='INSERT' AND NEW.input_audit_payload IS NOT NULL THEN
            RAISE EXCEPTION 'input audit requires a precreated step' USING ERRCODE='23514';
        END IF;
        IF TG_OP='UPDATE' AND OLD.input_audit_payload IS NOT NULL AND
           (NEW.input_audit_payload, NEW.input_audit_sha256, NEW.model_trace,
            NEW.model_call_reserved_at, NEW.model_call_completed_at) IS DISTINCT FROM
           (OLD.input_audit_payload, OLD.input_audit_sha256, OLD.model_trace,
            OLD.model_call_reserved_at, OLD.model_call_completed_at) THEN
            RAISE EXCEPTION 'input audit receipt is immutable' USING ERRCODE='23514';
        END IF;
        IF NEW.input_audit_payload IS NOT NULL THEN
            SELECT input_fingerprint, execution_policy_sha256,
                   execution_policy->'model_input_versions'
              INTO frozen_input, frozen_policy, frozen_versions
              FROM enrichment_workflows WHERE workflow_id=NEW.workflow_id;
            IF (NEW.input_audit_payload->>'input_fingerprint'=frozen_input AND
                NEW.input_audit_payload->>'execution_policy_sha256'=frozen_policy AND
                NEW.input_audit_payload->'model_input_versions'=frozen_versions) IS NOT TRUE THEN
                RAISE EXCEPTION 'input audit workflow identity invalid' USING ERRCODE='23514';
            END IF;
        END IF;
        RETURN NEW;
    END $$
        """
    )
    op.execute(
        """
CREATE TRIGGER enrichment_input_audit_guard BEFORE INSERT OR UPDATE ON enrichment_job_steps FOR EACH
ROW EXECUTE FUNCTION guard_enrichment_input_audit();
        """
    )
    op.execute(
        """
ALTER FUNCTION guard_enrichment_input_audit() SET search_path FROM CURRENT
        """
    )
    op.execute(
        """
CREATE FUNCTION prevent_enrichment_input_audit_deletion() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
IF OLD.input_audit_payload IS NOT NULL THEN
RAISE EXCEPTION 'input audit receipt is immutable' USING ERRCODE='23514';
END IF;
RETURN OLD;
END $$
        """
    )
    op.execute(
        """
CREATE TRIGGER enrichment_input_audit_delete_guard BEFORE DELETE ON enrichment_job_steps
FOR EACH ROW EXECUTE FUNCTION prevent_enrichment_input_audit_deletion()
        """
    )


def downgrade() -> None:
    """Preserve receipts and revocation history; use approved forward repair."""
    raise RuntimeError("recovery history requires forward-only recovery")
