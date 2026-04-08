from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DeviceType(str, Enum):
    """Тип устройства."""
    YANDEX_STATION = "yandex_station"
    DLNA_RENDERER = "dlna_renderer"


class StreamingStatus(str, Enum):
    """Статус стриминга."""
    IDLE = "idle"
    STREAMING = "streaming"
    PAUSED = "paused"
    ERROR = "error"


class DeviceInfo(BaseModel):
    """Базовая информация об устройстве."""
    device_id: str = Field(
        example="LY0000000000000375320000de71a2d5",
        description="Уникальный идентификатор устройства"
    )
    name: str = Field(
        example="Яндекс Станция в гостиной",
        description="Человекочитаемое имя устройства"
    )
    device_type: DeviceType = Field(
        description="Тип устройства (yandex_station или dlna_renderer)"
    )
    host: str = Field(
        example="192.168.1.100",
        description="Хост устройства (IP или доменное имя)"
    )
    port: int = Field(
        example=8080,
        description="Порт устройства"
    )
    ip_address: str = Field(
        default="",
        example="192.168.1.100",
        description="IP адрес устройства в локальной сети"
    )
    mac_address: str = Field(
        default="",
        example="aa:bb:cc:dd:ee:ff",
        description="MAC адрес устройства"
    )
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        example={"room": "living_room", "volume": 50},
        description="Дополнительные произвольные данные",
        exclude=True
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "LY0000000000000375320000de71a2d5",
                "name": "Яндекс Станция в гостиной",
                "device_type": "yandex_station",
                "host": "192.168.1.100",
                "port": 8080,
                "ip_address": "192.168.1.100",
                "mac_address": "aa:bb:cc:dd:ee:ff"
            }
        }
    )


class YandexStation(DeviceInfo):
    """Яндекс Станция как источник звука."""
    platform: str = Field(
        default="",
        example="yandex_station",
        description="Платформа интеграции"
    )
    volume: int = Field(
        default=0,
        example=50,
        description="Текущая громкость (0‑100)"
    )
    muted: bool = Field(
        default=False,
        example=False,
        description="Выключен ли звук"
    )
    alice_state: str = Field(
        default="IDLE",
        example="IDLE",
        description="Состояние Алисы (IDLE, SPEAKING, LISTENING)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "LY0000000000000375320000de71a2d5",
                "name": "Яндекс Станция в гостиной",
                "device_type": "yandex_station",
                "host": "192.168.1.100",
                "port": 8080,
                "ip_address": "192.168.1.100",
                "mac_address": "aa:bb:cc:dd:ee:ff",
                "platform": "yandex_station",
                "volume": 50,
                "muted": False,
                "alice_state": "IDLE"
            }
        }
    )


class DlnaRenderer(DeviceInfo):
    """DLNA-устройство как приёмник звука."""
    renderer_url: str = Field(
        default="",
        example="http://192.168.1.200:49152/description.xml",
        description="URL DLNA-рендерера для управления"
    )
    friendly_name: str = Field(
        default="",
        example="Living Room Speaker",
        description="Человекочитаемое имя устройства"
    )
    volume: int = Field(
        default=0,
        example=30,
        description="Текущая громкость (0‑100)"
    )
    power: bool = Field(
        default=False,
        example=True,
        description="Включено ли устройство"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "uuid:device-UUID-1234",
                "name": "DLNA Renderer",
                "device_type": "dlna_renderer",
                "host": "192.168.1.200",
                "port": 49152,
                "ip_address": "192.168.1.200",
                "mac_address": "11:22:33:44:55:66",
                "renderer_url": "http://192.168.1.200:49152/description.xml",
                "friendly_name": "Living Room Speaker",
                "volume": 30,
                "power": True
            }
        }
    )


class StreamingConfig(BaseModel):
    """Конфигурация стриминга."""
    source_device_id: str = Field(
        example="LY0000000000000375320000de71a2d5",
        description="ID активного источника (Яндекс Станция)"
    )
    target_device_id: str = Field(
        example="uuid:device-UUID-1234",
        description="ID активного приёмника (DLNA-устройство)"
    )
    mute_source: bool = Field(
        default=True,
        example=True,
        description="Отключать звук на Яндекс Станции во время трансляции"
    )
    enabled: bool = Field(
        default=False,
        example=False,
        description="Включен ли стриминг в данный момент"
    )
    current_status: StreamingStatus = Field(
        default=StreamingStatus.IDLE,
        example=StreamingStatus.IDLE,
        description="Текущий статус стриминга"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_device_id": "LY0000000000000375320000de71a2d5",
                "target_device_id": "uuid:device-UUID-1234",
                "mute_source": True,
                "enabled": False,
                "current_status": "idle"
            }
        }
    )