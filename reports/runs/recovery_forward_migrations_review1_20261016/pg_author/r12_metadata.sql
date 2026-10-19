CREATE TABLE qa_conversations (
	conversation_id UUID NOT NULL, 
	schema_version INTEGER NOT NULL, 
	user_id TEXT NOT NULL, 
	tenant_id TEXT, 
	status TEXT NOT NULL, 
	version BIGINT NOT NULL, 
	active_turn_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (conversation_id), 
	CONSTRAINT ck_qa_conversation_version CHECK (schema_version=1 AND version>=0), 
	CONSTRAINT ck_qa_conversation_status CHECK ((status='active' AND revoked_at IS NULL) OR (status='revoked' AND revoked_at IS NOT NULL)), 
	FOREIGN KEY(user_id) REFERENCES users (user_id)
);

CREATE TABLE qa_conversation_turns (
	turn_id UUID NOT NULL, 
	schema_version INTEGER NOT NULL, 
	conversation_id UUID NOT NULL, 
	user_id TEXT NOT NULL, 
	tenant_id TEXT, 
	turn_number BIGINT NOT NULL, 
	base_conversation_version BIGINT NOT NULL, 
	answer_id TEXT NOT NULL, 
	context_sha256 TEXT NOT NULL, 
	resolved_context JSONB NOT NULL, 
	admitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (turn_id), 
	CONSTRAINT ck_qa_turn_version CHECK (schema_version=1 AND turn_number>=1 AND base_conversation_version>=0), 
	CONSTRAINT ck_qa_turn_context CHECK (context_sha256 ~ '^[0-9a-f]{64}$' AND jsonb_typeof(resolved_context)='object'), 
	CONSTRAINT uq_qa_turn_number UNIQUE (conversation_id, turn_number), 
	CONSTRAINT uq_qa_turn_conversation_identity UNIQUE (conversation_id, turn_id), 
	FOREIGN KEY(conversation_id) REFERENCES qa_conversations (conversation_id), 
	FOREIGN KEY(user_id) REFERENCES users (user_id), 
	UNIQUE (answer_id), 
	FOREIGN KEY(answer_id) REFERENCES grounded_answers (answer_id)
);

ALTER TABLE qa_conversations ADD CONSTRAINT fk_qa_active_turn FOREIGN KEY(conversation_id, active_turn_id) REFERENCES qa_conversation_turns (conversation_id, turn_id) DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX ix_qa_conversation_owner ON qa_conversations (user_id, tenant_id, updated_at, conversation_id);
