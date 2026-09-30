"""Modelos Pydantic: definen y validan los datos que entran y salen de la API."""
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class RegistroIn(BaseModel):
    """Datos para dar de alta un cliente nuevo."""

    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)


class LoginIn(BaseModel):
    """Credenciales de inicio de sesión."""

    email: EmailStr
    password: str


class TokenOut(BaseModel):
    """Respuesta del login: token de sesión y rol del usuario."""

    access_token: str
    token_type: str = "bearer"
    rol: str


class PaqueteIn(BaseModel):
    """Datos para cargar un paquete turístico (jefe de ventas)."""

    codigo_paquete: str = Field(min_length=1, max_length=20)
    titulo: str = Field(min_length=1, max_length=150)
    descripcion: str | None = None
    tipo_paquete: str | None = None
    precio_total: Decimal = Field(ge=0)
    cantidad_noches: int = Field(gt=0)
    id_ubi_destino: int
    id_hotel: int | None = None
    id_vuelo: int | None = None
    id_seguro_medico: int | None = None
