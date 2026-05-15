from __future__ import annotations
import asyncio
import json
import os
from typing import List, Optional

import aio_pika
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

USUARIOS_URL = os.getenv("USUARIOS_URL", "http://localhost:8001")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")

app = FastAPI(title="CitaYa — Reservas Service", version="2.0.0")

_http: httpx.AsyncClient | None = None
_mq_conn: aio_pika.abc.AbstractConnection | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


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


# ---------- startup / shutdown ----------

@app.on_event("startup")
async def startup() -> None:
    global _http, _mq_conn, _exchange
    _http = httpx.AsyncClient()
    for attempt in range(15):
        try:
            _mq_conn = await aio_pika.connect_robust(RABBITMQ_URL)
            channel = await _mq_conn.channel()
            _exchange = await channel.declare_exchange(
                "citaya", aio_pika.ExchangeType.TOPIC, durable=True
            )
            print("[reservas] conectado a RabbitMQ")
            return
        except Exception as e:
            print(f"[reservas] esperando RabbitMQ (intento {attempt + 1}/15): {e}")
            await asyncio.sleep(3)


@app.on_event("shutdown")
async def shutdown() -> None:
    if _http:
        await _http.aclose()
    if _mq_conn and not _mq_conn.is_closed:
        await _mq_conn.close()


# ---------- helpers: enriquecimiento desde Usuarios ----------

async def _graphql(query: str, variables: dict) -> dict:
    """Llama al servicio Usuarios vía GraphQL y retorna data{}."""
    try:
        r = await _http.post(
            f"{USUARIOS_URL}/graphql",
            json={"query": query, "variables": variables},
            timeout=2.0,
        )
        return r.json().get("data", {})
    except Exception:
        return {}


async def _enrich(reserva: dict) -> dict:
    """Agrega clienteNombre y negocioNombre consultando el servicio Usuarios."""
    u_data, n_data = await asyncio.gather(
        _graphql(
            "query($id: String!) { usuario(id: $id) { nombre } }",
            {"id": reserva["clienteId"]},
        ),
        _graphql(
            "query($id: String!) { negocio(id: $id) { nombre } }",
            {"id": reserva["negocioId"]},
        ),
    )
    return {
        **reserva,
        "clienteNombre": (u_data.get("usuario") or {}).get("nombre", reserva["clienteId"]),
        "negocioNombre": (n_data.get("negocio") or {}).get("nombre", reserva["negocioId"]),
    }


# ---------- helper: publicar evento RabbitMQ ----------

async def _publish(routing_key: str, payload: dict) -> None:
    if _exchange is None:
        return
    await _exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=routing_key,
    )
    print(f"[reservas] publicado → {routing_key}: {payload['id']}")


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


# ---------- endpoints: reservas (async — necesitan enriquecimiento) ----------

@app.get("/reservas", tags=["reservas"], summary="Lista reservas con nombre de cliente y negocio")
async def listar_reservas(
    clienteId: Optional[str] = None, negocioId: Optional[str] = None
) -> List[dict]:
    result = _reservas
    if clienteId:
        result = [r for r in result if r["clienteId"] == clienteId]
    if negocioId:
        result = [r for r in result if r["negocioId"] == negocioId]
    return list(await asyncio.gather(*[_enrich(r) for r in result]))


@app.get("/reservas/{id}", tags=["reservas"], summary="Obtiene una reserva con nombre de cliente y negocio")
async def obtener_reserva(id: str) -> dict:
    r = next((r for r in _reservas if r["id"] == id), None)
    if not r:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return await _enrich(r)


@app.post("/reservas", tags=["reservas"], status_code=201, summary="Crea una reserva y publica evento")
async def crear_reserva(data: CrearReservaRequest) -> dict:
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
    await _publish("reserva.creada", nueva)
    return await _enrich(nueva)


@app.patch("/reservas/{id}/cancelar", tags=["reservas"], summary="Cancela una reserva y publica evento")
async def cancelar_reserva(id: str) -> dict:
    r = next((r for r in _reservas if r["id"] == id), None)
    if not r:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    if r["estado"] in ("COMPLETADA", "CANCELADA"):
        raise HTTPException(
            status_code=400,
            detail=f"No se puede cancelar una reserva en estado {r['estado']}",
        )
    r["estado"] = "CANCELADA"
    await _publish("reserva.cancelada", r)
    return await _enrich(r)


# ---------- health ----------

@app.get("/health", tags=["health"])
def health():
    return {
        "status": "ok",
        "service": "reservas",
        "rabbitmq": _exchange is not None,
    }
