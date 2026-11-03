-- Generated 002_g4_briefings_v1; exact schema/source pins are in BASELINE.json.

CREATE TABLE intelligence_heads (
	id VARCHAR NOT NULL, 
	sequence INTEGER NOT NULL, 
	sha256 VARCHAR NOT NULL, 
	latest_snapshot_id VARCHAR, 
	publication_version INTEGER NOT NULL, 
	persona_version_id VARCHAR, 
	PRIMARY KEY (id), 
	CHECK (sequence >= 0 AND publication_version >= 0)
)

;

CREATE TABLE intelligence_installation (
	id VARCHAR NOT NULL, 
	database_id VARCHAR NOT NULL, 
	revision VARCHAR NOT NULL, 
	source_sha256 VARCHAR NOT NULL, 
	schema_sha256 VARCHAR NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE intelligence_entries (
	id VARCHAR NOT NULL, 
	stream_id VARCHAR NOT NULL, 
	sequence INTEGER NOT NULL, 
	previous_sha256 VARCHAR NOT NULL, 
	kind VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	data JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (stream_id, sequence), 
	CHECK (sequence > 0), 
	FOREIGN KEY(stream_id) REFERENCES intelligence_heads (id)
)

;

CREATE TABLE intelligence_persona_versions (
	id VARCHAR NOT NULL, 
	stream_id VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	available_at VARCHAR NOT NULL, 
	data JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (stream_id, version), 
	CHECK (version > 0), 
	FOREIGN KEY(stream_id) REFERENCES intelligence_heads (id)
)

;

CREATE TABLE intelligence_requests (
	id VARCHAR NOT NULL, 
	stream_id VARCHAR NOT NULL, 
	"key" VARCHAR NOT NULL, 
	operation VARCHAR NOT NULL, 
	request_sha256 VARCHAR NOT NULL, 
	data JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (stream_id, "key"), 
	FOREIGN KEY(stream_id) REFERENCES intelligence_heads (id)
)

;

CREATE TABLE intelligence_runs (
	id VARCHAR NOT NULL, 
	stream_id VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	cancel_requested BOOLEAN NOT NULL, 
	created_at VARCHAR NOT NULL, 
	input_sha256 VARCHAR NOT NULL, 
	input JSON NOT NULL, 
	data JSON NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (version > 0), 
	CHECK (status IN ('queued','running','completed','cancelled','failed','stale','timed_out','interrupted','evidence_not_ready')), 
	FOREIGN KEY(stream_id) REFERENCES intelligence_heads (id)
)

;

CREATE TABLE intelligence_snapshots (
	id VARCHAR NOT NULL, 
	stream_id VARCHAR NOT NULL, 
	run_id VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	as_of VARCHAR NOT NULL, 
	generated_at VARCHAR NOT NULL, 
	runtime_sha256 VARCHAR NOT NULL, 
	runtime JSON NOT NULL, 
	data JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (stream_id, version), 
	CHECK (version > 0), 
	FOREIGN KEY(stream_id) REFERENCES intelligence_heads (id), 
	UNIQUE (run_id), 
	FOREIGN KEY(run_id) REFERENCES intelligence_runs (id)
)

;

CREATE TABLE intelligence_archive_items (
	id VARCHAR NOT NULL, 
	stream_id VARCHAR NOT NULL, 
	snapshot_id VARCHAR NOT NULL, 
	event_snapshot_id VARCHAR NOT NULL, 
	data JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (snapshot_id, event_snapshot_id), 
	FOREIGN KEY(stream_id) REFERENCES intelligence_heads (id), 
	FOREIGN KEY(snapshot_id) REFERENCES intelligence_snapshots (id)
)

;

CREATE TABLE intelligence_delivery_items (
	id VARCHAR NOT NULL, 
	stream_id VARCHAR NOT NULL, 
	snapshot_id VARCHAR NOT NULL, 
	event_snapshot_id VARCHAR NOT NULL, 
	ordinal INTEGER NOT NULL, 
	data JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (snapshot_id, event_snapshot_id), 
	FOREIGN KEY(stream_id) REFERENCES intelligence_heads (id), 
	FOREIGN KEY(snapshot_id) REFERENCES intelligence_snapshots (id)
)

;

CREATE TABLE intelligence_interactions (
	id VARCHAR NOT NULL, 
	stream_id VARCHAR NOT NULL, 
	snapshot_id VARCHAR NOT NULL, 
	target_id VARCHAR NOT NULL, 
	kind VARCHAR NOT NULL, 
	journal_sequence INTEGER NOT NULL, 
	ordinal INTEGER NOT NULL, 
	observation_key VARCHAR, 
	retracts_id VARCHAR, 
	available_at VARCHAR NOT NULL, 
	data JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (stream_id, journal_sequence, ordinal), 
	CHECK (journal_sequence > 0 AND ordinal >= 0), 
	CHECK (kind IN ('included','rendered','opened','ack','dismiss','retract')), 
	FOREIGN KEY(stream_id) REFERENCES intelligence_heads (id), 
	FOREIGN KEY(snapshot_id) REFERENCES intelligence_snapshots (id), 
	UNIQUE (observation_key), 
	UNIQUE (retracts_id), 
	FOREIGN KEY(retracts_id) REFERENCES intelligence_interactions (id)
)

;
CREATE INDEX ix_intelligence_entries_stream_id ON intelligence_entries (stream_id);
CREATE INDEX ix_intelligence_persona_versions_stream_id ON intelligence_persona_versions (stream_id);
CREATE INDEX ix_intelligence_requests_stream_id ON intelligence_requests (stream_id);
CREATE INDEX ix_intelligence_runs_status ON intelligence_runs (status);
CREATE INDEX ix_intelligence_runs_stream_id ON intelligence_runs (stream_id);
CREATE INDEX ix_intelligence_snapshots_stream_id ON intelligence_snapshots (stream_id);
CREATE INDEX ix_intelligence_archive_items_snapshot_id ON intelligence_archive_items (snapshot_id);
CREATE INDEX ix_intelligence_archive_items_stream_id ON intelligence_archive_items (stream_id);
CREATE INDEX ix_intelligence_delivery_items_snapshot_id ON intelligence_delivery_items (snapshot_id);
CREATE INDEX ix_intelligence_delivery_items_stream_id ON intelligence_delivery_items (stream_id);
CREATE INDEX ix_intelligence_interactions_snapshot_id ON intelligence_interactions (snapshot_id);
CREATE INDEX ix_intelligence_interactions_stream_id ON intelligence_interactions (stream_id);
CREATE TRIGGER intelligence_archive_items_no_update BEFORE UPDATE ON intelligence_archive_items BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_archive_items_no_delete BEFORE DELETE ON intelligence_archive_items BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_delivery_items_no_update BEFORE UPDATE ON intelligence_delivery_items BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_delivery_items_no_delete BEFORE DELETE ON intelligence_delivery_items BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_entries_no_update BEFORE UPDATE ON intelligence_entries BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_entries_no_delete BEFORE DELETE ON intelligence_entries BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_installation_no_update BEFORE UPDATE ON intelligence_installation BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_installation_no_delete BEFORE DELETE ON intelligence_installation BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_interactions_no_update BEFORE UPDATE ON intelligence_interactions BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_interactions_no_delete BEFORE DELETE ON intelligence_interactions BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_persona_versions_no_update BEFORE UPDATE ON intelligence_persona_versions BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_persona_versions_no_delete BEFORE DELETE ON intelligence_persona_versions BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_requests_no_update BEFORE UPDATE ON intelligence_requests BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_requests_no_delete BEFORE DELETE ON intelligence_requests BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_snapshots_no_update BEFORE UPDATE ON intelligence_snapshots BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_snapshots_no_delete BEFORE DELETE ON intelligence_snapshots BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_entries_linear BEFORE INSERT ON intelligence_entries
      BEGIN SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM intelligence_heads h
        WHERE h.id=NEW.stream_id AND NEW.sequence=h.sequence+1 AND NEW.previous_sha256=h.sha256)
        THEN RAISE(ABORT,'G4_HISTORY_CHAIN_INVALID') END; END;
CREATE TRIGGER intelligence_head_cas BEFORE UPDATE ON intelligence_heads
      BEGIN SELECT CASE WHEN NEW.id<>OLD.id OR NEW.sequence<>OLD.sequence+1 OR NOT EXISTS
        (SELECT 1 FROM intelligence_entries e WHERE e.stream_id=OLD.id AND e.sequence=NEW.sequence
         AND e.previous_sha256=OLD.sha256 AND e.id=NEW.sha256)
        THEN RAISE(ABORT,'G4_HEAD_CAS_REQUIRED') END; END;
CREATE TRIGGER intelligence_head_no_delete BEFORE DELETE ON intelligence_heads
      BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_run_no_delete BEFORE DELETE ON intelligence_runs
      BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END;
CREATE TRIGGER intelligence_run_version BEFORE UPDATE ON intelligence_runs
      BEGIN SELECT CASE WHEN NEW.id<>OLD.id OR NEW.stream_id<>OLD.stream_id OR NEW.version<>OLD.version+1
        OR NEW.created_at<>OLD.created_at OR NEW.input_sha256<>OLD.input_sha256 OR NEW.input<>OLD.input
        OR OLD.status IN ('completed','cancelled','failed','stale','timed_out','interrupted','evidence_not_ready')
        THEN RAISE(ABORT,'G4_RUN_TRANSITION_INVALID') END; END;
