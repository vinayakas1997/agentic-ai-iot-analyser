import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from agents.manager_agent import register as register_manager
from api.routes import manager
from api.websocket import register_ws_subscriber, websocket_endpoint
from config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_manager()
    register_ws_subscriber()
    logger.info(
        "Manager Agent backend started on port %s — scheduler disabled (planner/executor not yet implemented)",
        settings.api_port,
    )
    yield


app = FastAPI(title="Manager Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(manager.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/config")
async def config() -> dict:
    return {"user_id": settings.default_user_id}


@app.websocket("/ws")
async def ws_route(websocket: WebSocket) -> None:
    await websocket_endpoint(websocket)
