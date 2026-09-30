
"""Modelos Pydantic: definen y validan los datos que entran y salen de la API."""
from decimal import Decimal
from typing import Literal
 
from pydantic import BaseModel, EmailStr, Field, model_validator
 
 
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
        if self.condiciones_medicas and not (self.descripcion_medica or "").strip():
            raise ValueError("Describí la condición médica del pasajero")
        return self
 
 
class CompraIn(BaseModel):
    """Una compra: un paquete con uno o más pasajeros."""
 
    id_paquete: int
    pasajeros: list[PasajeroIn] = Field(min_length=1, max_length=9)