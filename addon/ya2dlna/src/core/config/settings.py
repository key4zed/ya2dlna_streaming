import sys
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация приложения."""

    @staticmethod
    def resolve_env_path() -> Path:
        """Определяет путь к файлу .env."""
        cwd_env = Path.cwd() / ".env"
        if cwd_env.exists():
            return cwd_env
        elif getattr(sys, "frozen", False):
            return Path(sys.executable).parent / ".env"
        else:
            return Path(__file__).resolve().parent.parent.parent / ".env"

    model_config = SettingsConfigDict(
        env_file=resolve_env_path(),
        env_prefix="APP_",
        extra="ignore",
        env_file_encoding="utf-8",
    )


    # Яндекс авторизация
    ya_music_token: str = Field(
        "",
        description="Токен Яндекс.Музыки (OAuth).",
    )
    ruark_pin: str = Field(
        "",
        description="PIN для управления Ruark R5.",
    )
    mute_yandex_station: bool = Field(
        True,
        description="Отключать звук на Яндекс Станции во время трансляции.",
    )

    # Фиксированные параметры (не настраиваются через конфигурацию аддона)
    stream_quality: str = "192"  # Качество аудиопотока в кбит/с (128, 192 или 320)
    stream_is_local_file: bool = False  # Скачивать треки локально перед стримингом (для отладки)
    yandex_music_timeout: int = 15  # Таймаут запросов к API Яндекс.Музыки (в секундах)
    yandex_music_cache_ttl: int = 300  # Время жизни кэша треков (в секундах)
    
    # Отладочное логирование
    debug: bool = Field(
        False,
        description="Включить отладочное логирование.",
    )


settings = Settings()
