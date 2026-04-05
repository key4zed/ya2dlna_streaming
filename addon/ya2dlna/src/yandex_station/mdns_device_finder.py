from core.logging.setup import setup_logging  # noqa
import ipaddress
from logging import getLogger
from time import sleep
from typing import List, Dict

from zeroconf import (ServiceBrowser, ServiceListener, ServiceStateChange,
                      Zeroconf)

logger = getLogger(__name__)


class DeviceFinder(ServiceListener):
    """Класс для поиска устройств Yandex Station в сети."""

    def __init__(self):
        self.devices: List[Dict] = []
        self.zeroconf = Zeroconf()

    def find_devices(self, type_="_yandexio._tcp.local."):
        """Поиск устройств Yandex Station в сети."""
        self.devices.clear()
        self.browser = ServiceBrowser(
            zc=self.zeroconf,
            type_=type_,
            handlers=[self._handler_device]
        )
        sleep(1)

    def _handler_device(
            self,
            zeroconf: Zeroconf,
            service_type: str,
            name: str,
            state_change: ServiceStateChange
    ) -> None:
        """Обработчик событий для устройств Yandex Station."""
        try:
            info = zeroconf.get_service_info(service_type, name)
            properties = {
                a.decode(): v.decode() for a, v in info.properties.items()
            }
            logger.info(f"Properties: {properties}")

            device = {
                "device_id": properties["deviceId"],
                "platform": properties["platform"],
                "host": str(ipaddress.ip_address(info.addresses[0])),
                "port": info.port,
            }
            # Проверяем, нет ли уже такого device_id в списке
            if not any(d["device_id"] == device["device_id"] for d in self.devices):
                self.devices.append(device)
                logger.info(f"Добавлена Яндекс Станция: {device}")
            else:
                logger.debug(f"Яндекс Станция {device['device_id']} уже в списке")

        except Exception as e:
            logger.error(f"Error: {e}")

    def close(self):
        """Закрытие zeroconf."""
        self.zeroconf.close()
