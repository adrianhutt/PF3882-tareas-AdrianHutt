from __future__ import annotations
from typing import Optional

from fastapi import FastAPI

app = FastAPI(title="CitaYa — Analíticas Service", version="1.0.0")


# ---------- datos fijos por negocio ----------

_ingresos = {
    "n1": {"negocioId": "n1", "nombre": "Barbería El Corte",      "total": 485000, "reservasCompletadas": 42, "promedioReserva": 11547},
    "n2": {"negocioId": "n2", "nombre": "Taller Mecánico Rueda",  "total": 920000, "reservasCompletadas": 38, "promedioReserva": 24210},
    "n3": {"negocioId": "n3", "nombre": "Consultorio Dra. López", "total": 1260000, "reservasCompletadas": 36, "promedioReserva": 35000},
}

_servicios_populares = [
    {"servicioId": "s4", "nombre": "Limpieza dental",  "negocioId": "n3", "reservas": 36, "ingresos": 1260000},
    {"servicioId": "s3", "nombre": "Cambio de aceite", "negocioId": "n2", "reservas": 38, "ingresos":  950000},
    {"servicioId": "s1", "nombre": "Corte clásico",    "negocioId": "n1", "reservas": 42, "ingresos":  464000},
    {"servicioId": "s2", "nombre": "Corte + barba",    "negocioId": "n1", "reservas": 13, "ingresos":  156000},
]

_horas_pico = [
    {"hora": "09:00", "reservas": 42},
    {"hora": "10:00", "reservas": 38},
    {"hora": "14:00", "reservas": 35},
    {"hora": "11:00", "reservas": 20},
    {"hora": "15:00", "reservas": 10},
]


# ---------- endpoints ----------

@app.get("/reportes/ingresos", tags=["reportes"], summary="Ingresos por negocio o totales de la plataforma")
def reporte_ingresos(negocioId: Optional[str] = None, periodo: str = "mes") -> dict:
    if negocioId:
        data = _ingresos.get(negocioId, {"total": 0, "reservasCompletadas": 0, "promedioReserva": 0})
        return {"periodo": periodo, **data}
    return {
        "periodo": periodo,
        "totalPlataforma": sum(v["total"] for v in _ingresos.values()),
        "negocios": list(_ingresos.values()),
    }


@app.get("/reportes/reservas", tags=["reportes"], summary="Estadísticas de reservas (completadas, canceladas, pendientes)")
def reporte_reservas(negocioId: Optional[str] = None) -> dict:
    return {
        "negocioId": negocioId or "todos",
        "totalReservas": 145,
        "completadas": 116,
        "canceladas": 21,
        "pendientes": 8,
        "tasaCancelacion": "14.5%",
        "tasaCompletacion": "80.0%",
    }


@app.get("/reportes/servicios", tags=["reportes"], summary="Servicios más reservados")
def servicios_populares(negocioId: Optional[str] = None) -> dict:
    servicios = _servicios_populares
    if negocioId:
        servicios = [s for s in servicios if s["negocioId"] == negocioId]
    return {"negocioId": negocioId or "todos", "servicios": servicios}


@app.get("/reportes/horas-pico", tags=["reportes"], summary="Horas con mayor volumen de reservas")
def horas_pico(negocioId: Optional[str] = None) -> dict:
    return {"negocioId": negocioId or "todos", "horasPico": _horas_pico}


# ---------- health ----------

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "service": "analiticas"}
