from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app import settings
from app.auth.security import get_current_user
from app.connectors.contracts import ConnectorError
from app.connectors.secrets import encrypt_connector_secret
from app.services.federated import (
    connection_runtime,
    public_connection,
    register_federated_dataset,
    serialize_query_result,
)
from app.storage import database

router = APIRouter(tags=["connections"])


class ConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: Literal["supabase", "postgresql"] = "supabase"
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(default="postgres", min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=2048)
    sslmode: Literal["require", "verify-ca", "verify-full"] = "require"

    @field_validator("host")
    @classmethod
    def plain_hostname(cls, value: str) -> str:
        host = value.strip()
        if "://" in host or "/" in host or "@" in host:
            raise ValueError("Enter only the database hostname, without a URL or credentials")
        return host


class FederatedDatasetCreate(BaseModel):
    connection_id: str = Field(min_length=1, max_length=64)
    schema_name: str = Field(min_length=1, max_length=128)
    table_name: str = Field(min_length=1, max_length=128)
    name: str | None = Field(default=None, max_length=120)


class FederatedQueryRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=12000)
    limit: int = Field(default=100, ge=1, le=settings.FEDERATED_MAX_RESULT_ROWS)


def _project(user_id: str, project_id: str) -> None:
    if not database.get_project_for_user(user_id, project_id):
        raise HTTPException(status_code=404, detail="Project not found")


def _runtime(user_id: str, project_id: str, connection_id: str):
    try:
        return connection_runtime(user_id, project_id, connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/connectors")
def connector_catalog(user: dict = Depends(get_current_user)):
    return [{
        "provider": "supabase",
        "connector_type": "postgresql",
        "name": "Supabase",
        "access_mode": "federated",
        "capabilities": ["schema_discovery", "table_discovery", "preview", "query"],
    }]


@router.post("/projects/{project_id}/connections", status_code=201)
def create_connection(project_id: str, payload: ConnectionCreate, user: dict = Depends(get_current_user)):
    _project(user["id"], project_id)
    if settings.IS_PRODUCTION and not settings.CONNECTOR_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Database connectors require CONNECTOR_SECRET_KEY to be configured.",
        )
    config = payload.model_dump(exclude={"name", "provider", "password"})
    record = database.create_data_connection(
        user["id"],
        project_id,
        name=payload.name,
        provider=payload.provider,
        connector_type="postgresql",
        config=config,
        encrypted_secret=encrypt_connector_secret({"password": payload.password}),
    )
    return public_connection(record)


@router.get("/projects/{project_id}/connections")
def list_connections(project_id: str, user: dict = Depends(get_current_user)):
    _project(user["id"], project_id)
    return database.list_data_connections(user["id"], project_id)


@router.delete("/projects/{project_id}/connections/{connection_id}")
def delete_connection(project_id: str, connection_id: str, user: dict = Depends(get_current_user)):
    _project(user["id"], project_id)
    try:
        deleted = database.delete_data_connection(user["id"], project_id, connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"deleted": True, "connection_id": connection_id}


@router.post("/projects/{project_id}/connections/{connection_id}/test")
def test_connection(project_id: str, connection_id: str, user: dict = Depends(get_current_user)):
    connection, connector, secret = _runtime(user["id"], project_id, connection_id)
    try:
        result = connector.test_connection(connection["config"], secret)
    except ConnectorError as exc:
        database.update_data_connection_status(user["id"], project_id, connection_id, status="failed", tested=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    database.update_data_connection_status(user["id"], project_id, connection_id, status="connected", tested=True)
    return result


@router.get("/projects/{project_id}/connections/{connection_id}/schemas")
def discover_schemas(project_id: str, connection_id: str, user: dict = Depends(get_current_user)):
    connection, connector, secret = _runtime(user["id"], project_id, connection_id)
    try:
        return connector.discover_schemas(connection["config"], secret)
    except ConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{project_id}/connections/{connection_id}/tables")
def discover_tables(
    project_id: str,
    connection_id: str,
    schema: str = Query(min_length=1, max_length=128),
    user: dict = Depends(get_current_user),
):
    connection, connector, secret = _runtime(user["id"], project_id, connection_id)
    try:
        return connector.discover_tables(connection["config"], secret, schema)
    except ConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{project_id}/connections/{connection_id}/preview")
def preview_table(
    project_id: str,
    connection_id: str,
    schema: str = Query(min_length=1, max_length=128),
    table: str = Query(min_length=1, max_length=128),
    limit: int = Query(default=50, ge=1, le=settings.FEDERATED_MAX_RESULT_ROWS),
    user: dict = Depends(get_current_user),
):
    connection, connector, secret = _runtime(user["id"], project_id, connection_id)
    try:
        return serialize_query_result(connector.preview(connection["config"], secret, schema, table, limit))
    except ConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/federated-datasets", status_code=201)
def create_federated_dataset(
    project_id: str,
    payload: FederatedDatasetCreate,
    user: dict = Depends(get_current_user),
):
    _project(user["id"], project_id)
    try:
        return register_federated_dataset(
            user["id"],
            project_id,
            connection_id=payload.connection_id,
            schema=payload.schema_name,
            table=payload.table_name,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/datasets/{dataset_id}/federated-query")
def query_federated_dataset(
    project_id: str,
    dataset_id: str,
    payload: FederatedQueryRequest,
    user: dict = Depends(get_current_user),
):
    from app.services.federated import execute_dataset_sql

    if not database.get_dataset_for_user(user["id"], project_id, dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found")
    try:
        return serialize_query_result(execute_dataset_sql(
            user["id"], project_id, dataset_id, payload.sql, payload.limit,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
