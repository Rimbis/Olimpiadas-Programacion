"""Validación del token de Supabase Auth y control de roles.

El frontend envía el header `Authorization: Bearer <token>`. Acá se valida el
token con Supabase y se determina si el usuario es cliente o admin.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import sb

bearer = HTTPBearer()


def usuario_actual(
    cred: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    """Devuelve {'id', 'email', 'rol'} del usuario dueño del token.

    El rol es 'cliente', 'ventas' o 'jefe_ventas'. Lanza 401 si el token
    es inválido o el usuario no tiene perfil.
    """
    try:
        user = sb.auth.get_user(cred.credentials).user
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")

    admin = sb.table("admin").select("rol").eq("id", user.id).execute().data
    if admin:
        return {"id": user.id, "email": user.email, "rol": admin[0]["rol"]}

    cliente = sb.table("cliente").select("id").eq("id", user.id).execute().data
    if cliente:
        return {"id": user.id, "email": user.email, "rol": "cliente"}

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario sin perfil")


def solo_cliente(usuario: dict = Depends(usuario_actual)) -> dict:
    """Permite el acceso solo a clientes."""
    if usuario["rol"] != "cliente":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo para clientes")
    return usuario


def solo_admin(usuario: dict = Depends(usuario_actual)) -> dict:
    """Permite el acceso solo al personal interno (ventas y jefe de ventas)."""
    if usuario["rol"] not in ("ventas", "jefe_ventas"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo para personal interno")
    return usuario
