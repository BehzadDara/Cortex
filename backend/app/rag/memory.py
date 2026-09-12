import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

os.environ.setdefault("MEM0_TELEMETRY", "False")

from mem0 import Memory as Mem0Memory
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings
from app.rag.llm import LLMProvider
from app.rag.prompts import build_memory_prompt, build_supersede_prompt

FACT_PREFIX = "The user"

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

STATEMENT_OPENERS = ("i ", "i'm ", "i've ", "my ", "we ", "we're ")

VAGUE_WORDS = {
    "anything",
    "anywhere",
    "someone",
    "somehow",
    "something",
    "somewhere",
    "stuff",
    "things",
}


@dataclass
class Memory:
    id: str
    text: str
    created_at: str | None = None


class MemoryStore(Protocol):
    def remember(self, message: str, source: dict) -> list[str]: ...

    def recall(self, query: str) -> list[Memory]: ...

    def all(self) -> list[Memory]: ...

    def forget(self, memory_id: str) -> None: ...


def asks_without_telling(message: str) -> bool:
    sentences = [part.strip() for part in SENTENCE_END.split(message) if part.strip()]
    if not sentences or not all(sentence.endswith("?") for sentence in sentences):
        return False
    return not any(
        sentence.lower().startswith(STATEMENT_OPENERS) for sentence in sentences
    )


def names_something_specific(fact: str) -> bool:
    words = {word.strip(".,!?;:'\"").lower() for word in fact.split()}
    return not words & VAGUE_WORDS


def extract_facts(llm: LLMProvider, message: str) -> list[str]:
    if asks_without_telling(message):
        return []
    reply = llm.complete(build_memory_prompt(message))
    facts = [line.strip() for line in reply.splitlines()]
    return [
        fact
        for fact in facts
        if fact.startswith(FACT_PREFIX) and names_something_specific(fact)
    ]


def qdrant_location() -> dict:
    parsed = urlparse(settings.qdrant_url)
    return {"host": parsed.hostname, "port": parsed.port}


def to_memory(result: dict) -> Memory:
    return Memory(
        id=result["id"],
        text=result["memory"],
        created_at=result.get("created_at"),
    )


class Mem0MemoryStore:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm
        self.user_id = settings.user_memory_id
        Path(settings.user_memory_history_path).parent.mkdir(
            parents=True, exist_ok=True
        )
        self.memory = Mem0Memory.from_config(
            {
                "llm": {
                    "provider": "ollama",
                    "config": {
                        "model": settings.fast_llm_model,
                        "ollama_base_url": settings.ollama_url,
                    },
                },
                "embedder": {
                    "provider": "ollama",
                    "config": {
                        "model": settings.embedding_model,
                        "embedding_dims": settings.embedding_dimensions,
                        "ollama_base_url": settings.ollama_url,
                    },
                },
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "collection_name": settings.qdrant_memory_collection,
                        "embedding_model_dims": settings.embedding_dimensions,
                        **qdrant_location(),
                    },
                },
                "history_db_path": settings.user_memory_history_path,
            }
        )

    def remember(self, message: str, source: dict) -> list[str]:
        stored = []
        for fact in extract_facts(self.llm, message):
            if self.already_known(fact):
                continue
            for memory_id in self.superseded_ids(fact):
                self.forget(memory_id)
            self.memory.add(
                [{"role": "user", "content": fact}],
                user_id=self.user_id,
                metadata=source,
                infer=False,
            )
            stored.append(fact)
        return stored

    def already_known(self, fact: str) -> bool:
        hits = self.search(fact, limit=1)
        return bool(hits) and hits[0]["score"] >= settings.user_memory_duplicate_score

    def superseded_ids(self, fact: str) -> list[str]:
        related = self.search(fact, limit=settings.user_memory_conflict_candidates)
        return [
            hit["id"]
            for hit in related
            if hit["score"] >= settings.user_memory_conflict_score
            and self.supersedes(fact, hit["memory"])
        ]

    def supersedes(self, fact: str, stored: str) -> bool:
        decision = self.llm.complete(build_supersede_prompt(stored, fact))
        return decision.strip().lower().startswith("yes")

    def search(self, query: str, limit: int) -> list[dict]:
        return self.memory.search(
            query, filters={"user_id": self.user_id}, top_k=limit
        )["results"]

    def recall(self, query: str) -> list[Memory]:
        found = self.search(query, limit=settings.user_memory_top_k)
        return [to_memory(result) for result in found]

    def all(self) -> list[Memory]:
        found = self.memory.get_all(
            filters={"user_id": self.user_id}, top_k=settings.user_memory_list_limit
        )["results"]
        return [to_memory(result) for result in found]

    def forget(self, memory_id: str) -> None:
        try:
            self.memory.delete(memory_id)
        except (ValueError, UnexpectedResponse):
            raise LookupError(memory_id)


class DisabledMemoryStore:
    def remember(self, message: str, source: dict) -> list[str]:
        return []

    def recall(self, query: str) -> list[Memory]:
        return []

    def all(self) -> list[Memory]:
        return []

    def forget(self, memory_id: str) -> None:
        raise LookupError(memory_id)


def recall_quietly(store: MemoryStore, query: str) -> list[str]:
    try:
        return [memory.text for memory in store.recall(query)]
    except Exception:
        return []


def remember_quietly(store: MemoryStore, message: str, source: dict) -> None:
    try:
        store.remember(message, source)
    except Exception:
        return None
