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

    def __init__(self):
        self._yandex_finder = DeviceFinder()
        # Используем имя устройства из настроек, если указано, иначе "DLNA Renderer"
        device_name = settings.dlna_device_name or "DLNA Renderer"
        self._dlna_controller = DLNAController(device_name=device_name)
        self._devices: Dict[str, DeviceInfo] = {}
        self._active_source_id: Optional[str] = None
        self._active_target_id: Optional[str] = None

    async def discover_yandex_stations(self) -> List[YandexStation]:
        """Обнаружить Яндекс Станции в сети."""
        logger.info("Поиск Яндекс Станций...")
        self._yandex_finder.find_devices()
        await asyncio.sleep(2)  # даём время на обнаружение
        device = self._yandex_finder.device
        stations = []
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
        # Используем существующий DLNAController для поиска устройств
        self._dlna_controller.refresh_device()
        device = self._dlna_controller.device
        renderers = []
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

    def find_device_by_entity_id(self, entity_id: str) -> Optional[DeviceInfo]:
        """Найти устройство по entity_id из Home Assistant."""
        # entity_id имеет формат "domain.object_id", например "media_player.yandex_station_ultraviolet"
        # или "media_player.am8_renderer"
        # Попробуем извлечь object_id (часть после последней точки)
        if "." not in entity_id:
            return None
        object_id = entity_id.split(".")[-1]
        logger.debug(f"Поиск устройства по entity_id {entity_id}, object_id={object_id}")
        
        # 1. Прямое совпадение device_id == entity_id (на случай, если передали device_id)
        if entity_id in self._devices:
            logger.debug(f"Найдено прямое совпадение device_id: {entity_id}")
            return self._devices[entity_id]
        
        # 2. Поиск по имени (name) - для Яндекс Станций name = "Yandex Station {platform}"
        #    object_id может содержать platform (например, "ultraviolet")
        for device in self._devices.values():
            device_name_normalized = device.name.lower().replace(" ", "_")
            if device_name_normalized == object_id:
                logger.debug(f"Найдено по имени: {device.name}")
                return device
            # Проверим, содержит ли object_id часть имени
            if object_id in device_name_normalized:
                logger.debug(f"Найдено по части имени: {device.name}")
                return device
        
        # 3. Для Яндекс Станций: object_id может быть platform (например, "yandexstation")
        for device in self._devices.values():
            if device.device_type == DeviceType.YANDEX_STATION:
                platform = None
                if isinstance(device, YandexStation):
                    platform = device.platform
                elif 'platform' in device.extra:
                    platform = device.extra['platform']
                if platform and object_id == platform.lower():
                    logger.debug(f"Найдено по platform: {platform}")
                    return device
        
        # 4. Для DLNA: object_id может быть friendly_name (например, "AM8 Renderer")
        for device in self._devices.values():
            if device.device_type == DeviceType.DLNA_RENDERER:
                friendly_name = None
                if isinstance(device, DlnaRenderer):
                    friendly_name = device.friendly_name
                elif 'friendly_name' in device.extra:
                    friendly_name = device.extra['friendly_name']
                if friendly_name and object_id == friendly_name.lower().replace(" ", "_"):
                    logger.debug(f"Найдено по friendly_name: {friendly_name}")
                    return device
        
        logger.warning(f"Устройство с entity_id {entity_id} не найдено. Доступные устройства: {list(self._devices.keys())}")
        return None

    def list_devices(self, device_type: Optional[DeviceType] = None) -> List[DeviceInfo]:
        """Список всех устройств, опционально отфильтрованный по типу."""
        if device_type:
            return [d for d in self._devices.values() if d.device_type == device_type]
        return list(self._devices.values())

    def set_active_source(self, device_or_entity_id: str) -> bool:
        """Установить активный источник звука."""
        # Сначала попробуем найти устройство по device_id
        device = self._devices.get(device_or_entity_id)
        if not device:
            # Если не найдено, попробуем найти по entity_id
            device = self.find_device_by_entity_id(device_or_entity_id)
            if not device:
                logger.warning(f"Устройство {device_or_entity_id} не найдено.")
                return False
        
        if device.device_type != DeviceType.YANDEX_STATION:
            logger.warning(f"Устройство {device_or_entity_id} не является Яндекс Станцией.")
            return False
        
        self._active_source_id = device.device_id
        logger.info(f"Активный источник установлен: {device.name}")
        return True

    def set_active_target(self, device_or_entity_id: str) -> bool:
        """Установить активный приёмник звука."""
        # Сначала попробуем найти устройство по device_id
        device = self._devices.get(device_or_entity_id)
        if not device:
            # Если не найдено, попробуем найти по entity_id
            device = self.find_device_by_entity_id(device_or_entity_id)
            if not device:
                logger.warning(f"Устройство {device_or_entity_id} не найдено.")
                return False
        
        if device.device_type != DeviceType.DLNA_RENDERER:
            logger.warning(f"Устройство {device_or_entity_id} не является DLNA-рендерером.")
            return False
        
        self._active_target_id = device.device_id
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

    def clear_active(self):
        """Сбросить активные устройства."""
        self._active_source_id = None
        self._active_target_id = None
        logger.info("Активные устройства сброшены.")