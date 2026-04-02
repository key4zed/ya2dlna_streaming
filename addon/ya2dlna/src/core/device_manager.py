import asyncio
from logging import getLogger
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

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


class DeviceEventType(str, Enum):
    """Типы событий устройств."""
    DEVICE_ADDED = "device_added"
    DEVICE_REMOVED = "device_removed"
    DEVICE_UPDATED = "device_updated"
    DEVICE_UNAVAILABLE = "device_unavailable"


@dataclass
class DeviceEvent:
    """Событие устройства."""
    event_type: DeviceEventType
    device: DeviceInfo
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())


DeviceCallback = Callable[[DeviceEvent], Any]


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
        self._callbacks: List[DeviceCallback] = []
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        self._last_discovery_time: float = 0.0
        self._discovery_interval: float = 30.0  # Интервал обнаружения в секундах

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
        
        # 0. Логируем все доступные устройства для отладки
        if not self._devices:
            logger.warning("Нет доступных устройств. Возможно, обнаружение ещё не выполнено.")
        else:
            logger.debug(f"Доступные устройства: {[d.name for d in self._devices.values()]}")
        
        # 1. Прямое совпадение device_id == entity_id (на случай, если передали device_id)
        if entity_id in self._devices:
            logger.debug(f"Найдено прямое совпадение device_id: {entity_id}")
            return self._devices[entity_id]
        
        # 2. Удаляем префикс "media_player." и пробуем найти по object_id
        #    Например, "yandex_station_ultraviolet" -> "ultraviolet"
        #    или "am8_renderer" -> "am8_renderer"
        #    Убираем возможные префиксы "yandex_station_", "yandex_", "station_"
        search_terms = [object_id]
        if object_id.startswith("yandex_station_"):
            search_terms.append(object_id.replace("yandex_station_", ""))
        if object_id.startswith("yandex_"):
            search_terms.append(object_id.replace("yandex_", ""))
        if object_id.startswith("station_"):
            search_terms.append(object_id.replace("station_", ""))
        
        # 3. Поиск по имени (name) - для Яндекс Станций name = "Yandex Station {platform}"
        #    object_id может содержать platform (например, "ultraviolet")
        for device in self._devices.values():
            device_name_normalized = device.name.lower().replace(" ", "_")
            
            # Проверяем все варианты поиска
            for term in search_terms:
                if device_name_normalized == term:
                    logger.debug(f"Найдено по имени: {device.name} (термин: {term})")
                    return device
                # Проверим, содержит ли term часть имени
                if term in device_name_normalized:
                    logger.debug(f"Найдено по части имени: {device.name} (термин: {term})")
                    return device
        
        # 4. Для Яндекс Станций: object_id может быть platform (например, "ultraviolet")
        for device in self._devices.values():
            if device.device_type == DeviceType.YANDEX_STATION:
                platform = None
                if isinstance(device, YandexStation):
                    platform = device.platform
                elif 'platform' in device.extra:
                    platform = device.extra['platform']
                if platform:
                    platform_normalized = platform.lower()
                    for term in search_terms:
                        if platform_normalized == term:
                            logger.debug(f"Найдено по platform: {platform} (термин: {term})")
                            return device
                        if term in platform_normalized:
                            logger.debug(f"Найдено по части platform: {platform} (термин: {term})")
                            return device
        
        # 5. Для DLNA: object_id может быть friendly_name (например, "AM8 Renderer")
        for device in self._devices.values():
            if device.device_type == DeviceType.DLNA_RENDERER:
                friendly_name = None
                if isinstance(device, DlnaRenderer):
                    friendly_name = device.friendly_name
                elif 'friendly_name' in device.extra:
                    friendly_name = device.extra['friendly_name']
                if friendly_name:
                    friendly_name_normalized = friendly_name.lower().replace(" ", "_")
                    for term in search_terms:
                        if friendly_name_normalized == term:
                            logger.debug(f"Найдено по friendly_name: {friendly_name} (термин: {term})")
                            return device
                        if term in friendly_name_normalized:
                            logger.debug(f"Найдено по части friendly_name: {friendly_name} (термин: {term})")
                            return device
        
        # 6. Дополнительно: поиск по hostname или IP
        for device in self._devices.values():
            if device.host and object_id in device.host:
                logger.debug(f"Найдено по host: {device.host}")
                return device
        
        logger.warning(f"Устройство с entity_id {entity_id} не найдено. Доступные устройства: {[(d.name, d.device_type.value) for d in self._devices.values()]}")
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

    # Методы для мониторинга устройств
    def add_callback(self, callback: DeviceCallback) -> None:
        """Добавить callback для получения событий устройств."""
        self._callbacks.append(callback)
        logger.debug(f"Добавлен callback для событий устройств. Всего callbacks: {len(self._callbacks)}")

    def remove_callback(self, callback: DeviceCallback) -> None:
        """Удалить callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger.debug(f"Удалён callback для событий устройств. Осталось callbacks: {len(self._callbacks)}")

    def _notify_callbacks(self, event: DeviceEvent) -> None:
        """Уведомить все зарегистрированные callbacks о событии."""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Ошибка в callback при обработке события {event.event_type}: {e}")

    async def _perform_discovery(self) -> Dict[str, DeviceInfo]:
        """Выполнить обнаружение устройств и вернуть новый словарь устройств."""
        old_devices = self._devices.copy()
        await self.discover_all()
        new_devices = self._devices
        
        # Определяем изменения
        added = {device_id: device for device_id, device in new_devices.items()
                 if device_id not in old_devices}
        removed = {device_id: device for device_id, device in old_devices.items()
                   if device_id not in new_devices}
        
        # Уведомляем о добавленных устройствах
        for device_id, device in added.items():
            logger.info(f"Устройство добавлено: {device.name} ({device_id})")
            self._notify_callbacks(DeviceEvent(
                event_type=DeviceEventType.DEVICE_ADDED,
                device=device
            ))
        
        # Уведомляем об удалённых устройствах
        for device_id, device in removed.items():
            logger.info(f"Устройство удалено: {device.name} ({device_id})")
            self._notify_callbacks(DeviceEvent(
                event_type=DeviceEventType.DEVICE_REMOVED,
                device=device
            ))
            
            # Если удалённое устройство было активным, сбрасываем активное устройство
            if device_id == self._active_source_id:
                logger.warning(f"Активный источник {device.name} удалён. Сбрасываем активный источник.")
                self._active_source_id = None
            if device_id == self._active_target_id:
                logger.warning(f"Активный приёмник {device.name} удалён. Сбрасываем активный приёмник.")
                self._active_target_id = None
        
        return new_devices

    async def start_monitoring(self, interval: float = None) -> None:
        """Запустить фоновый мониторинг устройств."""
        if self._is_monitoring:
            logger.warning("Мониторинг устройств уже запущен.")
            return
        
        if interval is not None:
            self._discovery_interval = interval
        
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"Мониторинг устройств запущен с интервалом {self._discovery_interval} секунд.")

    async def stop_monitoring(self) -> None:
        """Остановить фоновый мониторинг устройств."""
        if not self._is_monitoring:
            return
        
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        logger.info("Мониторинг устройств остановлен.")

    async def _monitoring_loop(self) -> None:
        """Фоновый цикл мониторинга устройств."""
        logger.info("Запущен цикл мониторинга устройств.")
        try:
            while self._is_monitoring:
                try:
                    await self._perform_discovery()
                except Exception as e:
                    logger.error(f"Ошибка при обнаружении устройств: {e}")
                
                # Ждём перед следующим обнаружением
                await asyncio.sleep(self._discovery_interval)
        except asyncio.CancelledError:
            logger.info("Цикл мониторинга устройств отменён.")
        except Exception as e:
            logger.error(f"Неожиданная ошибка в цикле мониторинга: {e}")
        finally:
            self._is_monitoring = False
            logger.info("Цикл мониторинга устройств завершён.")

    def is_device_available(self, device_id: str) -> bool:
        """Проверить, доступно ли устройство."""
        return device_id in self._devices

    def get_device_status(self, device_id: str) -> Optional[str]:
        """Получить статус устройства."""
        if device_id not in self._devices:
            return "not_found"
        
        device = self._devices[device_id]
        # Для DLNA-устройств можно проверить доступность через контроллер
        if device.device_type == DeviceType.DLNA_RENDERER:
            # Проверяем, инициализирован ли контроллер и доступно ли устройство
            if self._dlna_controller.device is None:
                return "unavailable"
            # Можно добавить ping или проверку соединения
            return "available"
        elif device.device_type == DeviceType.YANDEX_STATION:
            # Для Яндекс Станций проверяем наличие в сети
            return "available"  # Упрощённо, можно добавить ping
        
        return "unknown"