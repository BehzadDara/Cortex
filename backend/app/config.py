from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+psycopg://cortex:cortex@localhost:5442/cortex"
    qdrant_url: str = "http://localhost:6333"
    ollama_url: str = "http://localhost:11434"

    llm_model: str = "qwen3:4b"
    fast_llm_model: str = "gemma3:4b"
    vision_model: str = "gemma3:4b"
    image_size: int = 768
    image_dir: str = str(BACKEND_ROOT / "generated_images")
    knowledge_image_dir: str = str(BACKEND_ROOT / "knowledge_images")
    max_images_per_document: int = 8
    max_image_bytes: int = 8_000_000
    min_image_dimension: int = 128
    crawl_max_images_per_page: int = 4
    image_top_k: int = 3
    image_min_relevance: float = 0.0
    web_image_results: int = 8
    ocr_max_pages: int = 5
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    qdrant_collection: str = "chunks"
    qdrant_image_collection: str = "images"

    chunk_size: int = 1000
    chunk_overlap: int = 200
    code_chunk_lines: int = 60
    code_chunk_overlap_lines: int = 10
    top_k: int = 5
    hybrid_search: bool = True
    rerank: bool = True
    rerank_candidates: int = 30
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    memory_recent_messages: int = 6
    memory_summary_threshold: int = 4
    chat_max_rounds: int = 5
    llm_num_ctx: int = 16384
    agent_min_relevance: float = 0.0
    web_search_results: int = 5


settings = Settings()
