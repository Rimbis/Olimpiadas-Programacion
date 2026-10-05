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
from datetime import datetime, timedelta, timezone
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


AR = timezone(timedelta(hours=-3))  # Argentina no usa horario de verano

# Consulta mínima (siempre funciona) y consulta completa para el mail de pago.
CONSULTA_BASICA = "*, detalle_compras(paquetes_turisticos(titulo, codigo_paquete))"
CONSULTA_COMPLETA = (
    "*, detalle_compras(cantidad_pasajeros, precio_unitario, subtotal, "
    "paquetes_turisticos(titulo, codigo_paquete, tipo_paquete, cantidad_noches, "
    "hoteles(nombre_hotel, estrellas), "
    "ubicacion_destino(ciudad, pais), "
    "seguro_medico(nombre, empresa), "
    "vuelos(fecha_ida, fecha_vuelta, clase, cantidad_escalas, "
    "origen:ubicacion_aeropuerto!id_ubi_aereo_origen(ciudad, codigo_aeropuerto), "
    "destino:ubicacion_aeropuerto!id_ubi_aereo_destino(ciudad, codigo_aeropuerto)))), "
    "pasajeros_reserva(nombre, apellido, dni, tipo_pasajero, asiento(fila, letra)), "
    "pagos(monto, metodo_pago, fecha, estado, id_externo)"
)


def _fecha(valor: str | None) -> str:
    """Convierte un timestamp ISO a 'dd/mm/aaaa HH:MM' en hora de Argentina."""
    if not valor:
        return "-"
    try:
        return datetime.fromisoformat(valor).astimezone(AR).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(valor)


def _pesos(valor) -> str:
    """Formatea un importe al estilo argentino: $1.250.000 o $1.250.000,50."""
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return f"${valor}"
    texto = f"{n:,.0f}" if n == int(n) else f"{n:,.2f}"
    return "$" + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _lugar(aeropuerto: dict | None) -> str:
    """'Buenos Aires (EZE)' a partir de un registro de ubicacion_aeropuerto."""
    if not aeropuerto:
        return "-"
    return f"{aeropuerto.get('ciudad', '-')} ({aeropuerto.get('codigo_aeropuerto', '-')})"


def _detalle(compra: dict, para_sector: bool) -> str:
    """Arma el detalle completo de un pedido pagado (paquete, vuelo, pasajeros, pago).

    Devuelve '' si la compra no trae los datos completos; el llamador usa
    entonces el resumen corto. `para_sector` agrega el DNI de los pasajeros.
    """
    items = compra.get("detalle_compras") or []
    if not items or "pasajeros_reserva" not in compra:
        return ""
    item = items[0]
    paq = item.get("paquetes_turisticos") or {}
    hotel = paq.get("hoteles") or {}
    destino = paq.get("ubicacion_destino") or {}
    seguro = paq.get("seguro_medico") or {}
    vuelo = paq.get("vuelos") or {}

    lineas = [f"Pedido N° {compra['numero_pedido']}"]
    lineas.append(
        f"Paquete: {paq.get('titulo', '-')} "
        f"(código {paq.get('codigo_paquete', '-')}, {paq.get('tipo_paquete', '-')})"
    )
    if destino:
        lineas.append(
            f"Destino: {destino.get('ciudad', '-')}, {destino.get('pais', '-')}"
            f" - {paq.get('cantidad_noches', '-')} noches"
        )
    if hotel:
        lineas.append(f"Hotel: {hotel.get('nombre_hotel', '-')} ({hotel.get('estrellas', '-')} estrellas)")
    if seguro:
        lineas.append(f"Seguro médico: {seguro.get('nombre', '-')} ({seguro.get('empresa', '-')})")

    if vuelo:
        lineas += [
            "",
            "VUELO",
            f"Ida: {_fecha(vuelo.get('fecha_ida'))} - "
            f"{_lugar(vuelo.get('origen'))} a {_lugar(vuelo.get('destino'))}",
            f"Vuelta: {_fecha(vuelo.get('fecha_vuelta'))} - "
            f"{_lugar(vuelo.get('destino'))} a {_lugar(vuelo.get('origen'))}",
            f"Clase: {vuelo.get('clase', '-')} - Escalas: {vuelo.get('cantidad_escalas', 0)}",
        ]

    pasajeros = compra.get("pasajeros_reserva") or []
    if pasajeros:
        lineas += ["", "PASAJEROS Y ASIENTOS"]
        for i, p in enumerate(pasajeros, start=1):
            asiento = p.get("asiento")
            if isinstance(asiento, list):
                asiento = asiento[0] if asiento else None
            sitio = f"{asiento['fila']}{asiento['letra']}" if asiento else "sin asignar"
            dni = f" - DNI {p['dni']}" if para_sector and p.get("dni") else ""
            lineas.append(
                f"{i}. {p['nombre']} {p['apellido']} ({p.get('tipo_pasajero', '-')})"
                f"{dni} - asiento {sitio}"
            )

    lineas += ["", "PAGO"]
    if item.get("cantidad_pasajeros") and item.get("precio_unitario") is not None:
        lineas.append(
            f"{item['cantidad_pasajeros']} pasajero(s) x {_pesos(item['precio_unitario'])}"
            f" = {_pesos(item.get('subtotal'))}"
        )
    lineas.append(f"Total: {_pesos(compra['precio_total'])}")
    pagos = sorted(compra.get("pagos") or [], key=lambda p: p.get("fecha") or "")
    if pagos:
        pago = pagos[-1]
        lineas.append(f"Método de pago: {pago.get('metodo_pago', '-')}")
        lineas.append(f"Fecha del pago: {_fecha(pago.get('fecha'))}")
        if pago.get("id_externo"):
            lineas.append(f"Código de operación: {pago['id_externo']}")
    return "\n".join(lineas)


def _cargar_compra(id_compra: int) -> dict | None:
    """Trae la compra con todos sus datos; si la consulta completa falla, usa la básica."""
    for consulta in (CONSULTA_COMPLETA, CONSULTA_BASICA):
        try:
            data = sb.table("compras").select(consulta).eq("id", id_compra).execute().data
            return data[0] if data else None
        except Exception as e:
            print("ERROR CONSULTA MAIL (se prueba una más simple):", repr(e))
    return None


def _textos(evento: str, compra: dict, cliente: dict, paquetes: str) -> tuple[str, str, str, str]:
    """Devuelve (asunto_cliente, cuerpo_cliente, asunto_sector, cuerpo_sector)."""
    numero = compra["numero_pedido"]
    total = compra["precio_total"]
    nombre = f"{cliente['nombre']} {cliente['apellido']}"
    saludo = f"Hola {cliente['nombre']},\n\n"
    firma = "\n\nEquipo Aeroplate"
    resumen = f"Pedido N° {numero}\nPaquete: {paquetes}\nTotal: ${total}"

    if evento == "pagada":
        detalle_c = _detalle(compra, para_sector=False) or resumen
        detalle_s = _detalle(compra, para_sector=True) or resumen
        enlace = ""
        if "localhost" not in settings.base_url:
            enlace = f"\n\nPodés ver tus pedidos ingresando a {settings.base_url}"
        return (
            f"Aeroplate: pago confirmado (pedido N° {numero})",
            saludo + "Recibimos tu pago. ¡Gracias por tu compra! "
            "Guardá este mail como comprobante.\n\n" + detalle_c + enlace + firma,
            f"Nueva venta pagada: pedido N° {numero}",
            f"Cliente: {nombre} ({cliente['email']})\n\n" + detalle_s
            + "\n\nEstado: pagada, pendiente de entrega.",
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
    compra = _cargar_compra(id_compra)
    if not compra:
        return
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
