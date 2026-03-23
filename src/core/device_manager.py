import asyncio
from logging import getLogger
from typing import Dict, List, Optional

from core.config.settings import settings
from core.models.devices import (
    DeviceInfo,
    DeviceType,
    DlnaRenderer,
    YandexStation,
)
from dlna_stream_server.handlers.dlna_controller import DLNAController
from yandex_station.mdns_device_finder import DeviceFinder

logger = getLogger(__name__)


class DeviceManager:
    """Менеджер устройств для обнаружения и управления источниками и приёмниками."""

    def __init__(self) -> None:
        self._yandex_finder = DeviceFinder()
        device_name = settings.dlna_device_name or "DLNA Renderer"
        self._dlna_controller = DLNAController(device_name=device_name)
        self._devices: Dict[str, DeviceInfo] = {}
        self._active_source_id: Optional[str] = None
        self._active_target_id: Optional[str] = None

    async def discover_yandex_stations(self) -> List[YandexStation]:
        """Обнаружить Яндекс Станции в сети."""
        logger.info("Поиск Яндекс Станций...")
        self._yandex_finder.find_devices()
        # Даём время на обнаружение (можно было бы использовать callback)
        await asyncio.sleep(2)
        device = self._yandex_finder.device
        stations: List[YandexStation] = []
        if device:
            station = YandexStation(
                device_id=device.get("device_id", "unknown"),
                name=f"Yandex Station {device.get('platform', 'unknown')}",
                device_type=DeviceType.YANDEX_STATION,
                host=device.get("host", ""),
                port=device.get("port", 0),
                extra=device,
                platform=device.get("platform", "unknown"),
            )
            stations.append(station)
            self._devices[station.device_id] = station
        logger.info(f"Найдено станций: {len(stations)}")
        return stations

    async def discover_dlna_renderers(self) -> List[DlnaRenderer]:
        """Обнаружить DLNA-рендереры в сети."""
        logger.info("Поиск DLNA-устройств...")
        # Используем универсальный DLNA‑контроллер для поиска устройств
        self._dlna_controller.refresh_device()
        device = self._dlna_controller.device
        renderers: List[DlnaRenderer] = []
        if device:
            renderer = DlnaRenderer(
                device_id=device.udn,
                name=device.friendly_name,
                device_type=DeviceType.DLNA_RENDERER,
                host=self._dlna_controller.ip or "",
                port=80,
                extra={"location": device.location},
                renderer_url=device.location,
                friendly_name=device.friendly_name,
            )
            renderers.append(renderer)
            self._devices[renderer.device_id] = renderer
        logger.info(f"Найдено DLNA-устройств: {len(renderers)}")
        return renderers

    async def discover_all(self) -> Dict[str, DeviceInfo]:
        """Обнаружить все устройства."""
        await asyncio.gather(
            self.discover_yandex_stations(),
            self.discover_dlna_renderers(),
        )
        return self._devices

    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        """Получить устройство по ID."""
        return self._devices.get(device_id)

    def list_devices(
        self, device_type: Optional[DeviceType] = None
    ) -> List[DeviceInfo]:
        """Список всех устройств, опционально отфильтрованный по типу."""
        if device_type:
            return [
                d for d in self._devices.values()
                if d.device_type == device_type
            ]
        return list(self._devices.values())

    def set_active_source(self, device_id: str) -> bool:
        """Установить активный источник звука."""
        if device_id not in self._devices:
            logger.warning(f"Устройство {device_id} не найдено.")
            return False
        device = self._devices[device_id]
        if device.device_type != DeviceType.YANDEX_STATION:
            logger.warning(
                f"Устройство {device_id} не является Яндекс Станцией."
            )
            return False
        self._active_source_id = device_id
        logger.info(f"Активный источник установлен: {device.name}")
        return True

    def set_active_target(self, device_id: str) -> bool:
        """Установить активный приёмник звука."""
        if device_id not in self._devices:
            logger.warning(f"Устройство {device_id} не найдено.")
            return False
        device = self._devices[device_id]
        if device.device_type != DeviceType.DLNA_RENDERER:
            logger.warning(
                f"Устройство {device_id} не является DLNA-рендерером."
            )
            return False
        self._active_target_id = device_id
        logger.info(f"Активный приёмник установлен: {device.name}")
        return True

    def get_active_source(self) -> Optional[YandexStation]:
        """Получить активный источник."""
        if self._active_source_id:
            device = self._devices.get(self._active_source_id)
            if isinstance(device, YandexStation):
                return device
        return None

    def get_active_target(self) -> Optional[DlnaRenderer]:
        """Получить активный приёмник."""
        if self._active_target_id:
            device = self._devices.get(self._active_target_id)
            if isinstance(device, DlnaRenderer):
                return device
        return None

    def clear_active(self) -> None:
        """Сбросить активные устройства."""
        self._active_source_id = None
        self._active_target_id = None
        logger.info("Активные устройства сброшены.")