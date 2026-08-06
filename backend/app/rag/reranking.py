from typing import Protocol

from app.config import settings


class Reranker(Protocol):
    def rerank(self, question: str, texts: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(self) -> None:
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(settings.reranker_model)

    def rerank(self, question: str, texts: list[str]) -> list[float]:
        pairs = [(question, text) for text in texts]
        return self.model.predict(pairs).tolist()
