import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from agents.executor_agent import register as register_executor
from agents.manager_agent import register as register_manager
from agents.planner_agent import register as register_planner
from api.routes import manager, results, tasks
from api.websocket import register_ws_subscriber, websocket_endpoint
from config import get_settings
from db.db_subscriber import register as register_db_subscriber
from scheduler.worker_loop import start_worker, stop_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


def register_agents() -> None:
    register_executor()
    register_planner()
    register_manager()
    register_db_subscriber()
    register_ws_subscriber()


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_agents()
    await start_worker()
    logger.info("Manager Agent backend started on port %s", settings.api_port)
    yield
    await stop_worker()


app = FastAPI(title="Manager Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)
app.include_router(results.router)
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
