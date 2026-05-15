from __future__ import annotations
import asyncio
import json
import os
from typing import Optional

import aio_pika
from fastapi import FastAPI

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")

app = FastAPI(title="CitaYa — Analíticas Service", version="2.0.0")

_mq_conn: aio_pika.abc.AbstractConnection | None = None
_consumer_task: asyncio.Task | None = None


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

# Contadores en vivo que se actualizan con cada evento de RabbitMQ
# Valores iniciales corresponden a los datos semilla (r1, r2, r3)
_stats: dict = {
    "totalReservas": 3,
    "completadas": 1,
    "canceladas": 0,
    "pendientes": 2,
}


# ---------- consumidor RabbitMQ ----------

async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        try:
            payload = json.loads(message.body)
            rk = message.routing_key
            if rk == "reserva.creada":
                _stats["totalReservas"] += 1
                _stats["pendientes"] += 1
            elif rk == "reserva.cancelada":
                _stats["canceladas"] += 1
                _stats["pendientes"] = max(0, _stats["pendientes"] - 1)
            elif rk == "reserva.completada":
                _stats["completadas"] += 1
                _stats["pendientes"] = max(0, _stats["pendientes"] - 1)
            print(f"[analiticas] evento recibido → {rk}: {payload.get('id', '?')} | stats={_stats}")
        except Exception as e:
            print(f"[analiticas] error procesando mensaje: {e}")


async def _start_consumer() -> None:
    global _mq_conn
    for attempt in range(15):
        try:
            _mq_conn = await aio_pika.connect_robust(RABBITMQ_URL)
            channel = await _mq_conn.channel()
            await channel.set_qos(prefetch_count=10)
            exchange = await channel.declare_exchange(
                "citaya", aio_pika.ExchangeType.TOPIC, durable=True
            )
            queue = await channel.declare_queue("analiticas.reservas", durable=True)
            await queue.bind(exchange, routing_key="reserva.*")
            await queue.consume(_on_message)
            print("[analiticas] consumidor RabbitMQ activo — escuchando reserva.*")
            return
        except Exception as e:
            print(f"[analiticas] esperando RabbitMQ (intento {attempt + 1}/15): {e}")
            await asyncio.sleep(3)


# ---------- startup / shutdown ----------

@app.on_event("startup")
async def startup() -> None:
    global _consumer_task
    _consumer_task = asyncio.create_task(_start_consumer())


@app.on_event("shutdown")
async def shutdown() -> None:
    if _consumer_task:
        _consumer_task.cancel()
    if _mq_conn and not _mq_conn.is_closed:
        await _mq_conn.close()


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


@app.get("/reportes/reservas", tags=["reportes"], summary="Estadísticas en tiempo real (actualizado por eventos)")
def reporte_reservas(negocioId: Optional[str] = None) -> dict:
    total = _stats["totalReservas"]
    comp  = _stats["completadas"]
    canc  = _stats["canceladas"]
    pend  = _stats["pendientes"]
    return {
        "negocioId": negocioId or "todos",
        "totalReservas": total,
        "completadas": comp,
        "canceladas": canc,
        "pendientes": pend,
        "tasaCancelacion":  f"{canc / total * 100:.1f}%" if total > 0 else "0.0%",
        "tasaCompletacion": f"{comp / total * 100:.1f}%" if total > 0 else "0.0%",
        "fuente": "eventos RabbitMQ (tiempo real)",
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
    connected = _mq_conn is not None and not _mq_conn.is_closed
    return {
        "status": "ok",
        "service": "analiticas",
        "rabbitmq": connected,
        "stats": _stats,
    }
