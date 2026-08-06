from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+psycopg://cortex:cortex@localhost:5432/cortex"
    qdrant_url: str = "http://localhost:6333"
    ollama_url: str = "http://localhost:11434"

    llm_model: str = "qwen3:4b"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    qdrant_collection: str = "chunks"

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
    agent_max_steps: int = 4
    agent_top_k: int = 3


settings = Settings()
