from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


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


@dataclass
class DeviceInfo:
    """Базовая информация об устройстве."""
    device_id: str
    name: str
    device_type: DeviceType
    host: str
    port: int
    ip_address: str = ""
    mac_addresses: List[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class YandexStation(DeviceInfo):
    """Яндекс Станция как источник звука."""
    platform: str = ""
    volume: int = 0
    muted: bool = False
    alice_state: str = "IDLE"


@dataclass
class DlnaRenderer(DeviceInfo):
    """DLNA-устройство как приёмник звука."""
    renderer_url: str = ""
    friendly_name: str = ""
    volume: int = 0
    power: bool = False


@dataclass
class StreamingConfig:
    """Конфигурация стриминга."""
    source_device_id: str
    target_device_id: str
    mute_source: bool = True
    enabled: bool = False
    current_status: StreamingStatus = StreamingStatus.IDLE