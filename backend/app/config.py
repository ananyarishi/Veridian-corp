from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "veridian_it_agent"
    jwt_secret_key: str = "development-only-change-me"
    jwt_expire_minutes: int = 480
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    seed_on_start: bool = True
    demo_admin_username: str = "admin"
    demo_admin_password: str = "ChangeMe123!"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
