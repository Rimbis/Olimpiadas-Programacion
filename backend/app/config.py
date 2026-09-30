"""Configuración de la aplicación, leída desde variables de entorno (.env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno necesarias para conectarse a Supabase."""

    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
