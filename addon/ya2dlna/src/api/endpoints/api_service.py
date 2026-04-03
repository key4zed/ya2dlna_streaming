import asyncio
from logging import getLogger

from fastapi import APIRouter, HTTPException

from core.dependencies.main_di_container import MainDIContainer
from main_stream_service.main_stream_manager import MainStreamManager

logger = getLogger(__name__)

router = APIRouter()

di_container = MainDIContainer().get_container()

main_stream_manager = di_container.get(MainStreamManager)


@router.post("/stream_on")
async def stream_on():
    """API-команда для запуска стрима"""
    try:
        asyncio.create_task(main_stream_manager.start())
        logger.info("Стриминг запущен через API /stream_on")
        return {"status": "stream_on"}
    except Exception as e:
        logger.error(f"Ошибка при запуске стриминга через API /stream_on: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")


@router.post("/shutdown")
async def shutdown():
    """API-команда для остановки стрима"""
    try:
        await main_stream_manager.stop()
        logger.info("Стриминг остановлен через API /shutdown")
        return {"status": "main_service stopped"}
    except Exception as e:
        logger.error(f"Ошибка при остановке стриминга через API /shutdown: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")
