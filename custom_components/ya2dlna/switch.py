"""Switch platform for Ya2DLNA."""
import logging
import aiohttp
import asyncio
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_HOST, CONF_PORT
from .const import (
    DOMAIN,
    CONF_SOURCE_ENTITY,
    CONF_TARGET_ENTITY,
    CONF_API_HOST,
    CONF_API_PORT,
    CONF_X_TOKEN,
    CONF_COOKIE,
    CONF_RUARK_PIN,
    CONF_MUTE_YANDEX_STATION,
    DEFAULT_MUTE_YANDEX_STATION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switch platform."""
    api_host = config_entry.data.get(CONF_API_HOST, "localhost")
    api_port = config_entry.data.get(CONF_API_PORT, 8000)
    source_entity = config_entry.data.get(CONF_SOURCE_ENTITY)
    target_entity = config_entry.data.get(CONF_TARGET_ENTITY)
    x_token = config_entry.data.get(CONF_X_TOKEN, "")
    cookie = config_entry.data.get(CONF_COOKIE, "")
    ruark_pin = config_entry.data.get(CONF_RUARK_PIN, "")
    mute_yandex_station = config_entry.data.get(CONF_MUTE_YANDEX_STATION, DEFAULT_MUTE_YANDEX_STATION)

    switch = Ya2DLNASwitch(
        hass,
        api_host,
        api_port,
        source_entity,
        target_entity,
        x_token,
        cookie,
        ruark_pin,
        mute_yandex_station,
        config_entry.entry_id,
    )
    async_add_entities([switch])


class Ya2DLNASwitch(SwitchEntity):
    """Representation of a streaming switch."""

    def __init__(self, hass, api_host, api_port, source_entity, target_entity, x_token, cookie, ruark_pin, mute_yandex_station, entry_id):
        """Initialize the switch."""
        self.hass = hass
        self._api_host = api_host
        self._api_port = api_port
        self._source_entity = source_entity
        self._target_entity = target_entity
        self._x_token = x_token
        self._cookie = cookie
        self._ruark_pin = ruark_pin
        self._mute_yandex_station = mute_yandex_station
        self._entry_id = entry_id
        self._state = False
        self._attr_name = "Ya2DLNA Streaming"
        self._attr_unique_id = f"ya2dlna_switch_{entry_id}"

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    async def _check_server_availability(self, session):
        """Проверить, доступен ли сервер API."""
        try:
            async with session.get(
                f"http://{self._api_host}:{self._api_port}/ha/stream/status",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        # Определяем device_id выбранных устройств через их атрибуты
        # Для простоты используем entity_id как идентификатор устройства в API
        # В реальности нужно сопоставить entity_id с device_id через API обнаружения
        # Здесь упрощённая логика: отправляем entity_id как device_id
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Проверить доступность сервера перед выполнением операций
                if not await self._check_server_availability(session):
                    _LOGGER.error(
                        f"Сервер Ya2DLNA недоступен по адресу {self._api_host}:{self._api_port}. "
                        "Убедитесь, что аддон запущен и настроен правильно."
                    )
                    return

                # Установить источник
                source_url = f"http://{self._api_host}:{self._api_port}/ha/source/{self._source_entity}"
                _LOGGER.debug(f"Setting source via {source_url}")
                resp = await session.post(source_url)
                if resp.status not in (200, 201, 204):
                    _LOGGER.warning(f"Failed to set source: {resp.status}")
                # Установить приёмник
                target_url = f"http://{self._api_host}:{self._api_port}/ha/target/{self._target_entity}"
                _LOGGER.debug(f"Setting target via {target_url}")
                resp = await session.post(target_url)
                if resp.status not in (200, 201, 204):
                    _LOGGER.warning(f"Failed to set target: {resp.status}")
                # Запустить стриминг с передачей x_token, cookie, ruark_pin и mute_yandex_station, если они есть
                params = {}
                if self._x_token:
                    params["x_token"] = self._x_token
                if self._cookie:
                    params["cookie"] = self._cookie
                if self._ruark_pin:
                    params["ruark_pin"] = self._ruark_pin
                if self._mute_yandex_station is not None:
                    params["mute_yandex_station"] = str(self._mute_yandex_station).lower()
                stream_url = f"http://{self._api_host}:{self._api_port}/ha/stream/start"
                _LOGGER.debug(f"Starting stream via {stream_url} with params {params}")
                resp = await session.post(
                    stream_url,
                    params=params if params else None,
                )
                if resp.status not in (200, 201, 204):
                    _LOGGER.warning(f"Failed to start streaming: {resp.status}")
                else:
                    self._state = True
                    self.async_write_ha_state()
                    _LOGGER.info("Ya2DLNA streaming started")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout while starting streaming")
        except Exception as e:
            _LOGGER.error(f"Failed to start streaming to {self._api_host}:{self._api_port}: {e}")

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                stop_url = f"http://{self._api_host}:{self._api_port}/ha/stream/stop"
                _LOGGER.debug(f"Stopping stream via {stop_url}")
                resp = await session.post(stop_url)
                if resp.status not in (200, 201, 204):
                    _LOGGER.warning(f"Failed to stop streaming: {resp.status}")
                else:
                    self._state = False
                    self.async_write_ha_state()
                    _LOGGER.info("Ya2DLNA streaming stopped")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout while stopping streaming")
        except Exception as e:
            _LOGGER.error(f"Failed to stop streaming to {self._api_host}:{self._api_port}: {e}")

    async def async_update(self):
        """Update switch state by polling API."""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                status_url = f"http://{self._api_host}:{self._api_port}/ha/stream/status"
                _LOGGER.debug(f"Polling status via {status_url}")
                async with session.get(status_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._state = data.get("status") == "streaming"
                    else:
                        _LOGGER.debug(f"Status endpoint returned {resp.status}")
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout while updating switch state")
        except Exception as e:
            _LOGGER.debug(f"Could not update switch state from {self._api_host}:{self._api_port}: {e}")