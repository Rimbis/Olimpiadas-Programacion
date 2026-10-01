"""Modelos Pydantic: definen y validan los datos que entran y salen de la API."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


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


class AdminIn(BaseModel):
    """Datos para dar de alta a un integrante del personal interno."""

    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    rol: Literal["ventas", "jefe_ventas"]


class PaqueteIn(BaseModel):
    """Datos para cargar un paquete turístico (personal interno)."""

    codigo_paquete: int = Field(gt=0)
    titulo: str = Field(min_length=1, max_length=150)
    descripcion: str = Field(min_length=1)
    tipo_paquete: str = Field(min_length=1, max_length=50)
    precio_total: Decimal = Field(ge=0)
    cantidad_noches: int = Field(gt=0)
    id_ubi_destino: int
    id_hotel: int
    id_vuelo: int
    id_seguro_medico: int


class PasajeroIn(BaseModel):
    """Un pasajero con su asiento elegido."""

    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    dni: int = Field(gt=0)
    tipo_pasajero: Literal["adulto", "menor"]
    condiciones_medicas: bool = False
    descripcion_medica: str | None = None
    fila: int = Field(gt=0)
    letra: str = Field(pattern=r"^[A-Za-z]$")

    @model_validator(mode="after")
    def _medica_coherente(self):
        """Si hay condición médica, exige que se la describa."""
        if self.condiciones_medicas and not (self.descripcion_medica or "").strip():
            raise ValueError("Describí la condición médica del pasajero")
        return self


class CompraIn(BaseModel):
    """Una compra: un paquete con uno o más pasajeros."""

    id_paquete: int
    pasajeros: list[PasajeroIn] = Field(min_length=1, max_length=9)


class ModificarCompraIn(BaseModel):
    """Nueva lista de pasajeros (con asientos) para un pedido pendiente."""

    pasajeros: list[PasajeroIn] = Field(min_length=1, max_length=9)


class UbicacionDestinoIn(BaseModel):
    """Datos para cargar una ciudad de destino/hospedaje."""

    ciudad: str = Field(min_length=1, max_length=100)
    pais: str = Field(min_length=1, max_length=100)


class AeropuertoIn(BaseModel):
    """Datos para cargar un aeropuerto."""

    ciudad: str = Field(min_length=1, max_length=100)
    pais: str = Field(min_length=1, max_length=100)
    codigo_aeropuerto: str = Field(pattern=r"^[A-Za-z]{3}$")

    @field_validator("codigo_aeropuerto")
    @classmethod
    def _mayusculas(cls, v: str) -> str:
        """Guarda el código IATA siempre en mayúsculas (ej: EZE)."""
        return v.upper()


class SeguroMedicoIn(BaseModel):
    """Datos para cargar un seguro médico."""

    nombre: str = Field(min_length=1, max_length=100)
    empresa: str = Field(min_length=1, max_length=100)


class HotelIn(BaseModel):
    """Datos para cargar un hotel (id_ubicacion = ciudad de destino)."""

    id_ubicacion: int
    nombre_hotel: str = Field(min_length=1, max_length=150)
    descripcion: str = Field(min_length=1)
    precio_noche: Decimal = Field(ge=0)
    estrellas: int = Field(ge=1, le=5)


class VueloIn(BaseModel):
    """Datos para cargar un vuelo, con sus escalas en orden (puede no tener).

    `id_destino` es la ciudad de hospedaje; origen/destino aéreo y las escalas
    son ids de `ubicacion_aeropuerto`. `cantidad_escalas` la calcula el backend.
    """

    id_ubi_aereo_origen: int
    id_ubi_aereo_destino: int
    id_destino: int
    fecha_ida: datetime
    fecha_vuelta: datetime
    clase: str = Field(min_length=1, max_length=50)
    escalas: list[int] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def _coherente(self):
        """Valida fechas, que origen y destino difieran y que las escalas sean válidas."""
        try:
            if self.fecha_vuelta <= self.fecha_ida:
                raise ValueError("La fecha de vuelta debe ser posterior a la de ida")
        except TypeError:
            raise ValueError("Usá fechas con o sin zona horaria en ambas, no mezcladas")
        if self.id_ubi_aereo_origen == self.id_ubi_aereo_destino:
            raise ValueError("El aeropuerto de origen y el de destino no pueden ser el mismo")
        if len(set(self.escalas)) != len(self.escalas):
            raise ValueError("Hay escalas repetidas")
        if {self.id_ubi_aereo_origen, self.id_ubi_aereo_destino} & set(self.escalas):
            raise ValueError("Una escala no puede ser el origen ni el destino del vuelo")
        return self


class EscalasIn(BaseModel):
    """Nueva lista de escalas (ids de aeropuerto, en orden) de un vuelo existente."""

    escalas: list[int] = Field(max_length=5)

    @model_validator(mode="after")
    def _sin_repetidas(self):
        """Impide escalas repetidas."""
        if len(set(self.escalas)) != len(self.escalas):
            raise ValueError("Hay escalas repetidas")
        return self