"""Endpoints de autenticación (DFD 1.0): registro, login y perfil."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import usuario_actual
from app.db import nuevo_cliente_anon, sb
from app.schemas import LoginIn, RegistroIn, TokenOut

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/registro", status_code=status.HTTP_201_CREATED)
def registro(datos: RegistroIn) -> dict:
    """Crea la cuenta en Supabase Auth y el perfil en la tabla `cliente`."""
    try:
        res = sb.auth.admin.create_user(
            {
                "email": datos.email,
                "password": datos.password,
                "email_confirm": True,  # sin mail de confirmación
            }
        )
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo crear la cuenta")

    user_id = res.user.id
    try:
        sb.table("cliente").insert(
            {
                "id": user_id,
                "nombre": datos.nombre,
                "apellido": datos.apellido,
                "email": datos.email,
            }
        ).execute()
    except Exception as e:                                # antes: except Exception:
        print("ERROR INSERT CLIENTE:", repr(e))           # línea nueva, temporal
        sb.auth.admin.delete_user(user_id)  # no dejar cuentas a medias
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Error al crear el perfil")
    return {"mensaje": "Cuenta creada"}


@router.post("/login", response_model=TokenOut)
def login(datos: LoginIn) -> TokenOut:
    """Valida las credenciales con Supabase y devuelve el token y el rol."""
    try:
        res = nuevo_cliente_anon().auth.sign_in_with_password(
            {"email": datos.email, "password": datos.password}
        )
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales incorrectas")

    admin = sb.table("admin").select("rol").eq("id", res.user.id).execute().data
    rol = admin[0]["rol"] if admin else "cliente"
    return TokenOut(access_token=res.session.access_token, rol=rol)


@router.get("/me")
def me(usuario: dict = Depends(usuario_actual)) -> dict:
    """Devuelve los datos básicos del usuario logueado."""
    return usuario
