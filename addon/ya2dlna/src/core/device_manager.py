import asyncio
import ipaddress
import re
import subprocess
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


def get_mac_address(ip_address: str) -> Optional[str]:
    """
    Получить MAC-адрес по IP-адресу, используя ARP-таблицу.
    
    Args:
        ip_address: IP-адрес устройства
        
    Returns:
        MAC-адрес в формате "aa:bb:cc:dd:ee:ff" или None, если не найден
    """
    if not ip_address:
        return None
    
    try:
        # Чтение ARP-таблицы из /proc/net/arp
        with open('/proc/net/arp', 'r') as f:
            lines = f.readlines()
        
        # Пропускаем заголовок
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 4:
                ip = parts[0]
                mac = parts[3]
                if ip == ip_address and mac != '00:00:00:00:00:00':
                    return mac.lower()
    except Exception as e:
        logger.debug(f"Не удалось прочитать ARP-таблицу для IP {ip_address}: {e}")
    
    # Альтернативный метод: использование команды arp
    try:
        import subprocess
        result = subprocess.run(['arp', '-n', ip_address], capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            # Ищем MAC-адрес в выводе
            lines = result.stdout.split('\n')
            for line in lines:
                if ip_address in line:
                    # Разбираем строку вида "192.168.1.1 ether aa:bb:cc:dd:ee:ff"
                    match = re.search(r'([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})', line)
                    if match:
                        return match.group(0).lower()
    except Exception as e:
        logger.debug(f"Не удалось выполнить команду arp для IP {ip_address}: {e}")
    
    return None


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

    def __init__(self, dlna_controller: Optional[DLNAController] = None):
        self._yandex_finder = DeviceFinder()
        # Используем фиксированное имя устройства "DLNA Renderer"
        device_name = "DLNA Renderer"
        if dlna_controller is None:
            self._dlna_controller = DLNAController(device_name=device_name)
        else:
            self._dlna_controller = dlna_controller
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
        devices = self._yandex_finder.devices
        stations = []
        for device in devices:
            host = device.get("host", "")
            logger.debug(f"Найдена Яндекс Станция: host={host}, device={device}")
            
            # Получаем MAC-адрес по IP
            mac_address = ""
            if host:
                mac = get_mac_address(host)
                if mac:
                    mac_address = mac
                    logger.debug(f"Найден MAC-адрес для Яндекс Станции {host}: {mac}")
                else:
                    logger.debug(f"MAC-адрес для Яндекс Станции {host} не найден")
            
            station = YandexStation(
                device_id=device.get("device_id", "unknown"),
                name=f"Yandex Station {device.get('platform', 'unknown')}",
                device_type=DeviceType.YANDEX_STATION,
                host=host,
                port=device.get("port", 0),
                ip_address=host,  # Используем host как IP адрес
                mac_address=mac_address,
                extra=device,
                platform=device.get("platform", "unknown"),
            )
            stations.append(station)
            self._devices[station.device_id] = station
            logger.debug(f"Добавлена Яндекс Станция: {station.name} (ID: {station.device_id})")
        if not stations:
            logger.debug("Яндекс Станции не найдены")
        logger.info(f"Найдено Яндекс Станций: {len(stations)}")
        return stations

    def _is_renderer(self, device) -> bool:
        """Проверить, является ли UPnP устройство DLNA-рендерером (имеет сервис AVTransport)."""
        try:
            # Проверяем наличие сервиса AVTransport (urn:schemas-upnp-org:service:AVTransport:1)
            for service in device.services:
                if 'AVTransport' in service.service_type:
                    return True
            return False
        except Exception:
            return False

    async def discover_dlna_renderers(self) -> List[DlnaRenderer]:
        """Обнаружить DLNA-рендереры в сети."""
        logger.info("Поиск DLNA-устройств...")
        import upnpclient
        
        try:
            devices = upnpclient.discover()
            logger.info(f"Найдено {len(devices)} UPnP устройств в сети")

            for i, d in enumerate(devices):
                logger.debug(f"Устройство {i}: friendly_name={d.friendly_name}, udn={d.udn}, location={d.location}")
        except Exception as e:
            logger.error(f"Ошибка при обнаружении DLNA устройств: {e}")
            devices = []
        
        renderers = []
        for device in devices:
            try:
                # Пропускаем не-рендереры
                if not self._is_renderer(device):
                    logger.debug(f"Устройство {device.friendly_name} не является DLNA-рендерером, пропускаем")
                    continue
                
                # Получаем IP адрес из location URL
                location = device.location
                if not location:
                    logger.warning(f"У устройства {device.friendly_name} отсутствует location, пропускаем")
                    continue
                import urllib.parse
                parsed = urllib.parse.urlparse(location)
                ip_address = parsed.hostname if parsed.hostname else ""
                
                # Получаем MAC-адрес по IP
                mac_address = ""
                if ip_address:
                    mac = get_mac_address(ip_address)
                    if mac:
                        mac_address = mac
                        logger.debug(f"Найден MAC-адрес для DLNA устройства {ip_address}: {mac}")
                    else:
                        logger.debug(f"MAC-адрес для DLNA устройства {ip_address} не найден")
                
                renderer = DlnaRenderer(
                    device_id=device.udn,
                    name=device.friendly_name,
                    device_type=DeviceType.DLNA_RENDERER,
                    host=ip_address,
                    port=parsed.port or 80,
                    ip_address=ip_address,
                    mac_address=mac_address,
                    extra={"location": location},
                    renderer_url=location,
                    friendly_name=device.friendly_name,
                )
                renderers.append(renderer)
                self._devices[renderer.device_id] = renderer
                logger.debug(f"Добавлено DLNA устройство: {device.friendly_name} ({device.udn})")
            except Exception as e:
                logger.error(f"Ошибка при обработке DLNA устройства {device.friendly_name}: {e}", exc_info=True)
                continue
        
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

    def find_device_by_entity_id(
        self,
        entity_id: str,
        ip_address: Optional[str] = None,
        mac_addresses: Optional[List[str]] = None,
        platform: Optional[str] = None,
        friendly_name: Optional[str] = None,
    ) -> Optional[DeviceInfo]:
        """Найти устройство по entity_id из Home Assistant с дополнительными данными.
        
        Поиск выполняется в следующем порядке приоритета:
        1. По device_id (для всех устройств) - если entity_id совпадает с device_id
        2. По device_id из entity_id (для Яндекс Станций) - извлекается из entity_id
        3. По device_id из entity_id (для DLNA устройств) - извлекается из entity_id
        """
        logger.debug(f"Поиск устройства по entity_id {entity_id}, IP={ip_address}, MAC={mac_addresses}, friendly_name={friendly_name}")
        
        # 0. Логируем все доступные устройства для отладки
        if not self._devices:
            logger.warning("Нет доступных устройств. Возможно, обнаружение ещё не выполнено.")
        else:
            logger.debug(f"Доступные устройства: {[d.name for d in self._devices.values()]}")
        
        # 1. Прямой поиск по device_id (entity_id может быть самим device_id)
        # Приводим к верхнему регистру для регистронезависимого сравнения
        entity_id_upper = entity_id.upper()
        for dev in self._devices.values():
            if dev.device_id.upper() == entity_id_upper:
                logger.debug(f"Найдено устройство по прямому совпадению device_id: {dev.name}")
                return dev
        
        # Определяем тип устройства по entity_id (если можно) для ускорения поиска
        device_type = None
        if "yandex_station" in entity_id.lower() or "yandex" in entity_id.lower():
            device_type = DeviceType.YANDEX_STATION
        elif "dlna" in entity_id.lower() or "renderer" in entity_id.lower():
            device_type = DeviceType.DLNA_RENDERER
        
        # 2. Поиск по device_id из entity_id (для Яндекс Станций)
        if device_type == DeviceType.YANDEX_STATION:
            # Пробуем извлечь device_id из entity_id (формат: media_player.yandex_station_<device_id>)
            parts = entity_id.split('_')
            if len(parts) > 1:
                possible_device_id = parts[-1]
                if len(possible_device_id) == 32:  # Длина device_id Яндекс Станции
                    # Поиск без учёта регистра
                    possible_device_id_upper = possible_device_id.upper()
                    for dev in self._devices.values():
                        if dev.device_id.upper() == possible_device_id_upper:
                            logger.debug(f"Найдено устройство по device_id из entity_id (без учёта регистра): {dev.name}")
                            return dev
        
        # 3. Поиск по device_id из entity_id (для DLNA устройств)
        if device_type == DeviceType.DLNA_RENDERER:
            # Пробуем извлечь device_id из entity_id (формат: media_player.dlna_renderer_<device_id>)
            parts = entity_id.split('_')
            if len(parts) > 1:
                possible_device_id = parts[-1]
                # Поиск без учёта регистра
                possible_device_id_upper = possible_device_id.upper()
                for dev in self._devices.values():
                    if dev.device_id.upper() == possible_device_id_upper:
                        logger.debug(f"Найдено DLNA устройство по device_id из entity_id: {dev.name}")
                        return dev
        
        logger.warning(f"Устройство с entity_id {entity_id} не найдено. Доступные устройства: {[(d.name, d.device_type.value, d.device_id[:20]) for d in self._devices.values()]}")
        return None

    def _find_device_by_ip_mac(
        self,
        ip_address: Optional[str] = None,
        mac_addresses: Optional[List[str]] = None,
        device_type: Optional[DeviceType] = None,
    ) -> Optional[DeviceInfo]:
        """Найти устройство по IP и/или MAC адресу(ам)."""
        if not ip_address and not mac_addresses:
            return None
        
        # Нормализуем MAC-адреса для сравнения
        normalized_mac_addresses = None
        if mac_addresses:
            normalized_mac_addresses = [self._normalize_mac(mac) for mac in mac_addresses if mac]
            logger.debug(f"Нормализованные MAC-адреса для поиска: {normalized_mac_addresses} (исходные: {mac_addresses})")
        
        logger.debug(f"Поиск устройства по IP {ip_address}, MAC {mac_addresses}, тип {device_type}. Всего устройств: {len(self._devices)}")
        
        for device in self._devices.values():
            if device_type and device.device_type != device_type:
                logger.debug(f"Пропускаем устройство {device.name} из-за несовпадения типа: {device.device_type} != {device_type}")
                continue
            
            # Сравнение IP адреса (только IPv4)
            if ip_address and device.ip_address:
                # Проверяем, что IP адрес устройства является IPv4
                if not self._is_ipv4(device.ip_address):
                    logger.debug(f"IP адрес устройства {device.name} не является IPv4: {device.ip_address}")
                    continue
                # Простое сравнение строк (может быть IPv4 или hostname)
                if ip_address == device.ip_address:
                    logger.debug(f"Найдено устройство по IP адресу: {device.name} (IP: {ip_address})")
                    return device
                else:
                    logger.debug(f"IP не совпадает: {ip_address} != {device.ip_address}")
            
            # Сравнение MAC адресов с нормализацией
            if normalized_mac_addresses and device.mac_address:
                # Нормализуем MAC-адрес устройства
                normalized_device_mac = self._normalize_mac(device.mac_address)
                logger.debug(f"Нормализованный MAC-адрес устройства {device.name}: {normalized_device_mac} (исходный: {device.mac_address})")
                for normalized_mac in normalized_mac_addresses:
                    if normalized_mac == normalized_device_mac:
                        logger.debug(f"Найдено устройство по MAC адресу: {device.name} (MAC: {normalized_mac})")
                        return device
            elif normalized_mac_addresses:
                logger.debug(f"У устройства {device.name} нет MAC-адреса")
        
        logger.debug(f"Устройство по IP {ip_address} или MAC {mac_addresses} не найдено")
        return None

    def _is_ipv4(self, ip_str: str) -> bool:
        """Проверить, является ли строка IPv4 адресом."""
        try:
            ipaddress.IPv4Address(ip_str)
            return True
        except (ipaddress.AddressValueError, ValueError):
            return False

    def _normalize_mac(self, mac: str) -> str:
        """Нормализовать MAC-адрес: привести к нижнему регистру и удалить разделители."""
        if not mac:
            return mac
        import re
        mac_clean = re.sub(r'[^a-fA-F0-9]', '', mac)
        mac_clean = mac_clean.lower()
        return mac_clean

    def _find_device_by_friendly_name(
        self,
        friendly_name: str,
        device_type: Optional[DeviceType] = None,
    ) -> Optional[DeviceInfo]:
        """Найти устройство по friendly_name (для DLNA устройств)."""
        if not friendly_name:
            return None
        
        logger.debug(f"Поиск устройства по friendly_name: {friendly_name}, тип: {device_type}")
        friendly_name_upper = friendly_name.upper()
        
        for device in self._devices.values():
            if device_type and device.device_type != device_type:
                continue
            
            # Для DLNA устройств проверяем friendly_name
            if isinstance(device, DlnaRenderer) and device.friendly_name:
                device_friendly_upper = device.friendly_name.upper()
                # Точное совпадение
                if device_friendly_upper == friendly_name_upper:
                    logger.debug(f"Найдено устройство по точному совпадению friendly_name: {device.name}")
                    return device
                # Частичное совпадение (содержит)
                if friendly_name_upper in device_friendly_upper or device_friendly_upper in friendly_name_upper:
                    logger.debug(f"Найдено устройство по частичному совпадению friendly_name: {device.name}")
                    return device
            
            # Также проверяем имя устройства
            device_name_upper = device.name.upper()
            if friendly_name_upper in device_name_upper or device_name_upper in friendly_name_upper:
                logger.debug(f"Найдено устройство по совпадению имени: {device.name}")
                return device
        
        logger.debug(f"Устройство по friendly_name {friendly_name} не найдено")
        return None

    def _find_device_by_partial_name(
        self,
        search_string: str,
        device_type: Optional[DeviceType] = None,
    ) -> Optional[DeviceInfo]:
        """Найти устройство по частичному совпадению имени или идентификатора."""
        if not search_string:
            return None
        
        logger.debug(f"Поиск устройства по частичному совпадению: {search_string}, тип: {device_type}")
        
        # Приводим поисковую строку к нижнему регистру для регистронезависимого поиска
        search_lower = search_string.lower()
        
        for device in self._devices.values():
            if device_type and device.device_type != device_type:
                continue
            
            # Проверяем device_id
            if search_lower in device.device_id.lower():
                logger.debug(f"Найдено устройство по совпадению device_id: {device.name}")
                return device
            
            # Проверяем имя устройства
            if search_lower in device.name.lower():
                logger.debug(f"Найдено устройство по совпадению имени: {device.name}")
                return device
            
            # Для DLNA устройств проверяем friendly_name
            if isinstance(device, DlnaRenderer) and device.friendly_name:
                if search_lower in device.friendly_name.lower():
                    logger.debug(f"Найдено устройство по совпадению friendly_name: {device.name}")
                    return device
        
        logger.debug(f"Устройство по частичному совпадению {search_string} не найдено")
        return None

    def list_devices(self, device_type: Optional[DeviceType] = None) -> List[DeviceInfo]:
        """Список всех устройств, опционально отфильтрованный по типу."""
        if device_type:
            return [d for d in self._devices.values() if d.device_type == device_type]
        return list(self._devices.values())

    def set_active_source(self, device_or_entity_id: str) -> bool:
        """Установить активный источник звука (обратная совместимость)."""
        return self.set_active_source_with_details(
            entity_id=device_or_entity_id,
            ip_address=None,
            mac_addresses=None,
            platform=None,
        )

    def set_active_source_with_details(
        self,
        entity_id: str,
        ip_address: Optional[str] = None,
        mac_addresses: Optional[List[str]] = None,
        platform: Optional[str] = None,
    ) -> bool:
        """Установить активный источник звука с дополнительными данными."""
        # Поиск устройства по device_id
        device = self.find_device_by_entity_id(
            entity_id=entity_id,
            ip_address=ip_address,
            mac_addresses=mac_addresses,
            platform=platform,
        )
        if not device:
            logger.warning(f"Устройство {entity_id} не найдено по device_id.")
            return False
        
        if device.device_type != DeviceType.YANDEX_STATION:
            logger.warning(f"Устройство {entity_id} не является Яндекс Станцией.")
            return False
        
        # Обновляем данные устройства, если переданы дополнительные сведения
        if ip_address and not device.ip_address:
            device.ip_address = ip_address
        if mac_addresses and not device.mac_address:
            # Фильтруем пустые MAC-адреса и нормализуем, берём первый непустой MAC
            filtered_macs = [mac for mac in mac_addresses if mac]
            if filtered_macs:
                normalized_mac = self._normalize_mac(filtered_macs[0])
                device.mac_address = normalized_mac
                logger.debug(f"Установлен MAC-адрес для источника {device.name}: {normalized_mac}")
        if platform and isinstance(device, YandexStation) and not device.platform:
            device.platform = platform
        
        self._active_source_id = device.device_id
        logger.info(f"Активный источник установлен: {device.name} (IP: {device.ip_address}, MAC: {device.mac_address})")
        return True

    def set_active_target(self, device_or_entity_id: str) -> bool:
        """Установить активный приёмник звука (обратная совместимость)."""
        return self.set_active_target_with_details(
            entity_id=device_or_entity_id,
            ip_address=None,
            mac_addresses=None,
            friendly_name=None,
            renderer_url=None,
        )

    def set_active_target_with_details(
        self,
        entity_id: str,
        ip_address: Optional[str] = None,
        mac_addresses: Optional[List[str]] = None,
        friendly_name: Optional[str] = None,
        renderer_url: Optional[str] = None,
    ) -> bool:
        """Установить активный приёмник звука с дополнительными данными."""
        # Поиск устройства по device_id
        device = self.find_device_by_entity_id(
            entity_id=entity_id,
            ip_address=ip_address,
            mac_addresses=mac_addresses,
            platform=None,
            friendly_name=friendly_name,
        )
        if not device:
            logger.warning(f"Устройство {entity_id} не найдено по device_id.")
            return False
        
        if device.device_type != DeviceType.DLNA_RENDERER:
            logger.warning(f"Устройство {entity_id} не является DLNA-рендерером.")
            return False
        
        # Обновляем данные устройства, если переданы дополнительные сведения
        if ip_address and not device.ip_address:
            device.ip_address = ip_address
        if mac_addresses and not device.mac_address:
            # Фильтруем пустые MAC-адреса и нормализуем, берём первый непустой MAC
            filtered_macs = [mac for mac in mac_addresses if mac]
            if filtered_macs:
                normalized_mac = self._normalize_mac(filtered_macs[0])
                device.mac_address = normalized_mac
                logger.debug(f"Установлен MAC-адрес для приёмника {device.name}: {normalized_mac}")
        if friendly_name and isinstance(device, DlnaRenderer) and not device.friendly_name:
            device.friendly_name = friendly_name
        if renderer_url and isinstance(device, DlnaRenderer) and not device.renderer_url:
            device.renderer_url = renderer_url
        
        self._active_target_id = device.device_id
        logger.info(f"Активный приёмник установлен: {device.name} (IP: {device.ip_address}, MAC: {device.mac_address})")
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