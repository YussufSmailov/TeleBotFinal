from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    student_bot_token: str
    database_url: str
    timezone: str = "Asia/Almaty"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # старые переменные в .env не ломают запуск
    )


settings = Settings()
