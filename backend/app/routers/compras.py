"""Endpoints de compras del cliente (DFD 2.3-2.5, 3.1, 4.1 y 4.3)."""
from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError

from app.auth import solo_cliente
from app.db import sb
from app.schemas import CompraIn

router = APIRouter(prefix="/compras", tags=["Compras"])

# Pedido con su paquete, pasajeros y asientos.
DETALLE = (
    "*, detalle_compras(cantidad_pasajeros, precio_unitario, subtotal, "
    "paquetes_turisticos(id, titulo, codigo_paquete)), "
    "pasajeros_reserva(nombre, apellido, dni, tipo_pasajero, asiento(fila, letra))"
)


def _actualizar_vencidas() -> None:
    """Pasa a 'vencida' las compras pendientes de más de 15 min y libera sus asientos."""
    sb.rpc("vencer_compras").execute()


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_compra(compra: CompraIn, usuario: dict = Depends(solo_cliente)) -> dict:
    """Confirma la compra: guarda el pedido, los pasajeros y reserva los asientos.

    Queda 'pendiente' durante 15 minutos hasta que se pague.
    """
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
        if e.code == "23505":
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Uno de los asientos ya está ocupado o repetido"
            )
        if "PAQUETE_INEXISTENTE" in (e.message or ""):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paquete no encontrado")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo crear la compra")


@router.get("")
def mis_pedidos(usuario: dict = Depends(solo_cliente)) -> list[dict]:
    """Lista los pedidos del cliente, del más nuevo al más viejo."""
    _actualizar_vencidas()
    return (
        sb.table("compras")
        .select(DETALLE)
        .eq("id_cliente", usuario["id"])
        .order("fecha", desc=True)
        .execute()
        .data
    )


@router.get("/{compra_id}")
def obtener_pedido(compra_id: int, usuario: dict = Depends(solo_cliente)) -> dict:
    """Devuelve un pedido del cliente con paquete, pasajeros y asientos."""
    _actualizar_vencidas()
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


@router.delete("/{compra_id}")
def cancelar_pedido(compra_id: int, usuario: dict = Depends(solo_cliente)) -> dict:
    """Cancela un pedido pendiente y libera sus asientos."""
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