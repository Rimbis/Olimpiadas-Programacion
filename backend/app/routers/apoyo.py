"""Endpoints de apoyo para el frontend: listados para los formularios,
asientos ocupados de un vuelo (DFD 2.4) y alta/baja de ubicaciones destino,
aeropuertos, hoteles, seguros médicos y vuelos con sus escalas (DFD 5.1,
solo personal interno)."""
from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError

from app.auth import solo_admin, usuario_actual
from app.db import sb
from app.schemas import (
    AeropuertoIn, EscalasIn, HotelIn, SeguroMedicoIn, UbicacionDestinoIn, VueloIn,
)

router = APIRouter(prefix="/catalogo", tags=["Apoyo front"])


def _insertar(tabla: str, datos: dict, nombre: str) -> dict:
    """Inserta una fila y traduce los errores de la base a errores HTTP."""
    try:
        return sb.table(tabla).insert(datos).execute().data[0]
    except APIError as e:
        print(f"ERROR POST {tabla}:", e.code, e.message, e.details)
        if e.code == "23505":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Ya existe ese {nombre}")
        if e.code == "23503":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"La ubicación indicada no existe ({e.details})"
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"No se pudo guardar: {e.message}")


def _borrar(tabla: str, id_: int, nombre: str) -> dict:
    """Borra una fila por id. 404 si no existe, 409 si otra tabla la usa."""
    try:
        borradas = sb.table(tabla).delete().eq("id", id_).execute().data
    except APIError as e:
        print(f"ERROR DELETE {tabla}:", e.code, e.message, e.details)
        if e.code == "23503":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"No se puede eliminar: el {nombre} está en uso (paquetes, vuelos u hoteles)",
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"No se pudo eliminar: {e.message}")
    if not borradas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{nombre.capitalize()} no encontrado")
    return {"detail": f"{nombre.capitalize()} eliminado"}


@router.get("/ubicaciones-destino")
def ubicaciones_destino(_: dict = Depends(usuario_actual)) -> list[dict]:
    """Ciudades de destino/hospedaje (para el formulario de paquetes)."""
    return sb.table("ubicacion_destino").select("*").order("ciudad").execute().data


@router.post("/ubicaciones-destino", status_code=status.HTTP_201_CREATED)
def crear_ubicacion_destino(datos: UbicacionDestinoIn, _: dict = Depends(solo_admin)) -> dict:
    """Carga una ciudad de destino (solo personal interno)."""
    return _insertar("ubicacion_destino", datos.model_dump(mode="json"), "destino")


@router.delete("/ubicaciones-destino/{ubicacion_id}")
def eliminar_ubicacion_destino(ubicacion_id: int, _: dict = Depends(solo_admin)) -> dict:
    """Elimina una ciudad de destino si ningún hotel, vuelo o paquete la usa."""
    return _borrar("ubicacion_destino", ubicacion_id, "destino")


@router.get("/aeropuertos")
def aeropuertos(_: dict = Depends(usuario_actual)) -> list[dict]:
    """Aeropuertos (origen y destino de los vuelos)."""
    return sb.table("ubicacion_aeropuerto").select("*").order("ciudad").execute().data


@router.post("/aeropuertos", status_code=status.HTTP_201_CREATED)
def crear_aeropuerto(datos: AeropuertoIn, _: dict = Depends(solo_admin)) -> dict:
    """Carga un aeropuerto (solo personal interno)."""
    return _insertar("ubicacion_aeropuerto", datos.model_dump(mode="json"), "aeropuerto")


@router.delete("/aeropuertos/{aeropuerto_id}")
def eliminar_aeropuerto(aeropuerto_id: int, _: dict = Depends(solo_admin)) -> dict:
    """Elimina un aeropuerto si ningún vuelo o escala lo usa."""
    return _borrar("ubicacion_aeropuerto", aeropuerto_id, "aeropuerto")


@router.get("/hoteles")
def hoteles(_: dict = Depends(usuario_actual)) -> list[dict]:
    """Hoteles disponibles."""
    return sb.table("hoteles").select("*").order("nombre_hotel").execute().data


@router.post("/hoteles", status_code=status.HTTP_201_CREATED)
def crear_hotel(datos: HotelIn, _: dict = Depends(solo_admin)) -> dict:
    """Carga un hotel (solo personal interno)."""
    return _insertar("hoteles", datos.model_dump(mode="json"), "hotel")


@router.delete("/hoteles/{hotel_id}")
def eliminar_hotel(hotel_id: int, _: dict = Depends(solo_admin)) -> dict:
    """Elimina un hotel si ningún paquete lo usa."""
    return _borrar("hoteles", hotel_id, "hotel")


@router.get("/vuelos")
def vuelos(_: dict = Depends(usuario_actual)) -> list[dict]:
    """Vuelos disponibles, cada uno con sus escalas ordenadas en `escalas_vuelo`."""
    filas = (
        sb.table("vuelos")
        .select(
            "*, escalas_vuelo(orden, id_ubi_aeropuerto, "
            "ubicacion_aeropuerto(ciudad, codigo_aeropuerto))"
        )
        .order("fecha_ida")
        .execute()
        .data
    )
    for f in filas:
        f["escalas_vuelo"].sort(key=lambda e: e["orden"])
    return filas


@router.post("/vuelos", status_code=status.HTTP_201_CREATED)
def crear_vuelo(vuelo: VueloIn, _: dict = Depends(solo_admin)) -> dict:
    """Carga un vuelo y sus escalas (solo personal interno).

    Si falla el guardado de las escalas, borra el vuelo para no dejarlo a medias.
    """
    datos = vuelo.model_dump(mode="json", exclude={"escalas"})
    datos["cantidad_escalas"] = len(vuelo.escalas)
    creado = _insertar("vuelos", datos, "vuelo")

    if vuelo.escalas:
        filas = [
            {"id_vuelo": creado["id"], "id_ubi_aeropuerto": aeropuerto, "orden": orden}
            for orden, aeropuerto in enumerate(vuelo.escalas, start=1)
        ]
        try:
            sb.table("escalas_vuelo").insert(filas).execute()
        except APIError as e:
            print("ERROR POST escalas_vuelo:", e.code, e.message, e.details)
            sb.table("vuelos").delete().eq("id", creado["id"]).execute()
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Alguna escala no es un aeropuerto válido"
            )
    creado["escalas_vuelo"] = [
        {"orden": f["orden"], "id_ubi_aeropuerto": f["id_ubi_aeropuerto"]}
        for f in (filas if vuelo.escalas else [])
    ]
    return creado


@router.get("/vuelos/{vuelo_id}/escalas")
def escalas_de_vuelo(vuelo_id: int, _: dict = Depends(usuario_actual)) -> dict:
    """Cantidad de escalas de un vuelo y los aeropuertos donde hace escala, en orden."""
    if not sb.table("vuelos").select("id").eq("id", vuelo_id).execute().data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vuelo no encontrado")
    filas = (
        sb.table("escalas_vuelo")
        .select("orden, id_ubi_aeropuerto, ubicacion_aeropuerto(ciudad, pais, codigo_aeropuerto)")
        .eq("id_vuelo", vuelo_id)
        .order("orden")
        .execute()
        .data
    )
    escalas = [
        {
            "orden": f["orden"],
            "id_ubi_aeropuerto": f["id_ubi_aeropuerto"],
            **(f.get("ubicacion_aeropuerto") or {}),
        }
        for f in filas
    ]
    return {"id_vuelo": vuelo_id, "cantidad_escalas": len(escalas), "escalas": escalas}


@router.put("/vuelos/{vuelo_id}/escalas")
def modificar_escalas(vuelo_id: int, datos: EscalasIn, _: dict = Depends(solo_admin)) -> dict:
    """Reemplaza las escalas de un vuelo (lista vacía = vuelo directo).

    Actualiza también `cantidad_escalas`. Si falla el guardado, restaura las
    escalas anteriores.
    """
    vuelo = (
        sb.table("vuelos")
        .select("id, id_ubi_aereo_origen, id_ubi_aereo_destino")
        .eq("id", vuelo_id)
        .execute()
        .data
    )
    if not vuelo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vuelo no encontrado")
    if {vuelo[0]["id_ubi_aereo_origen"], vuelo[0]["id_ubi_aereo_destino"]} & set(datos.escalas):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Una escala no puede ser el origen ni el destino del vuelo"
        )

    previas = (
        sb.table("escalas_vuelo")
        .select("id_vuelo, id_ubi_aeropuerto, orden")
        .eq("id_vuelo", vuelo_id)
        .execute()
        .data
    )
    nuevas = [
        {"id_vuelo": vuelo_id, "id_ubi_aeropuerto": aeropuerto, "orden": orden}
        for orden, aeropuerto in enumerate(datos.escalas, start=1)
    ]
    sb.table("escalas_vuelo").delete().eq("id_vuelo", vuelo_id).execute()
    try:
        if nuevas:
            sb.table("escalas_vuelo").insert(nuevas).execute()
    except APIError as e:
        print("ERROR PUT escalas_vuelo:", e.code, e.message, e.details)
        if previas:
            sb.table("escalas_vuelo").insert(previas).execute()  # deja todo como estaba
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Alguna escala no es un aeropuerto válido")

    sb.table("vuelos").update({"cantidad_escalas": len(nuevas)}).eq("id", vuelo_id).execute()
    return {"id_vuelo": vuelo_id, "cantidad_escalas": len(nuevas), "escalas_vuelo": nuevas}


@router.delete("/vuelos/{vuelo_id}")
def eliminar_vuelo(vuelo_id: int, _: dict = Depends(solo_admin)) -> dict:
    """Elimina un vuelo y sus escalas, si ningún paquete ni asiento lo usa."""
    for tabla, motivo in (
        ("paquetes_turisticos", "un paquete lo usa"),
        ("asiento", "tiene asientos reservados"),
    ):
        if sb.table(tabla).select("id").eq("id_vuelo", vuelo_id).limit(1).execute().data:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"No se puede eliminar el vuelo: {motivo}"
            )
    sb.table("escalas_vuelo").delete().eq("id_vuelo", vuelo_id).execute()
    return _borrar("vuelos", vuelo_id, "vuelo")


@router.get("/seguros")
def seguros(_: dict = Depends(usuario_actual)) -> list[dict]:
    """Seguros médicos disponibles."""
    return sb.table("seguro_medico").select("*").order("nombre").execute().data


@router.post("/seguros", status_code=status.HTTP_201_CREATED)
def crear_seguro(datos: SeguroMedicoIn, _: dict = Depends(solo_admin)) -> dict:
    """Carga un seguro médico (solo personal interno)."""
    return _insertar("seguro_medico", datos.model_dump(mode="json"), "seguro")


@router.delete("/seguros/{seguro_id}")
def eliminar_seguro(seguro_id: int, _: dict = Depends(solo_admin)) -> dict:
    """Elimina un seguro médico si ningún paquete lo usa."""
    return _borrar("seguro_medico", seguro_id, "seguro")


@router.get("/vuelos/{vuelo_id}/asientos-ocupados")
def asientos_ocupados(vuelo_id: int, _: dict = Depends(usuario_actual)) -> list[dict]:
    """Asientos ya reservados de un vuelo, como [{'fila': 3, 'letra': 'B'}, ...]."""
    return sb.table("asiento").select("fila, letra").eq("id_vuelo", vuelo_id).execute().data