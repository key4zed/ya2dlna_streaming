import sys
from pathlib import Path
from typing import Any, Optional

from pydantic import Field, ValidationInfo, field_validator
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

    # Yandex Music settings
    ya_music_token: str = Field(
        "",
        description="Токен Яндекс.Музыки. Получить можно через OAuth. Если не указан, стриминг через Яндекс.Музыку будет недоступен.",
    )

    # Yandex Station авторизация (альтернатива ya_music_token)
    x_token: Optional[str] = Field(
        None,
        description="X‑Token для авторизации Яндекс.Станции (опционально).",
    )
    cookie: Optional[str] = Field(
        None,
        description="Cookie для авторизации Яндекс.Станции (опционально).",
    )

    # API server settings
    local_server_host: str = Field(
        "0.0.0.0",
        description="Хост, на котором будет запущен сервер стриминга.",
    )
    local_server_port_dlna: int = Field(
        8001,
        ge=1,
        le=65535,
        description="Порт DLNA‑сервера (для трансляции потока).",
    )
    local_server_port_api: int = Field(
        8000,
        ge=1,
        le=65535,
        description="Порт REST API (для управления).",
    )

    # Ruark R5 settings (опционально, требуется только для Ruark R5)
    ruark_pin: Optional[str] = Field(
        None,
        description="PIN‑код для управления Ruark R5 (опционально). Если не указан, управление громкостью через PIN отключено.",
    )

    # DLNA device settings
    dlna_device_name: Optional[str] = Field(
        None,
        description="Имя DLNA‑устройства для поиска (например, 'DLNA Renderer'). Если не указано, будет использовано первое найденное устройство.",
    )

    # Mode settings
    debug: bool = Field(
        False,
        description="Включить отладочное логирование.",
    )

    # Stream settings
    stream_quality: str = Field(
        "192",
        pattern=r"^(128|192|320)$",
        description="Качество аудиопотока в кбит/с (128, 192 или 320).",
    )
    stream_is_local_file: bool = Field(
        False,
        description="Скачивать треки локально перед стримингом (для отладки).",
    )

    # Mute Yandex Station during streaming
    mute_yandex_station: bool = Field(
        True,
        description="Отключать звук на Яндекс Станции во время трансляции.",
    )

    # Yandex Music API settings
    yandex_music_timeout: int = Field(
        15,
        ge=1,
        description="Таймаут запросов к API Яндекс.Музыки (в секундах).",
    )
    yandex_music_cache_ttl: int = Field(
        300,
        ge=0,
        description="Время жизни кэша треков (в секундах).",
    )

    @field_validator("local_server_port_dlna", mode="before")
    @classmethod
    def validate_local_server_port_dlna(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip() == "":
            return 8001  # значение по умолчанию
        return v

    @field_validator("local_server_port_api", mode="before")
    @classmethod
    def validate_local_server_port_api(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip() == "":
            return 8000  # значение по умолчанию
        return v

    @field_validator("debug", mode="before")
    @classmethod
    def validate_debug(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip() == "":
            return False  # значение по умолчанию
        return v

    @field_validator("stream_quality", mode="before")
    @classmethod
    def validate_stream_quality(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip() == "":
            return "192"  # значение по умолчанию
        return v

    @field_validator("mute_yandex_station", mode="before")
    @classmethod
    def validate_mute_yandex_station(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip() == "":
            return True  # значение по умолчанию
        return v

    @field_validator("stream_is_local_file", mode="before")
    @classmethod
    def validate_stream_is_local_file(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip() == "":
            return False  # значение по умолчанию
        return v

    @field_validator("yandex_music_timeout", "yandex_music_cache_ttl", mode="before")
    @classmethod
    def validate_int_fields(cls, v: Any, info: ValidationInfo) -> Any:
        if isinstance(v, str) and v.strip() == "":
            # Для этих полей тоже есть значения по умолчанию
            if info.field_name == "yandex_music_timeout":
                return 15
            elif info.field_name == "yandex_music_cache_ttl":
                return 300
        return v

settings = Settings()
