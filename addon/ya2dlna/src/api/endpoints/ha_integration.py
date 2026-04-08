import asyncio
from logging import getLogger
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core.dependencies.main_di_container import MainDIContainer
from core.device_manager import DeviceManager
from core.models.devices import (
    DeviceInfo,
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
    """Получить список всех обнаруженных устройств.

    Возвращает список устройств, обнаруженных в сети: Яндекс Станции и DLNA-рендереры.
    Устройства обновляются при каждом запросе через mDNS и UPnP.

    Ответ:
    - 200: Успешно, возвращает список объектов DeviceInfo.
    - 500: Внутренняя ошибка сервера.
    """
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Запрос списка всех устройств (HA {ha_version})")
    try:
        devices = await device_manager.discover_all()
        logger.info(f"Найдено {len(devices)} устройств (HA {ha_version})")
        return list(devices.values())
    except Exception as e:
        logger.error(f"Ошибка при получении списка устройств (HA {ha_version}): {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")


@router.get("/devices/yandex", response_model=List[YandexStation])
async def list_yandex_stations(request: Request):
    """Получить список Яндекс Станций.

    Возвращает список Яндекс Станций, обнаруженных в сети через mDNS.
    Каждая станция содержит информацию о device_id, имени, IP адресе, громкости и состоянии.

    Ответ:
    - 200: Успешно, возвращает список объектов YandexStation.
    - 500: Внутренняя ошибка сервера.
    """
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Запрос списка Яндекс Станций (HA {ha_version})")
    try:
        stations = await device_manager.discover_yandex_stations()
        logger.info(f"Найдено {len(stations)} Яндекс Станций (HA {ha_version})")
        return stations
    except Exception as e:
        logger.error(f"Ошибка при получении списка Яндекс Станций (HA {ha_version}): {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")


@router.get("/devices/dlna", response_model=List[DlnaRenderer])
async def list_dlna_renderers(request: Request):
    """Получить список DLNA-устройств.

    Возвращает список DLNA-рендереров, обнаруженных в сети через UPnP.
    Каждое устройство содержит информацию о device_id, friendly_name, URL рендерера, громкости и состоянии питания.

    Ответ:
    - 200: Успешно, возвращает список объектов DlnaRenderer.
    - 500: Внутренняя ошибка сервера.
    """
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Запрос списка DLNA-устройств (HA {ha_version})")
    try:
        renderers = await device_manager.discover_dlna_renderers()
        logger.info(f"Найдено {len(renderers)} DLNA-устройств (HA {ha_version})")
        return renderers
    except Exception as e:
        logger.error(f"Ошибка при получении списка DLNA-устройств (HA {ha_version}): {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")


@router.post("/source/{device_id}")
async def set_source(
    device_id: str,
    request: Request,
):
    """Установить активный источник звука (Яндекс Станция).

    Устанавливает активный источник для стриминга. Источником может быть Яндекс Станция,
    обнаруженная в сети. Устройство указывается через path parameter `device_id`.

    Параметры:
    - `device_id`: ID устройства, полученный из списка устройств.

    Ответ:
    - 200: Успешно, возвращает сообщение об установке источника.
    - 404: Устройство не найдено или не является Яндекс Станцией.
    - 500: Внутренняя ошибка сервера.
    """
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    device_id_normalized = device_id.upper()
    logger.info(f"Установка источника через path: {device_id_normalized} (HA {ha_version})")

    try:
        # Принудительно обновляем список устройств перед поиском
        await device_manager.discover_all()

        # Используем метод set_active_source
        success = device_manager.set_active_source(device_id_normalized)
        if not success:
            logger.warning(f"Устройство {device_id_normalized} не найдено или не является Яндекс Станцией (HA {ha_version})")
            raise HTTPException(status_code=404, detail="Устройство не найдено или не является Яндекс Станцией")
        logger.info(f"Источник установлен: {device_id_normalized} (HA {ha_version})")
        return {"message": f"Источник установлен: {device_id_normalized}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при установке источника (HA {ha_version}): {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")


@router.post("/target/{device_id}")
async def set_target(
    device_id: str,
    request: Request,
):
    """Установить активный приёмник звука (DLNA-устройство).

    Устанавливает активный приёмник для стриминга. Приёмником может быть DLNA-рендерер,
    обнаруженный в сети. Устройство указывается через path parameter `device_id`.

    Параметры:
    - `device_id`: ID устройства, полученный из списка устройств.

    Ответ:
    - 200: Успешно, возвращает сообщение об установке приёмника.
    - 404: Устройство не найдено или не является DLNA-рендерером.
    - 500: Внутренняя ошибка сервера.
    """
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    device_id_normalized = device_id.upper()
    logger.info(f"Установка приёмника через path: {device_id_normalized} (HA {ha_version})")

    try:
        # Принудительно обновляем список устройств перед поиском
        await device_manager.discover_all()

        # Используем метод set_active_target
        success = device_manager.set_active_target(device_id_normalized)
        if not success:
            logger.warning(f"Устройство {device_id_normalized} не найдено или не является DLNA-рендерером (HA {ha_version})")
            raise HTTPException(status_code=404, detail="Устройство не найдено или не является DLNA-рендерером")
        logger.info(f"Приёмник установлен: {device_id_normalized} (HA {ha_version})")
        return {"message": f"Приёмник установлен: {device_id_normalized}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при установке приёмника (HA {ha_version}): {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")


@router.get("/config", response_model=StreamingConfig)
async def get_config(request: Request):
    """Получить текущую конфигурацию стриминга.

    Возвращает текущую конфигурацию стриминга, включая активные источник и приёмник,
    настройку отключения звука на Яндекс Станции, состояние стриминга и статус.

    Ответ:
    - 200: Успешно, возвращает объект StreamingConfig.
    - 500: Внутренняя ошибка сервера.
    """
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Запрос конфигурации стриминга (HA {ha_version})")
    try:
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
    except Exception as e:
        logger.error(f"Ошибка при получении конфигурации стриминга (HA {ha_version}): {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")


@router.post("/stream/start")
async def start_streaming(
    request: Request,
    ruark_pin: Optional[str] = Query(None, description="PIN‑код для управления Ruark R5 (опционально)"),
    mute_yandex_station: Optional[bool] = Query(None, description="Отключать звук на Яндекс Станции во время трансляции (опционально)"),
):
    """Запустить стриминг с активного источника на активный приёмник.

    Запускает трансляцию аудио с активной Яндекс Станции на активный DLNA-рендерер.
    Перед запуском необходимо установить активные источник и приёмник через соответствующие эндпоинты.

    Параметры запроса (query parameters):
    - `ruark_pin`: (опционально) PIN‑код для управления Ruark R5.
    - `mute_yandex_station`: (опционально) Отключать звук на Яндекс Станции во время трансляции (по умолчанию True).

    Ответ:
    - 200: Успешно, возвращает сообщение о запуске стриминга.
    - 400: Не установлены активные источник и/или приёмник.
    - 500: Внутренняя ошибка сервера.
    """
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
    # Устанавливаем параметры стриминга
    try:
        main_stream_manager.set_streaming_params(
            ruark_pin=ruark_pin,
            mute_yandex_station=mute_yandex_station if mute_yandex_station is not None else True,
        )
        # Запускаем стриминг
        asyncio.create_task(main_stream_manager.start())
        logger.info(f"Стриминг запущен (HA {ha_version})")
        return {"message": "Стриминг запущен"}
    except Exception as e:
        logger.error(f"Ошибка при запуске стриминга (HA {ha_version}): {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")


@router.post("/stream/stop")
async def stop_streaming(request: Request):
    """Остановить стриминг.

    Останавливает текущую трансляцию аудио. Если стриминг не запущен, возвращает успех.

    Ответ:
    - 200: Успешно, возвращает сообщение об остановке стриминга.
    - 500: Внутренняя ошибка сервера.
    """
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Остановка стриминга (HA {ha_version})")
    try:
        await main_stream_manager.stop()
        logger.info(f"Стриминг остановлен (HA {ha_version})")
        return {"message": "Стриминг остановлен"}
    except Exception as e:
        logger.error(f"Ошибка при остановке стриминга (HA {ha_version}): {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")


@router.get("/stream/status")
async def get_stream_status(request: Request):
    """Получить статус стриминга.

    Возвращает текущий статус стриминга: idle (ожидание), streaming (трансляция),
    paused (пауза) или error (ошибка).

    Ответ:
    - 200: Успешно, возвращает объект с полем `status`.
    - 500: Внутренняя ошибка сервера.
    """
    ha_version = request.headers.get("X-Home-Assistant-Version", "unknown")
    logger.info(f"Запрос статуса стриминга (HA {ha_version})")
    try:
        status = main_stream_manager.get_status()
        logger.info(f"Статус стриминга: {status} (HA {ha_version})")
        return {"status": status}
    except Exception as e:
        logger.error(f"Ошибка при получении статуса стриминга (HA {ha_version}): {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")