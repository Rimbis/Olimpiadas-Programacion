"""Endpoints del catálogo de paquetes (DFD 2.1 y 5.1/5.2)."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import solo_admin, usuario_actual
from app.db import sb
from app.schemas import PaqueteIn

router = APIRouter(prefix="/paquetes", tags=["Catálogo"])


@router.get("")
def listar_paquetes(_: dict = Depends(usuario_actual)) -> list[dict]:
    """Lista los paquetes activos (en lista, sin imágenes)."""
    return sb.table("paquetes_turisticos").select("*").eq("activo", True).execute().data


@router.get("/{paquete_id}")
def obtener_paquete(paquete_id: int, _: dict = Depends(usuario_actual)) -> dict:
    """Devuelve un paquete por id."""
    data = sb.table("paquetes_turisticos").select("*").eq("id", paquete_id).execute().data
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paquete no encontrado")
    return data[0]


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_paquete(paquete: PaqueteIn, _: dict = Depends(solo_admin)) -> dict:
    """Carga un paquete nuevo (solo personal interno)."""
    datos = paquete.model_dump(mode="json")
    try:
        return sb.table("paquetes_turisticos").insert(datos).execute().data[0]
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo guardar (¿código repetido?)")
