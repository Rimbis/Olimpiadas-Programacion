"""Endpoints de compras del cliente (DFD 2.3-2.5, 3.1, 4.1, 4.2 y 4.3)."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from postgrest.exceptions import APIError

from app.auth import solo_cliente, solo_admin
from app.db import sb
from app.schemas import CompraIn, ModificarCompraIn
from app.services.vencimientos import notificar_vencidas, vencer_compras

router = APIRouter(prefix="/compras", tags=["Compras"])

# Pedido con su paquete, pasajeros y asientos.
DETALLE = (
    "*, detalle_compras(cantidad_pasajeros, precio_unitario, subtotal, "
    "paquetes_turisticos(id, titulo, codigo_paquete)), "
    "pasajeros_reserva(nombre, apellido, dni, tipo_pasajero, asiento(fila, letra))"
)


def _barrer(background: BackgroundTasks) -> None:
    """Vence las compras pendientes de más de 15 min y avisa por mail en segundo plano."""
    ids = vencer_compras()
    if ids:
        background.add_task(notificar_vencidas, ids)


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_compra(
    compra: CompraIn, background: BackgroundTasks, usuario: dict = Depends(solo_cliente)
) -> dict:
    """Confirma la compra: guarda el pedido, los pasajeros y reserva los asientos.

    Queda 'pendiente' durante 15 minutos hasta que se pague.
    """
    _barrer(background)
    try:
        return sb.rpc(
            "crear_compra",
            {
                "p_id_cliente": usuario["id"],
                "p_id_paquete": compra.id_paquete,
                "p_pasajeros": [p.model_dump(mode="json") for p in compra.pasajeros],
            },
        ).execute().data
    except APIError as e:
        msg = e.message or ""
        if e.code == "23505":
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Uno de los asientos ya está ocupado o repetido"
            )
        if "PAQUETE_INEXISTENTE" in msg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paquete no encontrado")
        if "PAQUETE_SIN_VUELO" in msg:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "El paquete no tiene vuelo asignado")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo crear la compra")


@router.get("")
def mis_pedidos(background: BackgroundTasks, usuario: dict = Depends(solo_cliente)) -> list[dict]:
    """Lista los pedidos del cliente, del más nuevo al más viejo."""
    _barrer(background)
    return (
        sb.table("compras")
        .select(DETALLE)
        .eq("id_cliente", usuario["id"])
        .order("fecha", desc=True)
        .execute()
        .data
    )


@router.get("/admin/todas")
def admin_ver_todas_las_compras(background: BackgroundTasks, usuario: dict = Depends(solo_admin)) -> list[dict]:
    """Permite al administrador ver las compras de todos los clientes."""
    _barrer(background)
    return (
        sb.table("compras")
        .select(DETALLE)
        .order("fecha", desc=True)
        .execute()
        .data
    )


@router.get("/{compra_id}")
def obtener_pedido(
    compra_id: int, background: BackgroundTasks, usuario: dict = Depends(solo_cliente)
) -> dict:
    """Devuelve un pedido del cliente con paquete, pasajeros y asientos."""
    _barrer(background)
    data = (
        sb.table("compras")
        .select(DETALLE)
        .eq("id", compra_id)
        .eq("id_cliente", usuario["id"])
        .execute()
        .data
    )
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    return data[0]


@router.put("/{compra_id}")
def modificar_pedido(
    compra_id: int,
    datos: ModificarCompraIn,
    background: BackgroundTasks,
    usuario: dict = Depends(solo_cliente),
) -> dict:
    """Modifica un pedido pendiente: reemplaza pasajeros y asientos y recalcula el total."""
    _barrer(background)
    try:
        return sb.rpc(
            "modificar_compra",
            {
                "p_id_compra": compra_id,
                "p_id_cliente": usuario["id"],
                "p_pasajeros": [p.model_dump(mode="json") for p in datos.pasajeros],
            },
        ).execute().data
    except APIError as e:
        msg = e.message or ""
        if e.code == "23505":
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Uno de los asientos ya está ocupado o repetido"
            )
        if "COMPRA_INEXISTENTE" in msg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
        if "NO_PENDIENTE" in msg:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Solo se pueden modificar pedidos pendientes"
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo modificar el pedido")


@router.delete("/{compra_id}")
def cancelar_pedido(
    compra_id: int, background: BackgroundTasks, usuario: dict = Depends(solo_cliente)
) -> dict:
    """Cancela un pedido pendiente y libera sus asientos."""
    _barrer(background)
    try:
        sb.rpc(
            "cancelar_compra", {"p_id_compra": compra_id, "p_id_cliente": usuario["id"]}
        ).execute()
    except APIError as e:
        msg = e.message or ""
        if "COMPRA_INEXISTENTE" in msg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
        if "NO_PENDIENTE" in msg:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Solo se pueden cancelar pedidos pendientes"
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo cancelar el pedido")
    return {"detail": "Pedido cancelado"}


@router.delete("/admin/{compra_id}")
def admin_cancelar_pedido(
    compra_id: int, background: BackgroundTasks, usuario: dict = Depends(solo_admin)
) -> dict:
    """Permite al administrador cancelar cualquier pedido del sistema."""
    _barrer(background)
    try:
        # Buscamos la compra primero para conocer el cliente y pasar su ID a la función RPC
        compra_data = sb.table("compras").select("id_cliente").eq("id", compra_id).execute().data
        if not compra_data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
        
        id_cliente = compra_data[0]["id_cliente"]
        sb.rpc(
            "cancelar_compra", {"p_id_compra": compra_id, "p_id_cliente": id_cliente}
        ).execute()
    except APIError as e:
        msg = e.message or ""
        if "COMPRA_INEXISTENTE" in msg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
        if "NO_PENDIENTE" in msg:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Solo se pueden cancelar pedidos pendientes"
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo cancelar el pedido")
    return {"detail": "Pedido cancelado por el administrador"}

