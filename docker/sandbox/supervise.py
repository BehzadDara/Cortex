import base64
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path("/workspace")
SCRIPT = WORKSPACE / "main.py"
STDOUT_PATH = Path("/tmp/stdout.txt")
STDERR_PATH = Path("/tmp/stderr.txt")
MATPLOTLIB_CACHE = Path("/opt/matplotlib")
WRITABLE_MATPLOTLIB_CACHE = Path("/tmp/matplotlib")
MAX_STREAM_BYTES = 20_000
MAX_FILES = 5
MAX_FILE_BYTES = 5_000_000
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".csv", ".json", ".txt"}
TRUNCATION_NOTICE = "\n… output truncated"
OUT_OF_MEMORY_NOTICE = "\nThe process was killed, most likely for exceeding the memory limit."


def read_stream(path: Path) -> str:
    with path.open("rb") as stream:
        head = stream.read(MAX_STREAM_BYTES + 1)
    text = head[:MAX_STREAM_BYTES].decode("utf-8", errors="replace")
    return text + TRUNCATION_NOTICE if len(head) > MAX_STREAM_BYTES else text


def child_environment() -> dict[str, str]:
    shutil.copytree(MATPLOTLIB_CACHE, WRITABLE_MATPLOTLIB_CACHE, dirs_exist_ok=True)
    return {**os.environ, "MPLCONFIGDIR": str(WRITABLE_MATPLOTLIB_CACHE)}


def run_child(timeout_seconds: float) -> tuple[int, bool]:
    with STDOUT_PATH.open("wb") as stdout, STDERR_PATH.open("wb") as stderr:
        child = subprocess.Popen(
            [sys.executable, "/sandbox/execute.py"],
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            cwd=WORKSPACE,
            env=child_environment(),
            start_new_session=True,
        )
        try:
            return child.wait(timeout=timeout_seconds), False
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            return child.returncode, True


def collect_files() -> list[dict]:
    files: list[dict] = []
    for path in sorted(WORKSPACE.iterdir()):
        if len(files) >= MAX_FILES:
            break
        if path == SCRIPT or path.is_symlink() or not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        files.append(
            {"name": path.name, "data": base64.b64encode(path.read_bytes()).decode()}
        )
    return files


def main() -> None:
    timeout_seconds = float(sys.argv[1])
    SCRIPT.write_text(sys.stdin.read())
    exit_code, timed_out = run_child(timeout_seconds)
    stderr = read_stream(STDERR_PATH)
    if exit_code == -signal.SIGKILL and not timed_out:
        stderr += OUT_OF_MEMORY_NOTICE
    report = {
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout": read_stream(STDOUT_PATH),
        "stderr": stderr,
        "files": collect_files(),
    }
    sys.stdout.write(json.dumps(report))


if __name__ == "__main__":
    main()
