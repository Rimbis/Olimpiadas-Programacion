"""Endpoints de pago (DFD 3.2 a 3.5) con Mercado Pago.

Flujo:
1. `POST /pagos/{id}/iniciar`   -> crea la preferencia y devuelve el link de pago.
2. El cliente paga en Mercado Pago.
3. Mercado Pago avisa a `POST /pagos/webhook` (solo funciona con URL pública https).
   Si no llega (por ejemplo en local), `POST /pagos/{id}/verificar` consulta a
   Mercado Pago y confirma igual.

El webhook NO confía en lo que recibe: vuelve a consultar el pago a la API de
Mercado Pago con nuestro token, así nadie puede falsificar una aprobación.

Sin `MP_ACCESS_TOKEN` en el `.env` el pago es simulado (`/pagos/{id}/simular`),
útil para probar y grabar el video. Con token configurado, el simulado se bloquea.
"""
import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from postgrest.exceptions import APIError

from app.auth import solo_cliente
from app.config import settings
from app.db import sb
from app.services.mails import notificar_compra
from app.services.vencimientos import notificar_vencidas, vencer_compras

router = APIRouter(prefix="/pagos", tags=["Pagos"])

MP_API = "https://api.mercadopago.com"
ESTADOS_MP = {"approved": "aprobado", "rejected": "rechazado", "cancelled": "rechazado"}


def _cabeceras() -> dict:
    """Cabeceras de autenticación para la API de Mercado Pago."""
    return {"Authorization": f"Bearer {settings.mp_access_token}"}


def _barrer(background: BackgroundTasks) -> None:
    """Vence compras viejas y avisa por mail en segundo plano."""
    ids = vencer_compras()
    if ids:
        background.add_task(notificar_vencidas, ids)


def _compra_a_pagar(compra_id: int, usuario: dict) -> dict:
    """Devuelve la compra del cliente si existe y sigue pendiente de pago."""
    data = (
        sb.table("compras")
        .select("id, numero_pedido, precio_total, estado")
        .eq("id", compra_id)
        .eq("id_cliente", usuario["id"])
        .execute()
        .data
    )
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    if data[0]["estado"] != "pendiente":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"El pedido no está pendiente de pago (estado: {data[0]['estado']})",
        )
    return data[0]


def _procesar_pago(pago: dict, background: BackgroundTasks) -> bool:
    """Registra un pago de Mercado Pago y, si corresponde, deja la compra pagada.

    Devuelve True si esta llamada dejó la compra en 'pagada'.
    """
    estado = ESTADOS_MP.get(pago.get("status"))
    referencia = str(pago.get("external_reference") or "")
    if estado is None or not referencia.isdigit():
        return False  # pago pendiente/en proceso o sin referencia a un pedido
    compra_id = int(referencia)

    compra = sb.table("compras").select("precio_total").eq("id", compra_id).execute().data
    if not compra:
        return False
    monto = float(pago.get("transaction_amount") or 0)
    if estado == "aprobado" and abs(monto - float(compra[0]["precio_total"])) > 0.01:
        print(f"PAGO CON MONTO DISTINTO: pedido {compra_id}, pagado {monto}")
        return False

    try:
        pagada = sb.rpc(
            "confirmar_pago",
            {
                "p_id_compra": compra_id,
                "p_monto": monto,
                "p_metodo": pago.get("payment_method_id") or "mercadopago",
                "p_estado_pago": estado,
                "p_id_externo": str(pago.get("id")),
            },
        ).execute().data
    except APIError as e:
        print("ERROR confirmar_pago:", e.message)
        return False
    if pagada:
        background.add_task(notificar_compra, compra_id, "pagada")
    return bool(pagada)


@router.post("/{compra_id}/iniciar")
def iniciar_pago(
    compra_id: int, background: BackgroundTasks, usuario: dict = Depends(solo_cliente)
) -> dict:
    """Genera el pago del pedido (DFD 3.2).

    Con Mercado Pago configurado devuelve el link de pago; si no, indica el
    endpoint del pago simulado.
    """
    _barrer(background)
    compra = _compra_a_pagar(compra_id, usuario)

    if not settings.mp_access_token:
        return {"modo": "simulado", "confirmar_en": f"/pagos/{compra_id}/simular"}

    base = settings.base_url.lower().strip().rstrip("/")
    
    # URL del Frontend donde el usuario debe ser redirigido tras pagar
    FRONTEND_URL = "https://olimpiadas-programacion-frontend.vercel.app/index.html"

    preferencia = {
        "items": [
            {
                "title": f"Aeroplate - Pedido N° {compra['numero_pedido']}",
                "quantity": 1,
                "unit_price": float(compra["precio_total"]),
                "currency_id": "ARS",
            }
        ],
        "external_reference": str(compra_id),
        "back_urls": {
            k: f"{FRONTEND_URL}/?pago={k}&pedido={compra_id}" for k in ("success", "failure", "pending")
        },
    }
    if base.startswith("https://"):  # Mercado Pago exige URL pública para esto
        preferencia["notification_url"] = f"{base}/pagos/webhook"
        preferencia["auto_return"] = "approved"

    try:
        r = httpx.post(
            f"{MP_API}/checkout/preferences", json=preferencia, headers=_cabeceras(), timeout=20
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        detalle = getattr(getattr(e, "response", None), "text", "")
        print("ERROR Mercado Pago (preferencia):", repr(e), "DETALLE:", detalle)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "No se pudo generar el pago")
    datos = r.json()
    return {
        "modo": "mercadopago",
        "init_point": datos["init_point"],
        "sandbox_init_point": datos.get("sandbox_init_point"),
    }


@router.post("/{compra_id}/verificar")
def verificar_pago(
    compra_id: int, background: BackgroundTasks, usuario: dict = Depends(solo_cliente)
) -> dict:
    """Consulta a Mercado Pago si el pedido fue pagado y lo confirma (sin webhook).

    El front lo llama al volver de Mercado Pago. Es idempotente.
    """
    if not settings.mp_access_token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mercado Pago no está configurado")
    propia = (
        sb.table("compras").select("id").eq("id", compra_id).eq("id_cliente", usuario["id"])
        .execute().data
    )
    if not propia:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    try:
        r = httpx.get(
            f"{MP_API}/v1/payments/search",
            params={"external_reference": str(compra_id), "sort": "date_created", "criteria": "desc"},
            headers=_cabeceras(),
            timeout=20,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        print("ERROR Mercado Pago (búsqueda):", repr(e))
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "No se pudo consultar el pago")
    for pago in r.json().get("results", []):
        _procesar_pago(pago, background)
    estado = sb.table("compras").select("estado").eq("id", compra_id).execute().data[0]["estado"]
    return {"estado": estado}


@router.post("/{compra_id}/simular")
def simular_pago(
    compra_id: int, background: BackgroundTasks, usuario: dict = Depends(solo_cliente)
) -> dict:
    """Aprueba el pago sin pasarela (solo si Mercado Pago NO está configurado)."""
    if settings.mp_access_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El pago simulado está deshabilitado")
    _barrer(background)
    compra = _compra_a_pagar(compra_id, usuario)
    pagada = sb.rpc(
        "confirmar_pago",
        {
            "p_id_compra": compra_id,
            "p_monto": float(compra["precio_total"]),
            "p_metodo": "simulado",
            "p_estado_pago": "aprobado",
            "p_id_externo": f"sim-{compra_id}",
        },
    ).execute().data
    if not pagada:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo registrar el pago")
    background.add_task(notificar_compra, compra_id, "pagada")
    return {"estado": "pagada", "numero_pedido": compra["numero_pedido"]}


@router.post("/webhook")
async def webhook(request: Request, background: BackgroundTasks) -> dict:
    """Recibe la notificación de Mercado Pago (DFD 3.3) y confirma el pago (3.4 y 3.5).

    Responde 200 siempre que la notificación sea válida, para que Mercado Pago
    no la reintente.
    """
    params = request.query_params
    tipo = params.get("type") or params.get("topic")
    pago_id = params.get("data.id") or params.get("id")
    if not pago_id:
        try:
            cuerpo = await request.json()
        except Exception:
            cuerpo = {}
        tipo = tipo or cuerpo.get("type")
        pago_id = (cuerpo.get("data") or {}).get("id")
    if tipo != "payment" or not pago_id or not settings.mp_access_token:
        return {"ok": True}

    async with httpx.AsyncClient(timeout=20) as cliente:
        r = await cliente.get(f"{MP_API}/v1/payments/{pago_id}", headers=_cabeceras())
    if r.status_code != 200:
        return {"ok": True}
    _procesar_pago(r.json(), background)
    return {"ok": True}
