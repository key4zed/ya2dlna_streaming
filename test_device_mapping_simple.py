#!/usr/bin/env python3
"""
Упрощённое тестирование улучшенного маппинга устройств без внешних зависимостей.
"""
import asyncio
import sys
import os

# Добавляем путь к модулям add-on
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'addon/ya2dlna/src'))

# Создаём мок-классы для зависимостей, чтобы избежать импорта реальных модулей
class MockDLNAController:
    def __init__(self, device_name="DLNA Renderer"):
        self.device_name = device_name
        self.device = None
        self.ip = None
    
    def refresh_device(self):
        pass

class MockDeviceFinder:
    def __init__(self):
        self.device = None
    
    def find_devices(self):
        pass

# Алиас для совместимости с кодом теста
MockYandexFinder = MockDeviceFinder

# Монтируем моки в sys.modules перед импортом DeviceManager
import sys
sys.modules['dlna_stream_server.handlers.dlna_controller'] = type(sys)('dlna_controller')
sys.modules['dlna_stream_server.handlers.dlna_controller'].DLNAController = MockDLNAController

sys.modules['yandex_station.mdns_device_finder'] = type(sys)('mdns_device_finder')
sys.modules['yandex_station.mdns_device_finder'].DeviceFinder = MockDeviceFinder

# Теперь импортируем DeviceManager
from core.device_manager import DeviceManager
from core.models.devices import DeviceType, YandexStation, DlnaRenderer


async def test_device_mapping():
    """Тестирование маппинга устройств."""
    print("=== Тестирование улучшенного маппинга устройств ===")
    
    # Создаём DeviceManager с моками
    device_manager = DeviceManager()
    
    # Заменяем реальные зависимости на моки
    device_manager._dlna_controller = MockDLNAController()
    device_manager._yandex_finder = MockYandexFinder()
    
    # Создаём тестовые устройства
    yandex_station = YandexStation(
        device_id="yandex_station_ultraviolet",
        name="Yandex Station ultraviolet",
        device_type=DeviceType.YANDEX_STATION,
        host="192.168.1.100",
        port=0,
        ip_address="192.168.1.100",
        mac_addresses=["aa:bb:cc:dd:ee:ff"],
        platform="ultraviolet",
        extra={"platform": "ultraviolet"}
    )
    
    dlna_renderer = DlnaRenderer(
        device_id="dlna_renderer_am8",
        name="AM8 Renderer",
        device_type=DeviceType.DLNA_RENDERER,
        host="192.168.1.200",
        port=80,
        ip_address="192.168.1.200",
        mac_addresses=["11:22:33:44:55:66", "77:88:99:aa:bb:cc"],
        renderer_url="http://192.168.1.200:80/desc.xml",
        friendly_name="AM8 Renderer",
        extra={"friendly_name": "AM8 Renderer"}
    )
    
    # Добавляем устройства в менеджер
    device_manager._devices = {
        yandex_station.device_id: yandex_station,
        dlna_renderer.device_id: dlna_renderer
    }
    
    print(f"Добавлено устройств: {len(device_manager._devices)}")
    for device_id, device in device_manager._devices.items():
        print(f"  - {device_id}: {device.name} (IP: {device.ip_address}, MAC: {device.mac_addresses})")
    
    # Тест 1: Поиск по entity_id без дополнительных данных
    print("\n1. Поиск по entity_id без дополнительных данных:")
    entity_id = "media_player.yandex_station_ultraviolet"
    device = device_manager.find_device_by_entity_id(entity_id)
    if device:
        print(f"   Найдено: {device.name} (ID: {device.device_id})")
    else:
        print(f"   Не найдено: {entity_id}")
    
    # Тест 2: Поиск по entity_id с IP адресом
    print("\n2. Поиск по entity_id с IP адресом:")
    entity_id = "media_player.yandex_station_ultraviolet"
    device = device_manager.find_device_by_entity_id(
        entity_id=entity_id,
        ip_address="192.168.1.100"
    )
    if device:
        print(f"   Найдено по IP: {device.name}")
    else:
        print(f"   Не найдено по IP: {entity_id}")
    
    # Тест 3: Поиск по entity_id с MAC адресом
    print("\n3. Поиск по entity_id с MAC адресом:")
    entity_id = "media_player.am8_renderer"
    device = device_manager.find_device_by_entity_id(
        entity_id=entity_id,
        mac_addresses=["11:22:33:44:55:66"]
    )
    if device:
        print(f"   Найдено по MAC: {device.name}")
    else:
        print(f"   Не найдено по MAC: {entity_id}")
    
    # Тест 4: Поиск по entity_id с IP и MAC
    print("\n4. Поиск по entity_id с IP и MAC:")
    entity_id = "media_player.am8_renderer"
    device = device_manager.find_device_by_entity_id(
        entity_id=entity_id,
        ip_address="192.168.1.200",
        mac_addresses=["77:88:99:aa:bb:cc"]
    )
    if device:
        print(f"   Найдено по IP+MAC: {device.name}")
    else:
        print(f"   Не найдено по IP+MAC: {entity_id}")
    
    # Тест 5: Поиск по platform (для Яндекс Станций)
    print("\n5. Поиск по platform:")
    entity_id = "media_player.ultraviolet"  # object_id = "ultraviolet"
    device = device_manager.find_device_by_entity_id(entity_id)
    if device:
        print(f"   Найдено по platform: {device.name}")
    else:
        print(f"   Не найдено по platform: {entity_id}")
    
    # Тест 6: Поиск по friendly_name (для DLNA)
    print("\n6. Поиск по friendly_name:")
    entity_id = "media_player.am8_renderer"
    device = device_manager.find_device_by_entity_id(
        entity_id=entity_id,
        friendly_name="AM8 Renderer"
    )
    if device:
        print(f"   Найдено по friendly_name: {device.name}")
    else:
        print(f"   Не найдено по friendly_name: {entity_id}")
    
    # Тест 7: Установка активного источника с деталями
    print("\n7. Установка активного источника с деталями:")
    success = device_manager.set_active_source_with_details(
        entity_id="media_player.yandex_station_ultraviolet",
        ip_address="192.168.1.100",
        mac_addresses=["aa:bb:cc:dd:ee:ff"],
        platform="ultraviolet"
    )
    print(f"   Результат: {'Успешно' if success else 'Ошибка'}")
    active_source = device_manager.get_active_source()
    if active_source:
        print(f"   Активный источник: {active_source.name}")
    
    # Тест 8: Установка активного приёмника с деталями
    print("\n8. Установка активного приёмника с деталями:")
    success = device_manager.set_active_target_with_details(
        entity_id="media_player.am8_renderer",
        ip_address="192.168.1.200",
        mac_addresses=["11:22:33:44:55:66"],
        friendly_name="AM8 Renderer",
        renderer_url="http://192.168.1.200:80/desc.xml"
    )
    print(f"   Результат: {'Успешно' if success else 'Ошибка'}")
    active_target = device_manager.get_active_target()
    if active_target:
        print(f"   Активный приёмник: {active_target.name}")
    
    print("\n=== Тестирование завершено ===")


if __name__ == "__main__":
    asyncio.run(test_device_mapping())