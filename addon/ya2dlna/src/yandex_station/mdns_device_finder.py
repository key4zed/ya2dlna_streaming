from core.logging.setup import setup_logging  # noqa
import ipaddress
from logging import getLogger
from time import sleep

from zeroconf import (ServiceBrowser, ServiceListener, ServiceStateChange,
                      Zeroconf)

logger = getLogger(__name__)


class DeviceFinder(ServiceListener):
    """Класс для поиска устройств Yandex Station в сети."""

    def __init__(self):
        self.devices = []  # список всех обнаруженных устройств
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
        if self.devices:
            logger.info(f"Найдено Яндекс Станций: {len(self.devices)}")
        else:
            logger.info("Яндекс Станции не найдены")

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
            logger.debug(f"Properties: {properties}")

            device = {
                "device_id": properties["deviceId"],
                "platform": properties["platform"],
                "host": str(ipaddress.ip_address(info.addresses[0])),
                "port": info.port,
            }
            self.devices.append(device)
            logger.debug(f"Яндекс Станция: device_id={device['device_id']}, platform={device['platform']}, host={device['host']}, port={device['port']}")

        except Exception as e:
            logger.error(f"Error: {e}")

    @property
    def device(self):
        """Свойство для обратной совместимости: возвращает первое устройство или пустой словарь."""
        return self.devices[0] if self.devices else {}

    def close(self):
        """Закрытие zeroconf."""
        self.zeroconf.close()
