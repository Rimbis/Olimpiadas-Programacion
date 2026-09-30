"""Conexión a Supabase.

- `sb`: cliente con la clave service_role. Lo usa el backend para leer y
  escribir en las tablas (ignora RLS). Nunca se expone al frontend.
- `nuevo_cliente_anon()`: cliente descartable con la clave anon, usado solo
  para el login, así no se contamina la sesión del cliente principal.
"""
from supabase import Client, create_client

from app.config import settings

sb: Client = create_client(settings.supabase_url, settings.supabase_service_key)


def nuevo_cliente_anon() -> Client:
    """Devuelve un cliente nuevo con la clave anon (para iniciar sesión)."""
    return create_client(settings.supabase_url, settings.supabase_anon_key)
