import asyncio
from logging import getLogger
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

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
async def list_devices(request: Request):
    """Получить список всех обнаруженных устройств."""
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Запрос списка всех устройств (HA {ha_version})")
    devices = await device_manager.discover_all()
    logger.info(f"Найдено {len(devices)} устройств (HA {ha_version})")
    return list(devices.values())


@router.get("/devices/yandex", response_model=List[YandexStation])
async def list_yandex_stations(request: Request):
    """Получить список Яндекс Станций."""
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Запрос списка Яндекс Станций (HA {ha_version})")
    stations = await device_manager.discover_yandex_stations()
    logger.info(f"Найдено {len(stations)} Яндекс Станций (HA {ha_version})")
    return stations


@router.get("/devices/dlna", response_model=List[DlnaRenderer])
async def list_dlna_renderers(request: Request):
    """Получить список DLNA-устройств."""
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Запрос списка DLNA-устройств (HA {ha_version})")
    renderers = await device_manager.discover_dlna_renderers()
    logger.info(f"Найдено {len(renderers)} DLNA-устройств (HA {ha_version})")
    return renderers


@router.post("/source/{device_id}")
async def set_source(device_id: str, request: Request):
    """Установить активный источник звука (Яндекс Станция)."""
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Установка источника {device_id} (HA {ha_version})")
    # Принудительно обновляем список устройств перед поиском
    await device_manager.discover_all()
    success = device_manager.set_active_source(device_id)
    if not success:
        logger.warning(f"Устройство {device_id} не найдено или не является Яндекс Станцией (HA {ha_version})")
        raise HTTPException(status_code=404, detail="Устройство не найдено или не является Яндекс Станцией")
    logger.info(f"Источник установлен: {device_id} (HA {ha_version})")
    return {"message": f"Источник установлен: {device_id}"}


@router.post("/target/{device_id}")
async def set_target(device_id: str, request: Request):
    """Установить активный приёмник звука (DLNA-устройство)."""
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Установка приёмника {device_id} (HA {ha_version})")
    # Принудительно обновляем список устройств перед поиском
    await device_manager.discover_all()
    success = device_manager.set_active_target(device_id)
    if not success:
        logger.warning(f"Устройство {device_id} не найдено или не является DLNA-рендерером (HA {ha_version})")
        raise HTTPException(status_code=404, detail="Устройство не найдено или не является DLNA-рендерером")
    logger.info(f"Приёмник установлен: {device_id} (HA {ha_version})")
    return {"message": f"Приёмник установлен: {device_id}"}


@router.get("/config", response_model=StreamingConfig)
async def get_config(request: Request):
    """Получить текущую конфигурацию стриминга."""
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Запрос конфигурации стриминга (HA {ha_version})")
    source = device_manager.get_active_source()
    target = device_manager.get_active_target()
    logger.info(f"Активный источник: {source.device_id if source else 'нет'}, приёмник: {target.device_id if target else 'нет'} (HA {ha_version})")
    return StreamingConfig(
        source_device_id=source.device_id if source else "",
        target_device_id=target.device_id if target else "",
        mute_source=True,  # по умолчанию
        enabled=False,  # TODO: определить состояние стриминга
        current_status=StreamingStatus.IDLE,
    )


@router.post("/stream/start")
async def start_streaming(
    request: Request,
    x_token: Optional[str] = Query(None, description="X‑Token для авторизации Яндекс.Станции (опционально)"),
    cookie: Optional[str] = Query(None, description="Cookie для авторизации Яндекс.Станции (опционально)"),
    ruark_pin: Optional[str] = Query(None, description="PIN‑код для управления Ruark R5 (опционально)"),
    mute_yandex_station: Optional[bool] = Query(None, description="Отключать звук на Яндекс Станции во время трансляции (опционально)"),
):
    """Запустить стриминг с активного источника на активный приёмник."""
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Запуск стриминга (HA {ha_version})")
    source = device_manager.get_active_source()
    target = device_manager.get_active_target()
    if not source or not target:
        logger.warning(f"Не установлены активные источник и/или приёмник (HA {ha_version})")
        raise HTTPException(
            status_code=400,
            detail="Не установлены активные источник и/или приёмник"
        )
    # Обновляем настройки, если переданы токены
    if x_token is not None:
        settings.x_token = x_token
        logger.info(f"✅ X‑Token обновлён (передан из интеграции) (HA {ha_version})")
    if cookie is not None:
        settings.cookie = cookie
        logger.info(f"✅ Cookie обновлён (передан из интеграции) (HA {ha_version})")
    if ruark_pin is not None:
        settings.ruark_pin = ruark_pin
        logger.info(f"✅ Ruark PIN обновлён (передан из интеграции) (HA {ha_version})")
    if mute_yandex_station is not None:
        settings.mute_yandex_station = mute_yandex_station
        logger.info(f"✅ Mute Yandex Station обновлён: {mute_yandex_station} (HA {ha_version})")
    # TODO: интегрировать с MainStreamManager для конкретных устройств
    # Пока используем существующий менеджер (который работает с предопределёнными устройствами)
    asyncio.create_task(main_stream_manager.start())
    logger.info(f"Стриминг запущен (HA {ha_version})")
    return {"message": "Стриминг запущен"}


@router.post("/stream/stop")
async def stop_streaming(request: Request):
    """Остановить стриминг."""
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Остановка стриминга (HA {ha_version})")
    await main_stream_manager.stop()
    logger.info(f"Стриминг остановлен (HA {ha_version})")
    return {"message": "Стриминг остановлен"}


@router.get("/stream/status")
async def get_stream_status(request: Request):
    """Получить статус стриминга."""
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Запрос статуса стриминга (HA {ha_version})")
    status = main_stream_manager.get_status()
    logger.info(f"Статус стриминга: {status} (HA {ha_version})")
    return {"status": status}