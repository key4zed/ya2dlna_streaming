#!/usr/bin/env python3
"""
Пример использования корректных идентификаторов устройств для ya2dlna

Этот скрипт демонстрирует, как правильно передавать идентификаторы устройств
при работе с API ya2dlna из Home Assistant.
"""

import asyncio
import aiohttp
import json

# Конфигурация API
API_HOST = "hassio"  # или "localhost" при локальной разработке
API_PORT = 8000
BASE_URL = f"http://{API_HOST}:{API_PORT}"


async def list_devices():
    """Получить список всех обнаруженных устройств."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/ha/devices") as resp:
                if resp.status == 200:
                    devices = await resp.json()
                    print(f"Найдено устройств: {len(devices)}")
                    
                    # Разделяем устройства по типам
                    yandex_stations = [d for d in devices if d.get("device_type") == "yandex_station"]
                    dlna_renderers = [d for d in devices if d.get("device_type") == "dlna_renderer"]
                    
                    print("\n=== Яндекс Станции ===")
                    for station in yandex_stations:
                        print(f"  • {station['name']}")
                        print(f"    device_id: {station['device_id']}")
                        print(f"    IP: {station.get('ip_address', 'неизвестно')}")
                        print(f"    Платформа: {station.get('platform', 'неизвестно')}")
                    
                    print("\n=== DLNA-устройства ===")
                    for renderer in dlna_renderers:
                        print(f"  • {renderer['name']}")
                        print(f"    device_id: {renderer['device_id']}")
                        print(f"    friendly_name: {renderer.get('friendly_name', 'неизвестно')}")
                        print(f"    URL: {renderer.get('renderer_url', 'неизвестно')}")
                    
                    return devices
                else:
                    print(f"Ошибка при получении устройств: {resp.status}")
                    return []
        except Exception as e:
            print(f"Исключение при получении устройств: {e}")
            return []


async def set_source_simple(device_id: str):
    """Установить источник звука (простой способ - только device_id)."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{BASE_URL}/ha/source/{device_id}"
            async with session.post(url) as resp:
                if resp.status in (200, 201, 204):
                    result = await resp.json()
                    print(f"Источник установлен: {result}")
                    return True
                else:
                    print(f"Ошибка установки источника: {resp.status}")
                    return False
        except Exception as e:
            print(f"Исключение при установке источника: {e}")
            return False


async def set_source_with_details(entity_id: str, ip_address: str, mac_addresses: list):
    """Установить источник звука с дополнительными данными."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{BASE_URL}/ha/source/any_id"  # device_id в пути не важен при использовании JSON
            data = {
                "entity_id": entity_id,
                "ip_address": ip_address,
                "mac_addresses": mac_addresses,
                "platform": "yandex_station",
                "extra": {}
            }
            async with session.post(url, json=data) as resp:
                if resp.status in (200, 201, 204):
                    result = await resp.json()
                    print(f"Источник установлен с деталями: {result}")
                    return True
                else:
                    print(f"Ошибка установки источника: {resp.status}")
                    return False
        except Exception as e:
            print(f"Исключение при установке источника: {e}")
            return False


async def set_target_simple(device_id: str):
    """Установить приёмник звука (простой способ - только device_id)."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{BASE_URL}/ha/target/{device_id}"
            async with session.post(url) as resp:
                if resp.status in (200, 201, 204):
                    result = await resp.json()
                    print(f"Приёмник установлен: {result}")
                    return True
                else:
                    print(f"Ошибка установки приёмника: {resp.status}")
                    return False
        except Exception as e:
            print(f"Исключение при установке приёмника: {e}")
            return False


async def set_target_with_details(entity_id: str, friendly_name: str, ip_address: str):
    """Установить приёмник звука с дополнительными данными."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{BASE_URL}/ha/target/any_id"
            data = {
                "entity_id": entity_id,
                "ip_address": ip_address,
                "friendly_name": friendly_name,
                "extra": {}
            }
            async with session.post(url, json=data) as resp:
                if resp.status in (200, 201, 204):
                    result = await resp.json()
                    print(f"Приёмник установлен с деталями: {result}")
                    return True
                else:
                    print(f"Ошибка установки приёмника: {resp.status}")
                    return False
        except Exception as e:
            print(f"Исключение при установке приёмника: {e}")
            return False


async def start_streaming(mute_yandex_station: bool = True):
    """Запустить стриминг."""
    async with aiohttp.ClientSession() as session:
        try:
            params = {"mute_yandex_station": str(mute_yandex_station).lower()}
            url = f"{BASE_URL}/ha/stream/start"
            async with session.post(url, params=params) as resp:
                if resp.status in (200, 201, 204):
                    result = await resp.json()
                    print(f"Стриминг запущен: {result}")
                    return True
                else:
                    print(f"Ошибка запуска стриминга: {resp.status}")
                    return False
        except Exception as e:
            print(f"Исключение при запуске стриминга: {e}")
            return False


async def stop_streaming():
    """Остановить стриминг."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{BASE_URL}/ha/stream/stop"
            async with session.post(url) as resp:
                if resp.status in (200, 201, 204):
                    result = await resp.json()
                    print(f"Стриминг остановлен: {result}")
                    return True
                else:
                    print(f"Ошибка остановки стриминга: {resp.status}")
                    return False
        except Exception as e:
            print(f"Исключение при остановке стриминга: {e}")
            return False


async def get_config():
    """Получить текущую конфигурацию стриминга."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{BASE_URL}/ha/config"
            async with session.get(url) as resp:
                if resp.status == 200:
                    config = await resp.json()
                    print(f"Текущая конфигурация: {json.dumps(config, indent=2, ensure_ascii=False)}")
                    return config
                else:
                    print(f"Ошибка получения конфигурации: {resp.status}")
                    return None
        except Exception as e:
            print(f"Исключение при получении конфигурации: {e}")
            return None


async def main():
    """Основная функция демонстрации."""
    print("=" * 60)
    print("Демонстрация работы с идентификаторами устройств ya2dlna")
    print("=" * 60)
    
    # 1. Получить список устройств
    print("\n1. Получение списка устройств...")
    devices = await list_devices()
    
    if not devices:
        print("Устройства не найдены. Завершение.")
        return
    
    # 2. Примеры использования разных методов установки устройств
    print("\n2. Примеры установки устройств:")
    
    # Пример 1: Простая установка Яндекс Станции по device_id
    print("\nПример 1: Установка Яндекс Станции по device_id")
    yandex_stations = [d for d in devices if d.get("device_type") == "yandex_station"]
    if yandex_stations:
        station = yandex_stations[0]
        await set_source_simple(station["device_id"])
    
    # Пример 2: Установка Яндекс Станции с дополнительными данными
    print("\nПример 2: Установка Яндекс Станции с дополнительными данными")
    await set_source_with_details(
        entity_id="media_player.yandex_station_living_room",
        ip_address="192.168.1.100",
        mac_addresses=["aa:bb:cc:dd:ee:ff"]
    )
    
    # Пример 3: Простая установка DLNA-устройства по device_id
    print("\nПример 3: Установка DLNA-устройства по device_id")
    dlna_renderers = [d for d in devices if d.get("device_type") == "dlna_renderer"]
    if dlna_renderers:
        renderer = dlna_renderers[0]
        await set_target_simple(renderer["device_id"])
    
    # Пример 4: Установка DLNA-устройства с дополнительными данными
    print("\nПример 4: Установка DLNA-устройства с дополнительными данными")
    await set_target_with_details(
        entity_id="media_player.lg_tv_bedroom",
        friendly_name="[TV][LG]42LA660V-ZA",
        ip_address="192.168.1.150"
    )
    
    # 3. Получить текущую конфигурацию
    print("\n3. Получение текущей конфигурации...")
    await get_config()
    
    # 4. Демонстрация запуска и остановки стриминга
    print("\n4. Демонстрация управления стримингом:")
    
    # Проверяем, установлены ли устройства
    config = await get_config()
    if config and config.get("source_device_id") and config.get("target_device_id"):
        print("Устройства установлены, можно запускать стриминг")
        
        # Запуск стриминга
        print("\nЗапуск стриминга...")
        await start_streaming(mute_yandex_station=True)
        
        # Ждем 3 секунды
        await asyncio.sleep(3)
        
        # Остановка стриминга
        print("\nОстановка стриминга...")
        await stop_streaming()
    else:
        print("Устройства не установлены, стриминг невозможен")
    
    print("\n" + "=" * 60)
    print("Демонстрация завершена")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())