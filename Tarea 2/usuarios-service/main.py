from __future__ import annotations
from typing import List, Optional

import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter


@strawberry.type
class Usuario:
    id: str
    nombre: str
    correo: str
    tipo: str   # "cliente" | "negocio"
    activo: bool


@strawberry.type
class Negocio:
    id: str
    nombre: str
    categoria: str
    correo: str
    telefono: str
    activo: bool


_usuarios: List[Usuario] = [
    Usuario(id="u1", nombre="Ana Mora",      correo="ana@citaya.com",    tipo="cliente", activo=True),
    Usuario(id="u2", nombre="Carlos Ruiz",   correo="carlos@citaya.com", tipo="cliente", activo=True),
    Usuario(id="u3", nombre="María Jiménez", correo="maria@citaya.com",  tipo="cliente", activo=False),
]

_negocios: List[Negocio] = [
    Negocio(id="n1", nombre="Barbería El Corte",       categoria="barberia", correo="corte@citaya.com", telefono="8888-0001", activo=True),
    Negocio(id="n2", nombre="Taller Mecánico Rueda",   categoria="mecanico", correo="rueda@citaya.com", telefono="8888-0002", activo=True),
    Negocio(id="n3", nombre="Consultorio Dra. López",  categoria="dentista", correo="lopez@citaya.com", telefono="8888-0003", activo=True),
]


@strawberry.type
class Query:
    @strawberry.field(description="Retorna un usuario por su ID")
    def usuario(self, id: str) -> Optional[Usuario]:
        return next((u for u in _usuarios if u.id == id), None)

    @strawberry.field(description="Lista todos los usuarios; usa soloActivos=true para filtrar")
    def usuarios(self, solo_activos: bool = False) -> List[Usuario]:
        if solo_activos:
            return [u for u in _usuarios if u.activo]
        return _usuarios

    @strawberry.field(description="Retorna un negocio por su ID")
    def negocio(self, id: str) -> Optional[Negocio]:
        return next((n for n in _negocios if n.id == id), None)

    @strawberry.field(description="Lista todos los negocios; filtra por categoria si se indica")
    def negocios(self, categoria: Optional[str] = None) -> List[Negocio]:
        if categoria:
            return [n for n in _negocios if n.categoria == categoria]
        return _negocios


schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)

app = FastAPI(title="CitaYa — Usuarios Service", version="1.0.0")
app.include_router(graphql_app, prefix="/graphql")


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "service": "usuarios"}
