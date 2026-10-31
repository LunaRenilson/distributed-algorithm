from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status

from app import db
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pools()
    yield
    await db.close_pools()


app = FastAPI(title="MC714 Tickets API", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready(response: Response):
    nodes = await db.ping_all_nodes()
    all_ok = all(n.ok for n in nodes)
    roles_ok = (
        sum(1 for n in nodes if n.role == "primary") == 1
        and all(n.role == "replica" for n in nodes if n.host != settings.db_primary)
    )
    if not all_ok or not roles_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "ready": all_ok and roles_ok,
        "primary": settings.db_primary,
        "replicas": settings.replica_hosts,
        "nodes": [db.node_to_dict(n) for n in nodes],
    }


@app.get("/databases")
async def databases():
    nodes = await db.ping_all_nodes()
    return {
        "primary": settings.db_primary,
        "replicas": settings.replica_hosts,
        "nodes": [db.node_to_dict(n) for n in nodes],
    }
