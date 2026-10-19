CREATE TABLE graph_projection_batches (
	batch_id TEXT NOT NULL, 
	namespace TEXT NOT NULL, 
	partition_key TEXT NOT NULL, 
	generation_id TEXT NOT NULL, 
	event_id TEXT NOT NULL, 
	sequence BIGINT NOT NULL, 
	kind TEXT NOT NULL, 
	payload_sha256 TEXT NOT NULL, 
	payload BYTEA NOT NULL, 
	captured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (batch_id), 
	CONSTRAINT uq_graph_projection_sequence UNIQUE (namespace, partition_key, generation_id, event_id, sequence), 
	CONSTRAINT ck_graph_projection_sequence CHECK (sequence > 0), 
	CONSTRAINT ck_graph_projection_kind CHECK (kind IN ('snapshot','tombstone')), 
	CONSTRAINT ck_graph_projection_payload CHECK (octet_length(payload) <= 8388608), 
	CONSTRAINT ck_graph_projection_digest CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE graph_projection_state (
	namespace TEXT NOT NULL, 
	partition_key TEXT NOT NULL, 
	generation_id TEXT NOT NULL, 
	state_key TEXT NOT NULL, 
	state_kind TEXT NOT NULL, 
	event_id TEXT, 
	body JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (namespace, partition_key, generation_id, state_key), 
	CONSTRAINT ck_graph_state_kind CHECK (state_kind IN ('partition','page','slot')), 
	CONSTRAINT ck_graph_state_event CHECK ((state_kind = 'slot') = (event_id IS NOT NULL))
);
