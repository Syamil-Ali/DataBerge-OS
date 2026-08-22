from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.settings import DB_PATH


def integrity(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    with sqlite3.connect(path) as conn:
        return str(conn.execute("pragma integrity_check").fetchone()[0])


def backup(source: Path, destination: Path) -> Path:
    source = source.resolve()
    destination = destination.resolve()
    if source == destination:
        raise ValueError("Source and destination must be different files")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)
    result = integrity(destination)
    if result != "ok":
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Backup integrity check failed: {result}")
    return destination


def restore(source: Path, destination: Path, confirmed: bool) -> tuple[Path, Path | None]:
    if not confirmed:
        raise ValueError("Restore requires --confirm after the application has been stopped")
    source = source.resolve()
    destination = destination.resolve()
    result = integrity(source)
    if result != "ok":
        raise RuntimeError(f"Refusing to restore an invalid backup: {result}")
    safety_backup: Path | None = None
    if destination.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safety_backup = destination.with_name(f"{destination.stem}.pre-restore-{timestamp}{destination.suffix}")
        backup(destination, safety_backup)
    backup(source, destination)
    return destination, safety_backup


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Back up, verify, or restore the Data-Berge SQLite database.")
    commands = result.add_subparsers(dest="command", required=True)
    backup_cmd = commands.add_parser("backup")
    backup_cmd.add_argument("--source", type=Path, default=DB_PATH)
    backup_cmd.add_argument("--output", type=Path)
    verify_cmd = commands.add_parser("verify")
    verify_cmd.add_argument("path", type=Path)
    restore_cmd = commands.add_parser("restore")
    restore_cmd.add_argument("backup", type=Path)
    restore_cmd.add_argument("--destination", type=Path, default=DB_PATH)
    restore_cmd.add_argument("--confirm", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "verify":
        print(f"integrity={integrity(args.path.resolve())}")
        return 0
    if args.command == "backup":
        output = args.output
        if output is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            output = DB_PATH.parent / "backups" / f"app-{timestamp}.db"
        print(f"backup={backup(args.source, output)}")
        return 0
    restored, safety = restore(args.backup, args.destination, args.confirm)
    print(f"restored={restored}")
    if safety:
        print(f"safety_backup={safety}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
