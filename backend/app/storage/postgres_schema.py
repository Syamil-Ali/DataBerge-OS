from __future__ import annotations

from typing import Any


SCHEMA_SQL = """
create table if not exists users (
    id text primary key,
    email text not null unique,
    name text not null,
    password_hash text not null,
    storage_used bigint not null default 0,
    created_at text not null
);
create table if not exists projects (
    id text primary key,
    user_id text references users(id) on delete cascade,
    name text not null,
    description text,
    created_at text not null,
    updated_at text not null
);
create table if not exists datasets (
    id text primary key,
    user_id text references users(id) on delete cascade,
    project_id text not null references projects(id) on delete cascade,
    name text not null,
    original_filename text not null,
    file_type text not null,
    source_path text not null,
    working_path text not null,
    row_count bigint not null,
    column_count integer not null,
    status text not null,
    profile_json text not null,
    created_at text not null,
    updated_at text not null
);
create table if not exists chat_sessions (
    id text primary key,
    user_id text references users(id) on delete cascade,
    project_id text not null references projects(id) on delete cascade,
    dataset_id text,
    title text not null,
    created_at text not null,
    updated_at text not null
);
create table if not exists chat_messages (
    id text primary key,
    user_id text references users(id) on delete cascade,
    project_id text not null references projects(id) on delete cascade,
    dataset_id text,
    session_id text,
    role text not null,
    content text not null,
    payload_json text not null,
    created_at text not null
);
create table if not exists artifacts (
    id text primary key,
    user_id text references users(id) on delete cascade,
    project_id text not null references projects(id) on delete cascade,
    dataset_id text,
    kind text not null,
    title text not null,
    status text not null,
    payload_json text not null,
    created_at text not null,
    updated_at text not null
);
create table if not exists report_types (
    id text primary key,
    user_id text not null references users(id) on delete cascade,
    project_id text not null references projects(id) on delete cascade,
    dataset_id text not null,
    name text not null,
    description text not null default '',
    payload_json text not null,
    is_default integer not null default 0,
    created_at text not null,
    updated_at text not null
);
create table if not exists relational_schemas (
    id text primary key,
    project_id text not null references projects(id) on delete cascade,
    user_id text references users(id) on delete cascade,
    name text not null,
    original_filename text not null,
    source_path text not null,
    schema_json text not null,
    status text not null default 'draft',
    created_at text not null,
    updated_at text not null
);
create table if not exists background_jobs (
    id text primary key,
    user_id text not null references users(id) on delete cascade,
    queue text not null,
    kind text not null,
    status text not null,
    message text not null default '',
    payload_json text not null default '{}',
    result_json text not null default '{}',
    created_at text not null,
    updated_at text not null
);
create table if not exists schema_migrations (
    version integer primary key,
    name text not null,
    applied_at text not null
);
"""


def initialize_postgres(connection: Any) -> None:
    connection.executescript(SCHEMA_SQL)
