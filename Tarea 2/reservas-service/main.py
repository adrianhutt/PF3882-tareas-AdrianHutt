from __future__ import annotations
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="CitaYa — Reservas Service", version="1.0.0")


# ---------- modelos de entrada ----------

class CrearReservaRequest(BaseModel):
    clienteId: str
    negocioId: str
    servicioId: str
    fecha: str   # YYYY-MM-DD
    hora: str    # HH:MM


# ---------- datos en memoria ----------

_servicios: List[dict] = [
    {"id": "s1", "negocioId": "n1", "nombre": "Corte clásico",    "duracionMinutos": 30, "precio": 8000.0},
    {"id": "s2", "negocioId": "n1", "nombre": "Corte + barba",    "duracionMinutos": 45, "precio": 12000.0},
    {"id": "s3", "negocioId": "n2", "nombre": "Cambio de aceite", "duracionMinutos": 60, "precio": 25000.0},
    {"id": "s4", "negocioId": "n3", "nombre": "Limpieza dental",  "duracionMinutos": 45, "precio": 35000.0},
]

_reservas: List[dict] = [
    {"id": "r1", "clienteId": "u1", "negocioId": "n1", "servicioId": "s1", "fecha": "2026-05-10", "hora": "09:00", "estado": "CONFIRMADA"},
    {"id": "r2", "clienteId": "u2", "negocioId": "n2", "servicioId": "s3", "fecha": "2026-05-10", "hora": "10:00", "estado": "CREADA"},
    {"id": "r3", "clienteId": "u1", "negocioId": "n3", "servicioId": "s4", "fecha": "2026-05-12", "hora": "14:00", "estado": "COMPLETADA"},
]

_disponibilidad: dict = {
    "n1": ["09:00", "09:30", "10:00", "10:30", "11:00", "14:00", "14:30", "15:00"],
    "n2": ["08:00", "09:00", "10:00", "11:00", "13:00", "14:00", "15:00"],
    "n3": ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"],
}

_next_id = 4


# ---------- endpoints: servicios ----------

@app.get("/servicios", tags=["servicios"], summary="Lista todos los servicios disponibles")
def listar_servicios(negocioId: Optional[str] = None) -> List[dict]:
    if negocioId:
        return [s for s in _servicios if s["negocioId"] == negocioId]
    return _servicios


@app.get("/servicios/{id}", tags=["servicios"], summary="Obtiene un servicio por ID")
def obtener_servicio(id: str) -> dict:
    s = next((s for s in _servicios if s["id"] == id), None)
    if not s:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    return s


# ---------- endpoints: disponibilidad ----------

@app.get("/disponibilidad/{negocioId}", tags=["disponibilidad"], summary="Slots libres de un negocio")
def obtener_disponibilidad(negocioId: str, fecha: Optional[str] = None) -> dict:
    slots = _disponibilidad.get(negocioId, [])
    return {
        "negocioId": negocioId,
        "fecha": fecha or "2026-05-10",
        "slotsDisponibles": slots,
    }


# ---------- endpoints: reservas ----------

@app.get("/reservas", tags=["reservas"], summary="Lista reservas; filtra por clienteId o negocioId")
def listar_reservas(clienteId: Optional[str] = None, negocioId: Optional[str] = None) -> List[dict]:
    result = _reservas
    if clienteId:
        result = [r for r in result if r["clienteId"] == clienteId]
    if negocioId:
        result = [r for r in result if r["negocioId"] == negocioId]
    return result


@app.get("/reservas/{id}", tags=["reservas"], summary="Obtiene una reserva por ID")
def obtener_reserva(id: str) -> dict:
    r = next((r for r in _reservas if r["id"] == id), None)
    if not r:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return r


@app.post("/reservas", tags=["reservas"], status_code=201, summary="Crea una nueva reserva")
def crear_reserva(data: CrearReservaRequest) -> dict:
    global _next_id
    nueva = {
        "id": f"r{_next_id}",
        "clienteId": data.clienteId,
        "negocioId": data.negocioId,
        "servicioId": data.servicioId,
        "fecha": data.fecha,
        "hora": data.hora,
        "estado": "CREADA",
    }
    _reservas.append(nueva)
    _next_id += 1
    return nueva


@app.patch("/reservas/{id}/cancelar", tags=["reservas"], summary="Cancela una reserva existente")
def cancelar_reserva(id: str) -> dict:
    r = next((r for r in _reservas if r["id"] == id), None)
    if not r:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    if r["estado"] in ("COMPLETADA", "CANCELADA"):
        raise HTTPException(status_code=400, detail=f"No se puede cancelar una reserva en estado {r['estado']}")
    r["estado"] = "CANCELADA"
    return r


# ---------- health ----------

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "service": "reservas"}
