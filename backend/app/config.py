from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://studease:studease@127.0.0.1:15433/studease"
    test_database_url: str | None = None
    cors_origins: str = "http://localhost:5173"
    seed: int = 20261022


settings = Settings()
