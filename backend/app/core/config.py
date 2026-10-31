from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    readonly_database_url: str | None = None
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "support_docs"

    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_model_fast: str = "deepseek-chat"
    llm_model_thorough: str = "deepseek-chat"
    llm_price_in_per_m: float = 0.0
    llm_price_out_per_m: float = 0.0
    use_mock_llm: bool = False

    embed_model: str = "BAAI/bge-m3"
    embed_dim: int = 1024
    embed_query_prefix: str = ""
    rerank_model: str = "BAAI/bge-reranker-v2-m3"


@lru_cache
def get_settings() -> Settings:
    return Settings()

