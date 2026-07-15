from __future__ import annotations

import argparse
import os

import uvicorn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the Data-Berge OS backend.")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("BACKEND_RELOAD", "false").lower() in {"1", "true", "yes", "on"},
        help="Enable Uvicorn's file watcher. Disabled by default on Windows for stable shutdown.",
    )
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)
