"""Endpoints del catálogo de paquetes (DFD 2.1 y 5.1/5.2)."""
from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError

from app.auth import solo_admin, usuario_actual
from app.db import sb
from app.schemas import PaqueteIn

router = APIRouter(prefix="/paquetes", tags=["Catálogo"])


@router.get("")
def listar_paquetes(_: dict = Depends(usuario_actual)) -> list[dict]:
    """Lista los paquetes (en lista, sin imágenes)."""
    return sb.table("paquetes_turisticos").select("*").execute().data


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
    except APIError as e:
        print("ERROR POST /paquetes:", e.code, e.message, e.details)
        if e.code == "23505":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ya existe un paquete con ese código")
        if e.code == "23503":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Un id de destino, hotel, vuelo o seguro no existe ({e.details})",
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"No se pudo guardar: {e.message}")


@router.delete("/{paquete_id}")
def eliminar_paquete(paquete_id: int, _: dict = Depends(solo_admin)) -> dict:
    """Elimina un paquete turístico por su ID (solo administrador)."""
    try:
        respuesta = sb.table("paquetes_turisticos").delete().eq("id", paquete_id).execute()
        if not respuesta.data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paquete no encontrado")
    except APIError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, 
            "No se pudo eliminar el paquete. Puede estar asociado a compras existentes."
        )
    return {"detail": "Paquete eliminado correctamente"}
