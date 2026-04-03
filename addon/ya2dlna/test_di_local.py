#!/usr/bin/env python3
"""Тест DI-контейнера для проверки зависимостей."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.dependencies.main_di_container import MainDIContainer
from main_stream_service.main_stream_manager import MainStreamManager

def test_di():
    try:
        container = MainDIContainer().get_container()
        manager = container.get(MainStreamManager)
        print("SUCCESS: MainStreamManager создан успешно")
        print(f"Manager: {manager}")
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_di()
    sys.exit(0 if success else 1)