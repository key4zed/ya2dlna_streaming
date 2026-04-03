import json
from logging import getLogger
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config.settings import Settings

logger = getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# Путь к файлу настроек
SETTINGS_FILE = Path("/data/settings.json")


class AppSettings(BaseModel):
    """Модель настроек приложения для API."""
    ya_music_token: str = Field("", description="Токен Яндекс.Музыки")
    x_token: str = Field("", description="X‑Token для авторизации Яндекс.Станции")
    cookie: str = Field("", description="Cookie для авторизации Яндекс.Станции")
    ruark_pin: str = Field("", description="PIN для управления Ruark R5")
    local_server_host: str = Field("0.0.0.0", description="Хост сервера")
    local_server_port_dlna: int = Field(8001, ge=1, le=65535, description="Порт DLNA сервера")
    local_server_port_api: int = Field(8000, ge=1, le=65535, description="Порт API")
    stream_quality: str = Field("192", description="Качество стрима: 128, 192, 320")
    debug: bool = Field(False, description="Режим отладки")
    mute_yandex_station: bool = Field(True, description="Отключить звук Яндекс Станции")
    dlna_device_name: str = Field("", description="Имя DLNA устройства")
    yandex_music_timeout: int = Field(10, ge=1, description="Таймаут Яндекс.Музыки (сек)")
    yandex_music_cache_ttl: int = Field(300, ge=0, description="Время жизни кэша треков (сек)")


def load_settings_from_file() -> Dict[str, Any]:
    """Загружает настройки из файла."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки настроек из файла: {e}")
        return {}


def save_settings_to_file(settings: Dict[str, Any]) -> None:
    """Сохраняет настройки в файл."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        logger.info("Настройки сохранены в файл")
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек в файл: {e}")
        raise HTTPException(status_code=500, detail="Не удалось сохранить настройки")


def get_current_settings() -> AppSettings:
    """Возвращает текущие настройки, объединяя значения из файла и переменных окружения."""
    file_settings = load_settings_from_file()
    # Получаем текущие настройки из глобального объекта settings
    current = Settings()
    # Преобразуем в словарь, заменяя значения из файла
    result = {}
    for field_name in AppSettings.model_fields.keys():
        # Берем значение из файла, если есть, иначе из текущих настроек
        if field_name in file_settings:
            result[field_name] = file_settings[field_name]
        else:
            # Получаем значение из текущих настроек (через getattr)
            result[field_name] = getattr(current, field_name, None)
    return AppSettings(**result)


@router.get("", response_model=AppSettings)
async def get_settings():
    """Получить текущие настройки."""
    try:
        return get_current_settings()
    except Exception as e:
        logger.error(f"Ошибка при получении настроек: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")


@router.post("", response_model=AppSettings)
async def update_settings(new_settings: AppSettings):
    """Обновить настройки."""
    try:
        # Сохраняем в файл
        save_settings_to_file(new_settings.model_dump())
        # Применяем настройки к текущему экземпляру Settings (перезагружаем)
        # Для этого нужно пересоздать объект Settings с учетом новых значений.
        # Однако глобальный объект settings уже создан. Вместо этого можно
        # обновить переменные окружения или перезапустить приложение.
        # Пока просто сохраняем в файл, а при следующем запуске настройки загрузятся.
        logger.info("Настройки обновлены через API")
        return new_settings
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при обновлении настроек: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")


@router.get("/schema")
async def get_settings_schema():
    """Получить JSON-схему настроек."""
    try:
        return AppSettings.model_json_schema()
    except Exception as e:
        logger.error(f"Ошибка при получении схемы настроек: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")