from pathlib import Path
from typing import Protocol
from uuid import uuid4


class FileStore(Protocol):
    def save(self, data: bytes, extension: str) -> str: ...

    def delete(self, filename: str) -> None: ...


class DiskFileStore:
    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)

    def save(self, data: bytes, extension: str) -> str:
        filename = f"{uuid4().hex}.{extension}"
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / filename).write_bytes(data)
        return filename

    def delete(self, filename: str) -> None:
        (self.directory / filename).unlink(missing_ok=True)
