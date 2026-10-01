"""Servicio de notificaciones por mail (DFD 6).

Arma el mail al cliente (6.1) y al sector de la empresa (6.2), los envía (6.3)
y deja el registro en la tabla `mails` (6.4).

Orden de envío:
1. Brevo por API HTTPS, si hay `BREVO_API_KEY` y `MAIL_REMITENTE`
   (funciona en Render gratis, que bloquea los puertos SMTP).
2. SMTP, si hay `SMTP_USER` y `SMTP_PASSWORD` (para correr en local).
3. Simulado: el mail no sale pero igual se registra con estado "simulado".
Una falla de mail nunca rompe la operación que lo disparó.
"""
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

import httpx

from app.config import settings
from app.db import sb


BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _enviar_brevo(destinatario: str, asunto: str, cuerpo: str) -> str:
    """Envía por la API HTTPS de Brevo. Devuelve 'enviado' o 'error'."""
    try:
        resp = httpx.post(
            BREVO_URL,
            headers={
                "api-key": settings.brevo_api_key,
                "accept": "application/json",
                "content-type": "application/json",
            },
            json={
                "sender": {"name": "Aeroplate", "email": settings.mail_remitente},
                "to": [{"email": destinatario}],
                "subject": asunto,
                "textContent": cuerpo,
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            return "enviado"
        print("ERROR MAIL BREVO:", resp.status_code, resp.text)
        return "error"
    except Exception as e:
        print("ERROR MAIL BREVO:", repr(e))
        return "error"


def _enviar_smtp(destinatario: str, asunto: str, cuerpo: str) -> str:
    """Envía por SMTP. Devuelve 'enviado' o 'error'."""
    msg = EmailMessage()
    msg["From"] = settings.smtp_user
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content(cuerpo)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return "enviado"
    except Exception as e:
        print("ERROR MAIL:", repr(e))
        return "error"


def _enviar(destinatario: str, asunto: str, cuerpo: str) -> str:
    """Elige el medio de envío y devuelve 'enviado', 'simulado' o 'error'."""
    if settings.brevo_api_key and settings.mail_remitente:
        return _enviar_brevo(destinatario, asunto, cuerpo)
    if settings.smtp_user and settings.smtp_password:
        return _enviar_smtp(destinatario, asunto, cuerpo)
    print(f"[MAIL SIMULADO] a {destinatario}: {asunto}")
    return "simulado"


def _registrar(
    id_cliente: str, id_compra: int, id_contacto: str | None,
    destinatario: str, asunto: str, cuerpo: str, estado: str,
) -> None:
    """Guarda el mail en la tabla `mails`."""
    try:
        sb.table("mails").insert(
            {
                "id_cliente": id_cliente,
                "id_compra": id_compra,
                "id_contacto": id_contacto,
                "destinatario": destinatario,
                "asunto": asunto,
                "cuerpo": cuerpo,
                "estado": estado,
                "fecha_envio": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception as e:
        print("ERROR REGISTRO MAIL:", repr(e))


def _textos(evento: str, compra: dict, cliente: dict, paquetes: str) -> tuple[str, str, str, str]:
    """Devuelve (asunto_cliente, cuerpo_cliente, asunto_sector, cuerpo_sector)."""
    numero = compra["numero_pedido"]
    total = compra["precio_total"]
    nombre = f"{cliente['nombre']} {cliente['apellido']}"
    saludo = f"Hola {cliente['nombre']},\n\n"
    firma = "\n\nEquipo Aeroplate"
    resumen = f"Pedido N° {numero}\nPaquete: {paquetes}\nTotal: ${total}"

    if evento == "pagada":
        return (
            f"Aeroplate: pago confirmado (pedido N° {numero})",
            saludo + "Recibimos tu pago. ¡Gracias por tu compra!\n\n" + resumen + firma,
            f"Nueva venta pagada: pedido N° {numero}",
            f"Cliente: {nombre} ({cliente['email']})\n" + resumen + "\nEstado: pagada, pendiente de entrega.",
        )
    if evento == "vencida":
        return (
            f"Aeroplate: tu pedido N° {numero} venció",
            saludo + "Tu pedido venció porque no se registró el pago en 15 minutos. "
            "Los asientos fueron liberados; podés hacer una nueva compra.\n\n" + resumen + firma,
            f"Pedido vencido: N° {numero}",
            f"Cliente: {nombre} ({cliente['email']})\n" + resumen + "\nEstado: vencida (sin pago).",
        )
    if evento == "entregada":
        return (
            f"Aeroplate: tu pedido N° {numero} fue entregado",
            saludo + "Tu pedido fue entregado. ¡Buen viaje!\n\n" + resumen + firma,
            f"Pedido entregado: N° {numero}",
            f"Cliente: {nombre} ({cliente['email']})\n" + resumen + "\nEstado: entregada.",
        )
    raise ValueError(f"Evento de mail desconocido: {evento}")


def _notificar(id_compra: int, evento: str) -> None:
    """Arma y envía los mails de un evento (cliente + sectores activos)."""
    compra = (
        sb.table("compras")
        .select("*, detalle_compras(paquetes_turisticos(titulo, codigo_paquete))")
        .eq("id", id_compra)
        .execute()
        .data
    )
    if not compra:
        return
    compra = compra[0]
    cliente = (
        sb.table("cliente")
        .select("nombre, apellido, email")
        .eq("id", compra["id_cliente"])
        .execute()
        .data[0]
    )
    paquetes = ", ".join(
        d["paquetes_turisticos"]["titulo"]
        for d in compra.get("detalle_compras") or []
        if d.get("paquetes_turisticos")
    )
    asunto_c, cuerpo_c, asunto_s, cuerpo_s = _textos(evento, compra, cliente, paquetes)

    estado = _enviar(cliente["email"], asunto_c, cuerpo_c)
    _registrar(compra["id_cliente"], id_compra, None, cliente["email"], asunto_c, cuerpo_c, estado)

    contactos = (
        sb.table("contactos_empresa").select("id, email").eq("activo", True).execute().data
    )
    for contacto in contactos:
        estado = _enviar(contacto["email"], asunto_s, cuerpo_s)
        _registrar(
            compra["id_cliente"], id_compra, contacto["id"],
            contacto["email"], asunto_s, cuerpo_s, estado,
        )


def notificar_compra(id_compra: int, evento: str) -> None:
    """Notifica un evento de la compra ('pagada', 'vencida' o 'entregada').

    Nunca lanza excepciones: se usa como tarea de fondo.
    """
    try:
        _notificar(id_compra, evento)
    except Exception as e:
        print("ERROR NOTIFICAR:", repr(e))