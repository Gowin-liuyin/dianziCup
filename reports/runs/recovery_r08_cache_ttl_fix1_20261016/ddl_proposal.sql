
CREATE TABLE r08_aggregate_observations (
	observation_id UUID NOT NULL, 
	schema_version TEXT NOT NULL, 
	canonical_json JSONB NOT NULL, 
	payload_sha256 TEXT NOT NULL, 
	call_key TEXT NOT NULL, 
	provider TEXT NOT NULL, 
	query_id TEXT NOT NULL, 
	query_version TEXT NOT NULL, 
	retrieved_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	observed_at TIMESTAMP WITH TIME ZONE, 
	recorded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	outcome TEXT NOT NULL, 
	error_code TEXT, 
	data_mode TEXT NOT NULL, 
	fee_status TEXT NOT NULL, 
	visibility TEXT NOT NULL, 
	tenant_id TEXT, 
	scope_key TEXT NOT NULL, 
	PRIMARY KEY (observation_id), 
	CONSTRAINT ck_r08_schema CHECK (schema_version = 'r08-aggregate-observation-1'), 
	CONSTRAINT ck_r08_provider CHECK (provider IN ('hunter','quake')), 
	CONSTRAINT ck_r08_query CHECK (query_id IN ('ollama','vllm')), 
	CONSTRAINT ck_r08_query_version CHECK (query_version = 'r08-product-name-1'), 
	CONSTRAINT ck_r08_mode CHECK (data_mode IN ('live','fixture')), 
	CONSTRAINT ck_r08_fee CHECK (fee_status = 'unknown'), 
	CONSTRAINT ck_r08_required_error CHECK (outcome = 'available' OR error_code IS NOT NULL), 
	CONSTRAINT ck_r08_hashes CHECK (payload_sha256 ~ '^[0-9a-f]{64}$' AND call_key ~ '^[0-9a-f]{64}$'), 
	CONSTRAINT ck_r08_scope CHECK ((visibility='public' AND tenant_id IS NULL AND scope_key='public') OR (visibility='tenant' AND tenant_id IS NOT NULL AND scope_key='tenant:' || tenant_id)), 
	CONSTRAINT ck_r08_outcome CHECK ((outcome='available' AND error_code IS NULL) OR (outcome='unknown' AND error_code='missing_total') OR (outcome='unauthorized' AND error_code='provider_unauthorized') OR (outcome='rate_limited' AND error_code='provider_rate_limited') OR (outcome='not_configured' AND error_code='credential_missing') OR (outcome='failed' AND error_code IN ('invalid_total','invalid_response','provider_http_error','provider_error','network_error','network_dns_error','network_tls_error','network_timeout','network_policy_violation','response_too_large','unsupported_content_type')))
)

;
CREATE INDEX ix_r08_current ON r08_aggregate_observations (call_key, scope_key, retrieved_at DESC, recorded_at DESC, (outcome = 'available') ASC, observation_id DESC);

CREATE FUNCTION r08_reject_aggregate_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'aggregate observation history is immutable' USING ERRCODE = '55000';
END;
$$
;

CREATE TRIGGER r08_aggregate_observations_immutable
BEFORE UPDATE OR DELETE ON r08_aggregate_observations
FOR EACH ROW EXECUTE FUNCTION r08_reject_aggregate_mutation()
;
