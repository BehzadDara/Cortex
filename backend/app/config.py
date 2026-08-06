from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+psycopg://cortex:cortex@localhost:5432/cortex"
    qdrant_url: str = "http://localhost:6333"
    ollama_url: str = "http://localhost:11434"


settings = Settings()
