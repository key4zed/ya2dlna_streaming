#!/usr/bin/env python3
"""Тест DI-контейнера с моком upnpclient."""

import sys
import os
import unittest.mock

# Мокаем upnpclient до импорта модулей
sys.modules['upnpclient'] = unittest.mock.MagicMock()

# Добавляем путь к src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'addon/ya2dlna/src')
sys.path.insert(0, src_path)

# Также мокаем другие возможные проблемные импорты
sys.modules['upnpclient.soap'] = unittest.mock.MagicMock()
sys.modules['upnpclient.upnp'] = unittest.mock.MagicMock()

from core.dependencies.main_di_container import MainDIContainer
from main_stream_service.main_stream_manager import MainStreamManager

def test_di():
    try:
        container = MainDIContainer().get_container()
        manager = container.get(MainStreamManager)
        print("SUCCESS: MainStreamManager создан успешно")
        print(f"Manager: {manager}")
        # Проверим, что device_manager присутствует
        if hasattr(manager, '_device_manager'):
            print(f"DeviceManager: {manager._device_manager}")
        else:
            print("WARNING: _device_manager отсутствует")
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_di()
    sys.exit(0 if success else 1)