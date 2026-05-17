from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"


settings = Settings()
