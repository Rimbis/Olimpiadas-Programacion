"""Vencimiento de compras pendientes (DFD 3.6 y 3.7).

La lógica real vive en la función SQL `vencer_compras` (sql/funciones.sql):
pasa a 'vencida' lo pendiente de más de 15 minutos y libera los asientos.
Acá se la llama y se avisa por mail de cada compra vencida.
"""
from app.db import sb
from app.services.mails import notificar_compra


def vencer_compras() -> list[int]:
       """Vence las compras pendientes de más de 15 min y devuelve sus ids."""
       try:
           return sb.rpc("vencer_compras").execute().data or []
       except Exception as e:
           print("ERROR vencer_compras:", repr(e))
           return []

def notificar_vencidas(ids: list[int]) -> None:
    """Envía el mail de 'compra vencida' de cada id."""
    for id_compra in ids:
        notificar_compra(id_compra, "vencida")


def vencer_y_notificar() -> list[int]:
    """Vence y notifica en un solo paso (lo usa el barrido periódico)."""
    ids = vencer_compras()
    notificar_vencidas(ids)
    return ids
