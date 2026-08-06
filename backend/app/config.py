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


settings = Settings()
