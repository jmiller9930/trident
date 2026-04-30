from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRIDENT_", env_file=".env", extra="ignore")

    env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    db_host: str = "trident-db"
    db_port: int = 5432
    vector_host: str = "trident-vector"
    vector_port: int = 8001


settings = Settings()
