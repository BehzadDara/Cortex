from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.rag.embeddings import EmbeddingProvider, OllamaEmbeddingProvider
from app.rag.file_store import DiskFileStore, FileStore
from app.rag.image_generation import ImageGenerator, PollinationsImageGenerator
from app.rag.llm import LLMProvider, OllamaLLMProvider
from app.rag.market_data import CoinGeckoMarketData, MarketDataProvider
from app.rag.reranking import CrossEncoderReranker, Reranker
from app.rag.speech import KokoroTextToSpeech, TextToSpeech
from app.rag.transcription import SpeechToText, WhisperSpeechToText
from app.rag.vector_store import QdrantVectorStore, VectorStore
from app.rag.vision import OllamaVisionProvider, VisionProvider
from app.rag.weather import OpenMeteoWeather, WeatherProvider
from app.rag.web_search import (
    DdgsImageSearch,
    DdgsVideoSearch,
    DdgsWebSearch,
    ImageSearchProvider,
    VideoSearchProvider,
    WebSearchProvider,
)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return OllamaEmbeddingProvider()


@lru_cache
def get_llm_provider() -> LLMProvider:
    return OllamaLLMProvider()


@lru_cache
def get_fast_llm_provider() -> LLMProvider:
    return OllamaLLMProvider(model=settings.fast_llm_model, think=False)


@lru_cache
def get_vector_store() -> VectorStore:
    return QdrantVectorStore()


@lru_cache
def get_image_vector_store() -> VectorStore:
    return QdrantVectorStore(collection=settings.qdrant_image_collection)


@lru_cache
def get_generated_image_store() -> FileStore:
    return DiskFileStore(settings.image_dir)


@lru_cache
def get_knowledge_image_store() -> FileStore:
    return DiskFileStore(settings.knowledge_image_dir)


@lru_cache
def get_chat_image_store() -> FileStore:
    return DiskFileStore(settings.chat_image_dir)


@lru_cache
def get_reranker() -> Reranker:
    return CrossEncoderReranker()


@lru_cache
def get_vision_provider() -> VisionProvider:
    return OllamaVisionProvider()


@lru_cache
def get_image_generator() -> ImageGenerator:
    return PollinationsImageGenerator()


@lru_cache
def get_web_search() -> WebSearchProvider:
    return DdgsWebSearch()


@lru_cache
def get_image_search() -> ImageSearchProvider:
    return DdgsImageSearch()


@lru_cache
def get_video_search() -> VideoSearchProvider:
    return DdgsVideoSearch()


@lru_cache
def get_speech_to_text() -> SpeechToText:
    return WhisperSpeechToText()


@lru_cache
def get_text_to_speech() -> TextToSpeech:
    return KokoroTextToSpeech()


@lru_cache
def get_weather_provider() -> WeatherProvider:
    return OpenMeteoWeather()


@lru_cache
def get_market_data_provider() -> MarketDataProvider:
    return CoinGeckoMarketData()
