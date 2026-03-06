from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    openai_api_key_embedding: str = "local"
    embedding_api_url: str = "http://host.docker.internal:8080/v1"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    llm_api_url: str = "http://host.docker.internal:8081/v1"
    llm_api_key: str = "local"
    llm_model: str = "llama-2-7b-chat"

    model_config = SettingsConfigDict()

settings = Settings()
