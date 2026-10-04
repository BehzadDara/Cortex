import base64
import binascii
import json
import subprocess
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol
from uuid import uuid4

from app.config import settings

CONTAINER_START_SLACK_SECONDS = 20
DOCKER_ERROR_EXIT_CODES = {125, 126, 127}
WORKSPACE_TMPFS_BYTES = 64 * 1024 * 1024
TMP_TMPFS_BYTES = 128 * 1024 * 1024
MAX_PROCESSES = 64
MAX_FILES = 5
MAX_FILE_BYTES = 5_000_000
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".csv", ".json", ".txt"}


@dataclass
class SandboxFile:
    name: str
    data: bytes


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    files: list[SandboxFile]


class SandboxUnavailableError(RuntimeError):
    pass


class CodeSandbox(Protocol):
    def run(self, code: str) -> ExecutionResult: ...


def safe_file(entry: dict) -> SandboxFile | None:
    name = PurePosixPath(str(entry.get("name", ""))).name
    if PurePosixPath(name).suffix.lower() not in ALLOWED_SUFFIXES:
        return None
    try:
        data = base64.b64decode(str(entry.get("data", "")), validate=True)
    except binascii.Error:
        return None
    if len(data) > MAX_FILE_BYTES:
        return None
    return SandboxFile(name=name, data=data)


def parse_report(stdout: bytes) -> ExecutionResult | None:
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(report, dict):
        return None
    entries = report.get("files") if isinstance(report.get("files"), list) else []
    files = [file for file in map(safe_file, entries[:MAX_FILES]) if file]
    return ExecutionResult(
        exit_code=int(report.get("exit_code", 1)),
        stdout=str(report.get("stdout", "")),
        stderr=str(report.get("stderr", "")),
        timed_out=bool(report.get("timed_out", False)),
        files=files,
    )


def timed_out_result() -> ExecutionResult:
    return ExecutionResult(
        exit_code=-1, stdout="", stderr="", timed_out=True, files=[]
    )


def crashed_result(exit_code: int) -> ExecutionResult:
    return ExecutionResult(
        exit_code=exit_code,
        stdout="",
        stderr=(
            f"The sandbox stopped unexpectedly (exit code {exit_code}), "
            "most likely for exceeding its memory limit."
        ),
        timed_out=False,
        files=[],
    )


class DockerCodeSandbox:
    def run(self, code: str) -> ExecutionResult:
        container = f"cortex-sandbox-{uuid4().hex[:12]}"
        try:
            completed = subprocess.run(
                self.command(container),
                input=code.encode(),
                capture_output=True,
                timeout=settings.code_timeout_seconds + CONTAINER_START_SLACK_SECONDS,
            )
        except FileNotFoundError as error:
            raise SandboxUnavailableError("Docker is not installed") from error
        except subprocess.TimeoutExpired:
            self.kill(container)
            return timed_out_result()
        result = parse_report(completed.stdout)
        if result is not None:
            return result
        if completed.returncode in DOCKER_ERROR_EXIT_CODES:
            message = completed.stderr.decode(errors="replace").strip()
            raise SandboxUnavailableError(message or "Docker could not start")
        return crashed_result(completed.returncode)

    def command(self, container: str) -> list[str]:
        return [
            "docker",
            "run",
            "--rm",
            "--interactive",
            "--name",
            container,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(MAX_PROCESSES),
            "--memory",
            f"{settings.code_memory_mb}m",
            "--memory-swap",
            f"{settings.code_memory_mb}m",
            "--cpus",
            str(settings.code_cpus),
            "--mount",
            f"type=tmpfs,destination=/workspace,tmpfs-size={WORKSPACE_TMPFS_BYTES},tmpfs-mode=1777",
            "--mount",
            f"type=tmpfs,destination=/tmp,tmpfs-size={TMP_TMPFS_BYTES},tmpfs-mode=1777",
            settings.code_sandbox_image,
            str(settings.code_timeout_seconds),
        ]

    def kill(self, container: str) -> None:
        subprocess.run(
            ["docker", "kill", container], capture_output=True, check=False
        )
