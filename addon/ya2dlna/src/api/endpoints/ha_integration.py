import asyncio
from logging import getLogger
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from core.config.settings import settings
from core.dependencies.main_di_container import MainDIContainer
from core.device_manager import DeviceManager
from core.models.devices import (
    DeviceInfo,
    DeviceType,
    DlnaRenderer,
    StreamingConfig,
    StreamingStatus,
    YandexStation,
)
from main_stream_service.main_stream_manager import MainStreamManager

logger = getLogger(__name__)

router = APIRouter(prefix="/ha", tags=["home_assistant"])

di_container = MainDIContainer().get_container()
device_manager = di_container.get(DeviceManager)
main_stream_manager = di_container.get(MainStreamManager)


@router.get("/devices", response_model=List[DeviceInfo])
async def list_devices():
    """Получить список всех обнаруженных устройств."""
    devices = await device_manager.discover_all()
    return list(devices.values())


@router.get("/devices/yandex", response_model=List[YandexStation])
async def list_yandex_stations():
    """Получить список Яндекс Станций."""
    stations = await device_manager.discover_yandex_stations()
    return stations


@router.get("/devices/dlna", response_model=List[DlnaRenderer])
async def list_dlna_renderers():
    """Получить список DLNA-устройств."""
    renderers = await device_manager.discover_dlna_renderers()
    return renderers


@router.post("/source/{device_id}")
async def set_source(device_id: str):
    """Установить активный источник звука (Яндекс Станция)."""
    success = device_manager.set_active_source(device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Устройство не найдено или не является Яндекс Станцией")
    return {"message": f"Источник установлен: {device_id}"}


@router.post("/target/{device_id}")
async def set_target(device_id: str):
    """Установить активный приёмник звука (DLNA-устройство)."""
    success = device_manager.set_active_target(device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Устройство не найдено или не является DLNA-рендерером")
    return {"message": f"Приёмник установлен: {device_id}"}


@router.get("/config", response_model=StreamingConfig)
async def get_config():
    """Получить текущую конфигурацию стриминга."""
    source = device_manager.get_active_source()
    target = device_manager.get_active_target()
    return StreamingConfig(
        source_device_id=source.device_id if source else "",
        target_device_id=target.device_id if target else "",
        mute_source=True,  # по умолчанию
        enabled=False,  # TODO: определить состояние стриминга
        current_status=StreamingStatus.IDLE,
    )


@router.post("/stream/start")
async def start_streaming(
    x_token: Optional[str] = Query(None, description="X‑Token для авторизации Яндекс.Станции (опционально)"),
    cookie: Optional[str] = Query(None, description="Cookie для авторизации Яндекс.Станции (опционально)"),
    ruark_pin: Optional[str] = Query(None, description="PIN‑код для управления Ruark R5 (опционально)"),
    mute_yandex_station: Optional[bool] = Query(None, description="Отключать звук на Яндекс Станции во время трансляции (опционально)"),
):
    """Запустить стриминг с активного источника на активный приёмник."""
    source = device_manager.get_active_source()
    target = device_manager.get_active_target()
    if not source or not target:
        raise HTTPException(
            status_code=400,
            detail="Не установлены активные источник и/или приёмник"
        )
    # Обновляем настройки, если переданы токены
    if x_token is not None:
        settings.x_token = x_token
        logger.info("✅ X‑Token обновлён (передан из интеграции)")
    if cookie is not None:
        settings.cookie = cookie
        logger.info("✅ Cookie обновлён (передан из интеграции)")
    if ruark_pin is not None:
        settings.ruark_pin = ruark_pin
        logger.info("✅ Ruark PIN обновлён (передан из интеграции)")
    if mute_yandex_station is not None:
        settings.mute_yandex_station = mute_yandex_station
        logger.info(f"✅ Mute Yandex Station обновлён: {mute_yandex_station}")
    # TODO: интегрировать с MainStreamManager для конкретных устройств
    # Пока используем существующий менеджер (который работает с предопределёнными устройствами)
    asyncio.create_task(main_stream_manager.start())
    return {"message": "Стриминг запущен"}


@router.post("/stream/stop")
async def stop_streaming():
    """Остановить стриминг."""
    await main_stream_manager.stop()
    return {"message": "Стриминг остановлен"}


@router.get("/stream/status")
async def get_stream_status():
    """Получить статус стриминга."""
    status = main_stream_manager.get_status()
    return {"status": status}