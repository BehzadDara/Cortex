import tempfile
from dataclasses import dataclass
from pathlib import Path

from git import Repo

INDEXABLE_SUFFIXES = {
    ".md",
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".yml",
    ".yaml",
    ".toml",
}
SKIPPED_DIRECTORIES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
}
MAX_FILE_BYTES = 100_000


@dataclass
class RepositoryFile:
    path: str
    text: str


def repository_name(url: str) -> str:
    return url.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1]


def indexable(path: Path) -> bool:
    if any(part in SKIPPED_DIRECTORIES for part in path.parts):
        return False
    if path.suffix.lower() not in INDEXABLE_SUFFIXES:
        return False
    return path.stat().st_size <= MAX_FILE_BYTES


def collect_files(url: str) -> list[RepositoryFile]:
    name = repository_name(url)
    files: list[RepositoryFile] = []
    with tempfile.TemporaryDirectory() as directory:
        Repo.clone_from(url, directory, depth=1)
        root = Path(directory)
        for path in sorted(root.rglob("*")):
            if not path.is_file() or not indexable(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if text.strip():
                relative = path.relative_to(root)
                files.append(RepositoryFile(path=f"{name}/{relative}", text=text))
    return files
