"""Punto de entrada de la API de Aeroplate.

Ejecutar con:  uvicorn app.main:app --reload
Documentación automática:  http://localhost:8000/docs
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import admin, auth, catalogo, compras

app = FastAPI(title="Aeroplate API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción, limitar al dominio propio
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(catalogo.router)
app.include_router(compras.router)
app.include_router(admin.router)
# TODO: routers de pagos y notificaciones.

# El frontend (HTML/JS) se sirve desde la carpeta /frontend, en la misma URL.
# Debe montarse al final para no tapar las rutas de la API.
if os.path.isdir("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")