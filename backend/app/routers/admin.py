"""Endpoints de administración (DFD 5): pedidos, entrega, anulación,
estado de cuenta y auditoría, más el alta de personal interno."""
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from postgrest.exceptions import APIError

from app.auth import solo_admin, usuario_actual
from app.db import sb
from app.schemas import AdminIn
from app.services.mails import notificar_compra
from app.services.vencimientos import notificar_vencidas, vencer_compras

router = APIRouter(prefix="/admin", tags=["Administración"])

ESTADOS = ("pendiente", "pagada", "entregada", "vencida", "cancelada", "anulada")

PEDIDO = (
    "*, detalle_compras(cantidad_pasajeros, subtotal, "
    "paquetes_turisticos(id, titulo, codigo_paquete)), "
    "pasajeros_reserva(nombre, apellido, dni, tipo_pasajero, asiento(fila, letra))"
)


def solo_jefe_ventas(usuario: dict = Depends(usuario_actual)) -> dict:
    """Permite el acceso solo al jefe de ventas."""
    if usuario["rol"] != "jefe_ventas":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo para el jefe de ventas")
    return usuario


def _barrer(background: BackgroundTasks) -> None:
    """Vence compras viejas y avisa por mail en segundo plano."""
    ids = vencer_compras()
    if ids:
        background.add_task(notificar_vencidas, ids)


def _con_clientes(filas: list[dict]) -> list[dict]:
    """Agrega a cada fila (con `id_cliente`) los datos del cliente en `cliente`."""
    ids = list({f["id_cliente"] for f in filas})
    if not ids:
        return filas
    clientes = (
        sb.table("cliente").select("id, nombre, apellido, email").in_("id", ids).execute().data
    )
    por_id = {c["id"]: c for c in clientes}
    for f in filas:
        f["cliente"] = por_id.get(f["id_cliente"])
    return filas


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
    except Exception:
        sb.auth.admin.delete_user(user_id)  # no dejar cuentas a medias
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Error al registrar el admin"
        )
    return {"mensaje": "Admin creado", "id": user_id, "rol": datos.rol}


@router.get("/pedidos")
def listar_pedidos(
    background: BackgroundTasks,
    estado: str = "pagada",
    _: dict = Depends(solo_admin),
) -> list[dict]:
    """Lista pedidos por estado (DFD 5.3).

    Por defecto 'pagada': los pedidos cobrados que esperan ser entregados.
    """
    if estado not in ESTADOS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Estado inválido. Usar: {', '.join(ESTADOS)}")
    _barrer(background)
    pedidos = (
        sb.table("compras").select(PEDIDO).eq("estado", estado).order("fecha").execute().data
    )
    return _con_clientes(pedidos)


@router.get("/pedidos/{compra_id}")
def obtener_pedido(compra_id: int, _: dict = Depends(solo_admin)) -> dict:
    """Devuelve un pedido cualquiera con paquete, pasajeros, asientos y cliente."""
    data = sb.table("compras").select(PEDIDO).eq("id", compra_id).execute().data
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    return _con_clientes(data)[0]


@router.post("/pedidos/{compra_id}/entregar")
def entregar_pedido(
    compra_id: int, background: BackgroundTasks, usuario: dict = Depends(solo_admin)
) -> dict:
    """Entrega un pedido pagado (DFD 5.4): pasa a 'entregada' y queda en historial_ventas."""
    try:
        sb.rpc(
            "entregar_compra", {"p_id_compra": compra_id, "p_id_admin": usuario["id"]}
        ).execute()
    except APIError as e:
        msg = e.message or ""
        if "COMPRA_INEXISTENTE" in msg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
        if "NO_ENTREGABLE" in msg:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Solo se pueden entregar pedidos pagados"
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo entregar el pedido")
    background.add_task(notificar_compra, compra_id, "entregada")
    return {"detail": "Pedido entregado"}


@router.post("/pedidos/{compra_id}/anular")
def anular_pedido(compra_id: int, _: dict = Depends(solo_admin)) -> dict:
    """Anula un pedido pendiente o pagado (DFD 5.5) y libera sus asientos."""
    try:
        sb.rpc("anular_compra", {"p_id_compra": compra_id}).execute()
    except APIError as e:
        msg = e.message or ""
        if "COMPRA_INEXISTENTE" in msg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
        if "NO_ANULABLE" in msg:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Solo se pueden anular pedidos pendientes o pagados"
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo anular el pedido")
    return {"detail": "Pedido anulado"}


@router.get("/estado-cuenta")
def estado_cuenta(
    background: BackgroundTasks,
    orden: Literal["fecha", "cliente"] = "fecha",
    _: dict = Depends(solo_admin),
) -> list[dict]:
    """Estado de cuenta (DFD 5.6): ventas a cobrar y cobradas.

    - `orden=fecha`: lista de pedidos, del más nuevo al más viejo.
    - `orden=cliente`: agrupado por cliente, con totales cobrado y a cobrar.

    'A cobrar' = pedido pendiente de pago; 'cobrado' = pagado o entregado.
    """
    _barrer(background)
    pedidos = (
        sb.table("compras")
        .select("id, numero_pedido, id_cliente, fecha, precio_total, estado")
        .in_("estado", ["pendiente", "pagada", "entregada"])
        .order("fecha", desc=True)
        .execute()
        .data
    )
    _con_clientes(pedidos)
    for p in pedidos:
        p["cobrado"] = p["estado"] != "pendiente"
    if orden == "fecha":
        return pedidos

    grupos: dict[str, dict] = {}
    for p in pedidos:
        g = grupos.setdefault(
            p["id_cliente"],
            {"cliente": p["cliente"], "pedidos": [], "total_cobrado": 0.0, "total_a_cobrar": 0.0},
        )
        g["pedidos"].append(p)
        clave = "total_cobrado" if p["cobrado"] else "total_a_cobrar"
        g[clave] = round(g[clave] + float(p["precio_total"]), 2)
    return sorted(
        grupos.values(), key=lambda g: ((g["cliente"] or {}).get("apellido") or "").lower()
    )


@router.get("/auditoria")
def auditoria(limite: int = 200, _: dict = Depends(solo_admin)) -> list[dict]:
    """Historial de ventas entregadas (DFD 5.7): quién entregó qué, a quién y cuándo."""
    limite = max(1, min(limite, 1000))
    filas = (
        sb.table("historial_ventas")
        .select("*")
        .order("fecha", desc=True)
        .limit(limite)
        .execute()
        .data
    )
    _con_clientes(filas)
    admins = sb.table("admin").select("id, nombre, apellido, rol").execute().data
    por_id = {a["id"]: a for a in admins}
    for f in filas:
        f["admin"] = por_id.get(f.get("id_admin"))
    return filas
