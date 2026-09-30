"""Endpoints de administración: alta de personal interno."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import usuario_actual
from app.db import sb
from app.schemas import AdminIn

router = APIRouter(prefix="/admin", tags=["Administración"])


def solo_jefe_ventas(usuario: dict = Depends(usuario_actual)) -> dict:
    """Permite el acceso solo al jefe de ventas."""
    if usuario["rol"] != "jefe_ventas":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo para el jefe de ventas")
    return usuario


@router.post("/usuarios", status_code=status.HTTP_201_CREATED)
def crear_admin(datos: AdminIn, _: dict = Depends(solo_jefe_ventas)) -> dict:
    """Crea la cuenta en Supabase Auth y la registra en la tabla `admin`."""
    try:
        res = sb.auth.admin.create_user(
            {
                "email": datos.email,
                "password": datos.password,
                "email_confirm": True,  # sin mail de confirmación
            }
        )
    except Exception:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "No se pudo crear la cuenta (¿email ya registrado?)"
        )

    user_id = res.user.id
    try:
        sb.table("admin").insert(
            {
                "id": user_id,
                "nombre": datos.nombre,
                "apellido": datos.apellido,
                "email": datos.email,
                "rol": datos.rol,
            }
        ).execute()
    except Exception as e:
        print("ERROR INSERT ADMIN:", e)
        sb.auth.admin.delete_user(user_id)  # no dejar cuentas a medias
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Error al registrar el admin"
        )
    return {"mensaje": "Admin creado", "id": user_id, "rol": datos.rol}