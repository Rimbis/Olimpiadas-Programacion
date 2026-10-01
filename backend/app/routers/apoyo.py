"""Endpoints de apoyo para el frontend: listados para los formularios y
asientos ocupados de un vuelo (DFD 2.4)."""
from fastapi import APIRouter, Depends

from app.auth import usuario_actual
from app.db import sb

router = APIRouter(prefix="/catalogo", tags=["Apoyo front"])


@router.get("/ubicaciones-destino")
def ubicaciones_destino(_: dict = Depends(usuario_actual)) -> list[dict]:
    """Ciudades de destino/hospedaje (para el formulario de paquetes)."""
    return sb.table("ubicacion_destino").select("*").order("ciudad").execute().data


@router.get("/aeropuertos")
def aeropuertos(_: dict = Depends(usuario_actual)) -> list[dict]:
    """Aeropuertos (origen y destino de los vuelos)."""
    return sb.table("ubicacion_aeropuerto").select("*").order("ciudad").execute().data


@router.get("/hoteles")
def hoteles(_: dict = Depends(usuario_actual)) -> list[dict]:
    """Hoteles disponibles."""
    return sb.table("hoteles").select("*").order("nombre_hotel").execute().data


@router.get("/vuelos")
def vuelos(_: dict = Depends(usuario_actual)) -> list[dict]:
    """Vuelos disponibles."""
    return sb.table("vuelos").select("*").order("fecha_ida").execute().data


@router.get("/seguros")
def seguros(_: dict = Depends(usuario_actual)) -> list[dict]:
    """Seguros médicos disponibles."""
    return sb.table("seguro_medico").select("*").order("nombre").execute().data


@router.get("/vuelos/{vuelo_id}/asientos-ocupados")
def asientos_ocupados(vuelo_id: int, _: dict = Depends(usuario_actual)) -> list[dict]:
    """Asientos ya reservados de un vuelo, como [{'fila': 3, 'letra': 'B'}, ...]."""
    return sb.table("asiento").select("fila, letra").eq("id_vuelo", vuelo_id).execute().data