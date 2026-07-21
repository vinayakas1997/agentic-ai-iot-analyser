import asyncio
import logging

from agents.executor_agent import register as register_executor
from agents.manager_agent import register as register_manager
from agents.planner_agent import register as register_planner
from db.db_subscriber import register as register_db_subscriber
from scheduler.worker_loop import start_worker, worker_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def register_all() -> None:
    register_executor()
    register_planner()
    register_manager()
    register_db_subscriber()


async def main() -> None:
    register_all()
    await worker_loop()


if __name__ == "__main__":
    asyncio.run(main())
