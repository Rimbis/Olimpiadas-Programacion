"""Configuración de la aplicación, leída desde variables de entorno (.env)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent  # carpeta que contiene app/


class Settings(BaseSettings):
    """Variables de entorno de la aplicación.

    Obligatorias: las tres de Supabase. El resto es opcional: sin
    `MP_ACCESS_TOKEN` el pago funciona en modo simulado, y sin `SMTP_USER`
    los mails se registran en la tabla `mails` como "simulado".
    """

    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    # Mercado Pago (access token de prueba) y URL pública de la app.
    mp_access_token: str = ""
    base_url: str = "http://localhost:8000"

    # Envío de mails por SMTP (Gmail: contraseña de aplicación).
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    model_config = SettingsConfigDict(
        env_file=RAIZ / ".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
