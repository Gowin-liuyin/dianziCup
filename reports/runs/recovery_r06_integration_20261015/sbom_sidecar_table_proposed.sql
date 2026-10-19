
CREATE TABLE asset_snapshot_sbom_sidecars (
	snapshot_id TEXT NOT NULL, 
	asset_id TEXT NOT NULL, 
	tenant_id TEXT NOT NULL, 
	adapter_version TEXT NOT NULL, 
	spec_version TEXT NOT NULL, 
	sidecar_sha256 TEXT NOT NULL, 
	combined_semantic_sha256 TEXT NOT NULL, 
	canonical_payload JSONB NOT NULL, 
	PRIMARY KEY (snapshot_id), 
	CONSTRAINT fk_sbom_sidecar_snapshot_tenant FOREIGN KEY(asset_id, tenant_id, snapshot_id) REFERENCES asset_snapshots (asset_id, tenant_id, snapshot_id), 
	CONSTRAINT ck_sbom_sidecar_tenant CHECK (length(tenant_id) BETWEEN 1 AND 200), 
	CONSTRAINT ck_sbom_adapter_version CHECK (length(adapter_version) BETWEEN 1 AND 200), 
	CONSTRAINT ck_sbom_spec_version CHECK (length(spec_version) BETWEEN 1 AND 200), 
	CONSTRAINT ck_sbom_sidecar_sha256 CHECK (sidecar_sha256 ~ '^[0-9a-f]{64}$'), 
	CONSTRAINT ck_sbom_combined_sha256 CHECK (combined_semantic_sha256 ~ '^[0-9a-f]{64}$'), 
	CONSTRAINT ck_sbom_sidecar_payload CHECK (jsonb_typeof(canonical_payload) = 'object')
)

