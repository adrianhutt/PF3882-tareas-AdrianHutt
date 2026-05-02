# CitaYa — Tarea #2: Implementación de APIs REST y GraphQL

Implementación de los tres microservicios identificados en la Tarea #1 usando **Python**, **FastAPI** y **Strawberry**.

| Servicio | Protocolo | Puerto | Documentación |
|---|---|---|---|
| **Usuarios** | GraphQL (Strawberry) | 8001 | http://localhost:8001/graphql |
| **Reservas** | REST (FastAPI) | 8002 | http://localhost:8002/docs |
| **Analíticas** | REST (FastAPI) | 8003 | http://localhost:8003/docs |

---

## Levantar el sistema

```bash
docker compose up --build
```

Eso es todo. Los tres servicios quedan disponibles de inmediato.

Para detenerlos:

```bash
docker compose down
```

---

## Usuarios Service — GraphQL

Playground interactivo: **http://localhost:8001/graphql**

### Queries disponibles

#### Listar todos los usuarios
```graphql
query {
  usuarios {
    id
    nombre
    correo
    tipo
    activo
  }
}
```

#### Listar solo usuarios activos
```graphql
query {
  usuarios(soloActivos: true) {
    id
    nombre
  }
}
```

#### Obtener un usuario por ID
```graphql
query {
  usuario(id: "u1") {
    id
    nombre
    correo
    activo
  }
}
```

#### Listar todos los negocios
```graphql
query {
  negocios {
    id
    nombre
    categoria
    telefono
    activo
  }
}
```

#### Filtrar negocios por categoría
```graphql
query {
  negocios(categoria: "barberia") {
    id
    nombre
  }
}
```

#### Obtener un negocio por ID
```graphql
query {
  negocio(id: "n1") {
    id
    nombre
    categoria
    correo
  }
}
```

---

## Reservas Service — REST

Swagger UI: **http://localhost:8002/docs**

### Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/servicios` | Lista todos los servicios. Filtra con `?negocioId=n1` |
| GET | `/servicios/{id}` | Obtiene un servicio por ID |
| GET | `/disponibilidad/{negocioId}` | Slots disponibles de un negocio |
| GET | `/reservas` | Lista reservas. Filtra con `?clienteId=u1` o `?negocioId=n1` |
| GET | `/reservas/{id}` | Obtiene una reserva por ID |
| POST | `/reservas` | Crea una nueva reserva |
| PATCH | `/reservas/{id}/cancelar` | Cancela una reserva |

### Ejemplo: crear una reserva

```bash
curl -X POST http://localhost:8002/reservas \
  -H "Content-Type: application/json" \
  -d '{
    "clienteId": "u1",
    "negocioId": "n1",
    "servicioId": "s1",
    "fecha": "2026-05-15",
    "hora": "10:00"
  }'
```

### Ejemplo: cancelar una reserva

```bash
curl -X PATCH http://localhost:8002/reservas/r2/cancelar
```

### Ejemplo: ver disponibilidad

```bash
curl "http://localhost:8002/disponibilidad/n1?fecha=2026-05-15"
```

---

## Analíticas Service — REST

Swagger UI: **http://localhost:8003/docs**

### Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/reportes/ingresos` | Ingresos por negocio o totales. Filtra con `?negocioId=n1&periodo=mes` |
| GET | `/reportes/reservas` | Estadísticas de reservas (completadas, canceladas, pendientes) |
| GET | `/reportes/servicios` | Servicios más reservados |
| GET | `/reportes/horas-pico` | Horas con mayor volumen de reservas |

### Ejemplos

```bash
# Ingresos totales de la plataforma
curl http://localhost:8003/reportes/ingresos

# Ingresos de un negocio específico
curl "http://localhost:8003/reportes/ingresos?negocioId=n1"

# Servicios populares
curl http://localhost:8003/reportes/servicios

# Horas pico
curl http://localhost:8003/reportes/horas-pico
```

---

## Datos de prueba incluidos

### Usuarios (`u1`, `u2`, `u3`)
| ID | Nombre | Tipo | Activo |
|---|---|---|---|
| u1 | Ana Mora | cliente | sí |
| u2 | Carlos Ruiz | cliente | sí |
| u3 | María Jiménez | cliente | no |

### Negocios (`n1`, `n2`, `n3`)
| ID | Nombre | Categoría |
|---|---|---|
| n1 | Barbería El Corte | barberia |
| n2 | Taller Mecánico Rueda | mecanico |
| n3 | Consultorio Dra. López | dentista |

### Reservas (`r1`, `r2`, `r3`)
| ID | Cliente | Negocio | Estado |
|---|---|---|---|
| r1 | u1 | n1 | CONFIRMADA |
| r2 | u2 | n2 | CREADA |
| r3 | u1 | n3 | COMPLETADA |

---

## Tecnologías

- **Python 3.12**
- **FastAPI 0.111** — framework REST
- **Strawberry 0.227** — framework GraphQL para Python
- **Uvicorn 0.29** — servidor ASGI
- **Docker + Docker Compose** — contenedores y orquestación local
