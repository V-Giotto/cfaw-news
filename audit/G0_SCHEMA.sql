-- Observed G0 schema, NOT a migration or restore script.
-- SQL schema only; no user records are included.

CREATE INDEX ix_decisions_goal_id ON decisions (goal_id);

CREATE INDEX ix_run_events_run_id ON run_events (run_id);

CREATE INDEX ix_runs_created_at ON runs (created_at);

CREATE INDEX ix_runs_goal_id ON runs (goal_id);

CREATE INDEX ix_runs_status ON runs (status);

CREATE TABLE article_media (
	article_id VARCHAR NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (article_id),
	FOREIGN KEY(article_id) REFERENCES articles (id)
);

CREATE TABLE article_reading (
	article_id VARCHAR NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (article_id),
	FOREIGN KEY(article_id) REFERENCES articles (id)
);

CREATE TABLE articles (
	id VARCHAR NOT NULL,
	content_hash VARCHAR NOT NULL,
	origin VARCHAR NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE decisions (
	id VARCHAR NOT NULL,
	run_id VARCHAR NOT NULL,
	goal_id VARCHAR NOT NULL,
	goal_version INTEGER NOT NULL,
	basis_hash VARCHAR NOT NULL,
	choice VARCHAR NOT NULL,
	reason TEXT NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (run_id),
	FOREIGN KEY(run_id) REFERENCES runs (id),
	FOREIGN KEY(goal_id) REFERENCES goals (id)
);

CREATE TABLE goals (
	id VARCHAR NOT NULL,
	version INTEGER NOT NULL,
	status VARCHAR NOT NULL,
	is_demo BOOLEAN NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE meta (
	"key" VARCHAR NOT NULL,
	value VARCHAR NOT NULL,
	PRIMARY KEY ("key")
);

CREATE TABLE run_events (
	id INTEGER NOT NULL,
	run_id VARCHAR NOT NULL,
	kind VARCHAR NOT NULL,
	message TEXT NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(run_id) REFERENCES runs (id)
);

CREATE TABLE runs (
	id VARCHAR NOT NULL,
	goal_id VARCHAR NOT NULL,
	goal_version INTEGER NOT NULL,
	status VARCHAR NOT NULL,
	mode VARCHAR NOT NULL,
	snapshot JSON NOT NULL,
	result JSON,
	basis_hash VARCHAR NOT NULL,
	error TEXT,
	cancel_requested BOOLEAN NOT NULL,
	created_at VARCHAR NOT NULL,
	finished_at VARCHAR,
	metrics JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(goal_id) REFERENCES goals (id)
);

CREATE TABLE schedules (
	id VARCHAR NOT NULL,
	proposal_key VARCHAR NOT NULL,
	run_id VARCHAR NOT NULL,
	title VARCHAR NOT NULL,
	content TEXT NOT NULL,
	start VARCHAR NOT NULL,
	"end" VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (proposal_key),
	FOREIGN KEY(run_id) REFERENCES runs (id)
);

CREATE TABLE source_states (
	source_id VARCHAR NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (source_id)
);

