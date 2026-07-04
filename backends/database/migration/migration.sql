BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> ac696a9ca787

CREATE TABLE audit_logs (
    id SERIAL NOT NULL, 
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    method VARCHAR(10) NOT NULL, 
    path VARCHAR(255) NOT NULL, 
    "user" VARCHAR(100), 
    auth_type VARCHAR(50), 
    status_code INTEGER NOT NULL, 
    duration_ms FLOAT NOT NULL, 
    request_metadata JSON, 
    created TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE groups (
    id SERIAL NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    description VARCHAR(255), 
    created TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

CREATE TYPE llmmodelstatus AS ENUM ('NEW', 'PENDING', 'APPROVED', 'DISABLED', 'REJECTED', 'DEPRECATED', 'RETIRED');

CREATE TABLE models (
    id SERIAL NOT NULL, 
    url VARCHAR(255) NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    technical_name VARCHAR(100) NOT NULL, 
    provider VARCHAR(100) NOT NULL, 
    status llmmodelstatus NOT NULL, 
    created TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated TIMESTAMP WITH TIME ZONE NOT NULL, 
    capabilities JSON NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_name_technical_name UNIQUE (name, technical_name)
);

CREATE TABLE token_usages (
    id SERIAL NOT NULL, 
    user_id VARCHAR(255) NOT NULL, 
    model VARCHAR(255) NOT NULL, 
    prompt_tokens INTEGER NOT NULL, 
    completion_tokens INTEGER NOT NULL, 
    total_tokens INTEGER NOT NULL, 
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    request_id VARCHAR(36), 
    endpoint VARCHAR(255) NOT NULL, 
    created TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_token_usages_model ON token_usages (model);

CREATE INDEX ix_token_usages_user_id ON token_usages (user_id);

CREATE TABLE users (
    id VARCHAR(36) NOT NULL, 
    username VARCHAR(100) NOT NULL, 
    email VARCHAR(255), 
    is_active BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    created TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_username ON users (username);

CREATE TABLE api_keys (
    id VARCHAR(36) NOT NULL, 
    key_hash VARCHAR(255) NOT NULL, 
    name VARCHAR(100), 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITHOUT TIME ZONE, 
    is_active BOOLEAN NOT NULL, 
    last_used_at TIMESTAMP WITHOUT TIME ZONE, 
    created TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE UNIQUE INDEX ix_api_keys_key_hash ON api_keys (key_hash);

CREATE TABLE model_authorization (
    group_id INTEGER NOT NULL, 
    model_id INTEGER NOT NULL, 
    PRIMARY KEY (group_id, model_id), 
    FOREIGN KEY(group_id) REFERENCES groups (id), 
    FOREIGN KEY(model_id) REFERENCES models (id)
);

CREATE TABLE user_group_association (
    user_id VARCHAR(36) NOT NULL, 
    group_id INTEGER NOT NULL, 
    PRIMARY KEY (user_id, group_id), 
    FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

INSERT INTO alembic_version (version_num) VALUES ('ac696a9ca787') RETURNING alembic_version.version_num;

COMMIT;

