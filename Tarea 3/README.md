# CitaYa — Tarea #3: Comunicación Asíncrona con Mensajería

Esta entrega parte de la **Tarea #2** e introduce dos mejoras:

1. **Comunicación síncrona entre servicios** — Reservas ahora consulta a Usuarios vía GraphQL para enriquecer sus respuestas con los nombres reales de clientes y negocios (en vez de mostrar solo los IDs).
2. **Mensajería asíncrona con RabbitMQ** — cada vez que se crea o cancela una reserva, Reservas publica un evento al _exchange_ `citaya`. Analíticas consume esos eventos y mantiene sus estadísticas actualizadas en tiempo real.

---

## Arquitectura

```
┌──────────────┐   GraphQL (HTTP)   ┌──────────────────┐
│   Reservas   │ ─────────────────► │    Usuarios      │
│  :8002       │                    │    :8001         │
│              │                    └──────────────────┘
│              │   reserva.creada   ┌──────────────────┐
│              │ ──────────────────►│                  │
│              │   reserva.cancelada│   RabbitMQ       │
└──────────────┘ ──────────────────►│   :5672 / :15672 │
                                    │                  │
┌──────────────┐   reserva.*        │                  │
│  Analíticas  │ ◄──────────────────│                  │
│  :8003       │                    └──────────────────┘
└──────────────┘
```

| Servicio    | Protocolo | Puerto | Documentación                         |
|-------------|-----------|--------|---------------------------------------|
| Usuarios    | GraphQL   | 8001   | http://localhost:8001/graphql         |
| Reservas    | REST      | 8002   | http://localhost:8002/docs            |
| Analíticas  | REST      | 8003   | http://localhost:8003/docs            |
| RabbitMQ UI | Web       | 15672  | http://localhost:15672 (guest/guest)  |

---

## Levantar el sistema

```bash
docker compose up --build
```

RabbitMQ tarda unos segundos en estar listo. Los servicios reintentan la conexión automáticamente (hasta 15 intentos cada 3 s), por lo que no es necesario esperar.

Para detener:

```bash
docker compose down
```

---

## Verificar la mensajería asíncrona

### Paso 1 — crear una reserva

```bash
curl -X POST http://localhost:8002/reservas \
  -H "Content-Type: application/json" \
  -d '{
    "clienteId": "u1",
    "negocioId": "n1",
    "servicioId": "s1",
    "fecha": "2026-06-01",
    "hora": "09:00"
  }'
```

La respuesta ahora incluye los nombres resueltos desde el servicio Usuarios:

```json
{
  "id": "r4",
  "clienteId": "u1",
  "clienteNombre": "Ana Mora",
  "negocioId": "n1",
  "negocioNombre": "Barbería El Corte",
  "servicioId": "s1",
  "fecha": "2026-06-01",
  "hora": "09:00",
  "estado": "CREADA"
}
```

### Paso 2 — verificar que Analíticas recibió el evento

```bash
curl http://localhost:8003/reportes/reservas
```

El campo `totalReservas` habrá aumentado en 1 respecto al valor inicial (3 → 4), y `pendientes` también subirá.

```json
{
  "negocioId": "todos",
  "totalReservas": 4,
  "completadas": 1,
  "canceladas": 0,
  "pendientes": 3,
  "fuente": "eventos RabbitMQ (tiempo real)"
}
```

### Paso 3 — cancelar una reserva

```bash
curl -X PATCH http://localhost:8002/reservas/r4/cancelar
```

### Paso 4 — verificar el efecto en Analíticas

```bash
curl http://localhost:8003/reportes/reservas
```

```json
{
  "totalReservas": 4,
  "completadas": 1,
  "canceladas": 1,
  "pendientes": 2,
  "fuente": "eventos RabbitMQ (tiempo real)"
}
```

### Paso 5 — inspeccionar mensajes en la UI de RabbitMQ

Abrir http://localhost:15672 (usuario: `guest`, contraseña: `guest`):

- **Exchanges** → `citaya` (tipo `topic`, durable): aquí Reservas publica.
- **Queues** → `analiticas.reservas` (durable, binding `reserva.*`): aquí Analíticas consume.
- En la pestaña **Get messages** de la cola se pueden ver los mensajes JSON publicados.

---

## Verificar el enriquecimiento síncrono

Consultar cualquier reserva existente devuelve los nombres en lugar de solo los IDs:

```bash
# Lista completa
curl http://localhost:8002/reservas

# Por cliente
curl "http://localhost:8002/reservas?clienteId=u1"

# Por ID
curl http://localhost:8002/reservas/r1
```

Respuesta de `/reservas/r1`:

```json
{
  "id": "r1",
  "clienteId": "u1",
  "clienteNombre": "Ana Mora",
  "negocioId": "n1",
  "negocioNombre": "Barbería El Corte",
  "servicioId": "s1",
  "fecha": "2026-05-10",
  "hora": "09:00",
  "estado": "CONFIRMADA"
}
```

---

## Cambios respecto a Tarea #2

| Componente       | Tarea 2                          | Tarea 3                                               |
|------------------|----------------------------------|-------------------------------------------------------|
| Reservas → GET   | Retorna solo IDs                 | Enriquece con `clienteNombre` y `negocioNombre`       |
| Reservas → POST  | Crea reserva, retorna IDs        | Crea reserva, publica `reserva.creada`, retorna nombres |
| Reservas → PATCH | Cancela reserva, retorna IDs     | Cancela reserva, publica `reserva.cancelada`, retorna nombres |
| Analíticas stats | Valores hardcodeados             | Contadores en vivo actualizados por eventos           |
| Infraestructura  | 3 contenedores                   | 4 contenedores (+ RabbitMQ)                           |

---

## Tecnologías

- **Python 3.12** + **FastAPI** + **Uvicorn**
- **Strawberry** — GraphQL en el servicio Usuarios
- **httpx** — cliente HTTP async para llamadas entre servicios
- **aio-pika** — cliente async para RabbitMQ (AMQP 0-9-1)
- **RabbitMQ 3.13** con plugin de gestión
- **Docker + Docker Compose**
