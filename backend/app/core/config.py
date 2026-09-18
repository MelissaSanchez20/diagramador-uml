from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Diagramador UML"
    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174"

    # CU11 — interpretación de comandos de voz vía function calling. Opcional
    # (no requerida al arrancar) para no romper `pytest`/entornos sin la key
    # configurada todavía -- `app/services/comandos_voz.py` valida que esté
    # presente recién al momento de llamar a la API, con un error claro.
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origen.strip() for origen in self.CORS_ORIGINS.split(",") if origen.strip()]


settings = Settings()
