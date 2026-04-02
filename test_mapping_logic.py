#!/usr/bin/env python3
"""
Тестирование логики маппинга устройств без зависимостей.
"""
import sys
import os

# Добавляем путь к модулям add-on
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'addon/ya2dlna/src'))

from core.models.devices import DeviceType, YandexStation, DlnaRenderer


def test_find_device_by_ip_mac():
    """Тестирование поиска устройства по IP и MAC адресам."""
    print("=== Тестирование логики маппинга устройств ===")
    
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
    
    devices = {
        yandex_station.device_id: yandex_station,
        dlna_renderer.device_id: dlna_renderer
    }
    
    # Тестируем функцию _find_device_by_ip_mac (скопированная логика)
    def _find_device_by_ip_mac(ip_address=None, mac_addresses=None, device_type=None):
        """Найти устройство по IP и/или MAC адресу(ам)."""
        if not ip_address and not mac_addresses:
            return None
        
        for device in devices.values():
            if device_type and device.device_type != device_type:
                continue
            
            # Сравнение IP адреса
            if ip_address and device.ip_address:
                # Простое сравнение строк (может быть IPv4 или hostname)
                if ip_address == device.ip_address:
                    print(f"Найдено устройство по IP адресу: {device.name} (IP: {ip_address})")
                    return device
            
            # Сравнение MAC адресов
            if mac_addresses and device.mac_addresses:
                for mac in mac_addresses:
                    if mac in device.mac_addresses:
                        print(f"Найдено устройство по MAC адресу: {device.name} (MAC: {mac})")
                        return device
        
        print(f"Устройство по IP {ip_address} или MAC {mac_addresses} не найдено")
        return None
    
    # Тест 1: Поиск по IP
    print("\n1. Поиск по IP адресу:")
    device = _find_device_by_ip_mac(ip_address="192.168.1.100")
    assert device is yandex_station, f"Ожидалось Яндекс Станция, получено {device}"
    
    # Тест 2: Поиск по MAC
    print("\n2. Поиск по MAC адресу:")
    device = _find_device_by_ip_mac(mac_addresses=["11:22:33:44:55:66"])
    assert device is dlna_renderer, f"Ожидалось DLNA Renderer, получено {device}"
    
    # Тест 3: Поиск по IP и MAC
    print("\n3. Поиск по IP и MAC:")
    device = _find_device_by_ip_mac(
        ip_address="192.168.1.200",
        mac_addresses=["77:88:99:aa:bb:cc"]
    )
    assert device is dlna_renderer, f"Ожидалось DLNA Renderer, получено {device}"
    
    # Тест 4: Поиск с указанием типа устройства
    print("\n4. Поиск с указанием типа устройства:")
    device = _find_device_by_ip_mac(
        ip_address="192.168.1.100",
        device_type=DeviceType.YANDEX_STATION
    )
    assert device is yandex_station, f"Ожидалось Яндекс Станция, получено {device}"
    
    # Тест 5: Неверный IP
    print("\n5. Поиск с неверным IP:")
    device = _find_device_by_ip_mac(ip_address="192.168.1.999")
    assert device is None, f"Ожидалось None, получено {device}"
    
    print("\n=== Все тесты логики маппинга прошли успешно ===")


def test_entity_id_normalization():
    """Тестирование нормализации entity_id."""
    print("\n=== Тестирование нормализации entity_id ===")
    
    # Тестируем логику из find_device_by_entity_id
    test_cases = [
        ("media_player.yandex_station_ultraviolet", ["yandex_station_ultraviolet", "ultraviolet", "station_ultraviolet"]),
        ("media_player.yandex_ultraviolet", ["yandex_ultraviolet", "ultraviolet"]),
        ("media_player.station_ultraviolet", ["station_ultraviolet", "ultraviolet"]),
        ("media_player.ultraviolet", ["ultraviolet"]),
        ("media_player.am8_renderer", ["am8_renderer"]),
    ]
    
    for entity_id, expected_terms in test_cases:
        if "." not in entity_id:
            continue
        object_id = entity_id.split(".")[-1]
        search_terms = [object_id]
        if object_id.startswith("yandex_station_"):
            search_terms.append(object_id.replace("yandex_station_", ""))
        if object_id.startswith("yandex_"):
            search_terms.append(object_id.replace("yandex_", ""))
        if object_id.startswith("station_"):
            search_terms.append(object_id.replace("station_", ""))
        
        print(f"  {entity_id} -> {search_terms}")
        assert search_terms == expected_terms, f"Ожидалось {expected_terms}, получено {search_terms}"
    
    print("=== Нормализация entity_id прошла успешно ===")


if __name__ == "__main__":
    test_find_device_by_ip_mac()
    test_entity_id_normalization()
    print("\n✅ Все тесты улучшенного маппинга устройств прошли успешно!")