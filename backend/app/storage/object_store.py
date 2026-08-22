from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from threading import Lock
from typing import Protocol
from urllib.parse import urlparse

from app import settings


class ObjectStore(Protocol):
    def put(self, local_path: str | Path, *, user_id: str, namespace: str, name: str | None = None) -> str: ...
    def materialize(self, uri: str | Path) -> Path: ...
    def delete(self, uri: str | Path) -> None: ...
    def delete_namespace(self, *, user_id: str, namespace: str) -> None: ...
    def usage(self, user_id: str) -> int: ...
    def namespace_usage(self, *, user_id: str, namespace: str) -> int: ...
    def size(self, uri: str | Path) -> int: ...
    def health_check(self) -> None: ...


class LocalObjectStore:
    def put(self, local_path: str | Path, *, user_id: str, namespace: str, name: str | None = None) -> str:
        return str(Path(local_path).resolve())

    def materialize(self, uri: str | Path) -> Path:
        return Path(uri).resolve()

    def delete(self, uri: str | Path) -> None:
        path = Path(uri).resolve()
        if path.is_file():
            path.unlink(missing_ok=True)

    def delete_namespace(self, *, user_id: str, namespace: str) -> None:
        target = (settings.UPLOAD_DIR / namespace).resolve()
        try:
            target.relative_to(settings.UPLOAD_DIR.resolve())
        except ValueError:
            return
        shutil.rmtree(target, ignore_errors=True)

    def usage(self, user_id: str) -> int:
        return 0

    def namespace_usage(self, *, user_id: str, namespace: str) -> int:
        target = (settings.UPLOAD_DIR / namespace).resolve()
        if not target.exists():
            return 0
        return sum(item.stat().st_size for item in target.rglob("*") if item.is_file())

    def size(self, uri: str | Path) -> int:
        path = Path(uri).resolve()
        return path.stat().st_size if path.is_file() else 0

    def health_check(self) -> None:
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        if not os.access(settings.UPLOAD_DIR, os.W_OK):
            raise RuntimeError("Local object storage is not writable")


class S3ObjectStore:
    def __init__(self) -> None:
        import boto3

        self.bucket = settings.S3_BUCKET
        self.prefix = settings.S3_PREFIX
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        )
        self._locks: dict[str, Lock] = {}
        self._locks_guard = Lock()

    def _key(self, user_id: str, namespace: str, name: str) -> str:
        clean_name = Path(name).name
        parts = [part for part in (self.prefix, "users", user_id, namespace, clean_name) if part]
        return "/".join(parts)

    def _prefix(self, user_id: str, namespace: str | None = None) -> str:
        parts = [part for part in (self.prefix, "users", user_id, namespace) if part]
        return "/".join(parts).rstrip("/") + "/"

    def put(self, local_path: str | Path, *, user_id: str, namespace: str, name: str | None = None) -> str:
        source = Path(local_path)
        key = self._key(user_id, namespace, name or source.name)
        self.client.upload_file(str(source), self.bucket, key)
        return f"s3://{self.bucket}/{key}"

    def _parse(self, uri: str | Path) -> tuple[str, str]:
        parsed = urlparse(str(uri))
        if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.lstrip("/"):
            raise ValueError("Invalid S3 object URI")
        if parsed.netloc != self.bucket:
            raise ValueError("Object URI does not belong to the configured bucket")
        return parsed.netloc, parsed.path.lstrip("/")

    def materialize(self, uri: str | Path) -> Path:
        bucket, key = self._parse(uri)
        digest = hashlib.sha256(str(uri).encode("utf-8")).hexdigest()
        target = settings.CACHE_DIR / digest[:2] / digest / Path(key).name
        if target.exists():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._locks_guard:
            lock = self._locks.setdefault(digest, Lock())
        with lock:
            if target.exists():
                return target
            fd, temp_name = tempfile.mkstemp(prefix="object-", dir=target.parent)
            os.close(fd)
            temp_path = Path(temp_name)
            try:
                self.client.download_file(bucket, key, str(temp_path))
                os.replace(temp_path, target)
            finally:
                temp_path.unlink(missing_ok=True)
        return target

    def delete(self, uri: str | Path) -> None:
        bucket, key = self._parse(uri)
        self.client.delete_object(Bucket=bucket, Key=key)

    def delete_namespace(self, *, user_id: str, namespace: str) -> None:
        prefix = self._prefix(user_id, namespace)
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if objects:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})

    def usage(self, user_id: str) -> int:
        total = 0
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self._prefix(user_id)):
            total += sum(int(item.get("Size") or 0) for item in page.get("Contents", []))
        return total

    def namespace_usage(self, *, user_id: str, namespace: str) -> int:
        total = 0
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self._prefix(user_id, namespace)):
            total += sum(int(item.get("Size") or 0) for item in page.get("Contents", []))
        return total

    def size(self, uri: str | Path) -> int:
        bucket, key = self._parse(uri)
        response = self.client.head_object(Bucket=bucket, Key=key)
        return int(response.get("ContentLength") or 0)

    def health_check(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)


_store: ObjectStore | None = None
_store_lock = Lock()


def get_object_store() -> ObjectStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = S3ObjectStore() if settings.OBJECT_STORAGE_BACKEND == "s3" else LocalObjectStore()
        return _store


def reset_object_store() -> None:
    global _store
    with _store_lock:
        _store = None


def persist_file(path: str | Path, *, user_id: str, namespace: str, name: str | None = None) -> str:
    return get_object_store().put(path, user_id=user_id, namespace=namespace, name=name)


def materialize_path(uri: str | Path) -> Path:
    return get_object_store().materialize(uri)


def materialize_record_paths(record: dict) -> dict:
    for field in ("source_path", "working_path"):
        value = record.get(field)
        if not value:
            continue
        record[f"{field.removesuffix('_path')}_uri"] = str(value)
        record[field] = str(materialize_path(value))
    schema = record.get("schema")
    if isinstance(schema, dict):
        source = schema.get("source")
        if isinstance(source, dict):
            nested_source = source.get("source_path")
            if nested_source:
                source["source_uri"] = str(nested_source)
                source["source_path"] = str(materialize_path(nested_source))
            for item in source.get("opendosm_tables", []) or []:
                if not isinstance(item, dict) or not item.get("source_path"):
                    continue
                item["source_uri"] = str(item["source_path"])
                item["source_path"] = str(materialize_path(item["source_path"]))
    return record
