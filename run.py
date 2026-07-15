from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
BACKEND_VENV_PYTHON = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def require_port_available(port: int, label: str) -> None:
    if is_port_in_use(port):
        raise SystemExit(
            f"{label} port {port} is already in use. "
            f"Stop the existing service first or rerun with a different port."
        )


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"{label} not found: {path}")


def start_process(
    name: str,
    cmd: list[str],
    cwd: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen[str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    print(f"[start] {name}: {' '.join(cmd)}")
    return subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        creationflags=creationflags,
    )


def stop_process(name: str, proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    print(f"[stop] {name}")
    try:
        if os.name == "nt":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            time.sleep(1.5)
        else:
            proc.terminate()
            time.sleep(1.0)
    except Exception:
        pass
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                proc.kill()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start the Data-Berge OS backend and frontend."
    )
    parser.add_argument("--backend-port", type=int, default=int(os.getenv("BACKEND_PORT", "8000")))
    parser.add_argument("--frontend-port", type=int, default=int(os.getenv("FRONTEND_PORT", "5173")))
    parser.add_argument("--mlflow-port", type=int, default=int(os.getenv("MLFLOW_PORT", "5000")))
    parser.add_argument("--backend-host", default=os.getenv("BACKEND_HOST", "0.0.0.0"))
    parser.add_argument("--frontend-host", default=os.getenv("FRONTEND_HOST", "0.0.0.0"))
    parser.add_argument("--mlflow-host", default=os.getenv("MLFLOW_HOST", "127.0.0.1"))
    parser.add_argument(
        "--with-mlflow",
        action="store_true",
        default=os.getenv("START_MLFLOW", "false").lower() in {"1", "true", "yes", "on"},
        help="Also start the local MLflow tracking server.",
    )
    parser.add_argument(
        "--skip-mlflow",
        action="store_true",
        help="Deprecated compatibility flag. MLflow is skipped by default.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    start_mlflow = bool(args.with_mlflow and not args.skip_mlflow)

    require_file(BACKEND_VENV_PYTHON, "Backend virtualenv Python")
    require_file(FRONTEND_DIR / "package.json", "Frontend package.json")

    require_port_available(args.backend_port, "Backend")
    require_port_available(args.frontend_port, "Frontend")
    if start_mlflow:
        require_port_available(args.mlflow_port, "MLflow")

    mlflow_db = (ROOT / "data" / "mlflow.db").resolve()
    mlruns_dir = (ROOT / "data" / "mlruns").resolve()
    mlruns_dir.mkdir(parents=True, exist_ok=True)

    processes: list[tuple[str, subprocess.Popen[str]]] = []
    try:
        if start_mlflow:
            processes.append(
                (
                    "mlflow",
                    start_process(
                        "mlflow",
                        [
                            str(BACKEND_VENV_PYTHON),
                            "-m",
                            "mlflow",
                            "server",
                            "--host",
                            args.mlflow_host,
                            "--port",
                            str(args.mlflow_port),
                            "--backend-store-uri",
                            f"sqlite:///{mlflow_db.as_posix()}",
                            "--default-artifact-root",
                            mlruns_dir.as_posix(),
                        ],
                        ROOT,
                    ),
                )
            )

        backend_env = {"PORT": str(args.backend_port)}
        if start_mlflow:
            backend_env["MLFLOW_TRACKING_URI"] = f"http://{args.mlflow_host}:{args.mlflow_port}"
            backend_env["MLFLOW_TRACKING_ENABLED"] = "true"

        processes.append(
            (
                "backend",
                start_process(
                    "backend",
                    [str(BACKEND_VENV_PYTHON), "run.py"],
                    BACKEND_DIR,
                    extra_env=backend_env,
                ),
            )
        )

        processes.append(
            (
                "frontend",
                start_process(
                    "frontend",
                    ["npm.cmd", "run", "dev", "--", "--host", args.frontend_host, "--port", str(args.frontend_port)],
                    FRONTEND_DIR,
                    extra_env={"VITE_API_PROXY_TARGET": f"http://127.0.0.1:{args.backend_port}"},
                ),
            )
        )

        print()
        print("Data-Berge OS is starting up:")
        print(f"- Backend:  http://127.0.0.1:{args.backend_port}")
        print(f"- Frontend: http://127.0.0.1:{args.frontend_port}")
        if start_mlflow:
            print(f"- MLflow:   http://{args.mlflow_host}:{args.mlflow_port}")
        else:
            print("- MLflow:   skipped (use --with-mlflow to enable tracking)")
        print()
        print("Press Ctrl+C once to stop everything.")

        while True:
            for name, proc in processes:
                code = proc.poll()
                if code is not None:
                    raise SystemExit(f"{name} exited early with code {code}.")
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nReceived Ctrl+C. Stopping services...")
    finally:
        for name, proc in reversed(processes):
            stop_process(name, proc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
