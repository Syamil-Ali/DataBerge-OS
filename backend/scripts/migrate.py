from __future__ import annotations

from app.settings import validate_runtime_config
from app.storage.database import init_db


def main() -> None:
    validate_runtime_config()
    init_db()
    print("Database migrations applied successfully.")


if __name__ == "__main__":
    main()
