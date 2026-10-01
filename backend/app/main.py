"""Punto de entrada de la API de Aeroplate.

Ejecutar con:  uvicorn app.main:app --reload
Documentación automática:  http://localhost:8000/docs
"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import admin, apoyo, auth, catalogo, compras, pagos
from app.services.vencimientos import vencer_y_notificar

INTERVALO_BARRIDO = 60  # segundos entre chequeos de compras vencidas


async def _barrido_vencimientos() -> None:
    """Cada minuto vence las compras pendientes de más de 15 min (DFD 3.6)."""
    while True:
        try:
            await asyncio.to_thread(vencer_y_notificar)
        except Exception as e:
            print("ERROR barrido de vencimientos:", repr(e))
        await asyncio.sleep(INTERVALO_BARRIDO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranca el barrido de vencimientos al iniciar y lo frena al cerrar."""
    tarea = asyncio.create_task(_barrido_vencimientos())
    yield
    tarea.cancel()


app = FastAPI(title="Aeroplate API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción, limitar al dominio propio
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(catalogo.router)
app.include_router(apoyo.router)
app.include_router(compras.router)
app.include_router(pagos.router)
app.include_router(admin.router)

# El frontend (HTML/JS) se sirve desde la carpeta /frontend, en la misma URL.
# Debe montarse al final para no tapar las rutas de la API.
if os.path.isdir("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
