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
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switch platform."""
    api_host = config_entry.data.get(CONF_API_HOST, "localhost")
    api_port = config_entry.data.get(CONF_API_PORT, 8000)
    source_entity = config_entry.data.get(CONF_SOURCE_ENTITY)
    target_entity = config_entry.data.get(CONF_TARGET_ENTITY)

    switch = Ya2DLNASwitch(
        hass,
        api_host,
        api_port,
        source_entity,
        target_entity,
        config_entry.entry_id,
    )
    async_add_entities([switch])


class Ya2DLNASwitch(SwitchEntity):
    """Representation of a streaming switch."""

    def __init__(self, hass, api_host, api_port, source_entity, target_entity, entry_id):
        """Initialize the switch."""
        self.hass = hass
        self._api_host = api_host
        self._api_port = api_port
        self._source_entity = source_entity
        self._target_entity = target_entity
        self._entry_id = entry_id
        self._state = False
        self._attr_name = "Ya2DLNA Streaming"
        self._attr_unique_id = f"ya2dlna_switch_{entry_id}"

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        # Определяем device_id выбранных устройств через их атрибуты
        # Для простоты используем entity_id как идентификатор устройства в API
        # В реальности нужно сопоставить entity_id с device_id через API обнаружения
        # Здесь упрощённая логика: отправляем entity_id как device_id
        try:
            async with aiohttp.ClientSession() as session:
                # Установить источник
                await session.post(
                    f"http://{self._api_host}:{self._api_port}/ha/source/{self._source_entity}"
                )
                # Установить приёмник
                await session.post(
                    f"http://{self._api_host}:{self._api_port}/ha/target/{self._target_entity}"
                )
                # Запустить стриминг
                await session.post(
                    f"http://{self._api_host}:{self._api_port}/ha/stream/start"
                )
                self._state = True
                self.async_write_ha_state()
                _LOGGER.info("Ya2DLNA streaming started")
        except Exception as e:
            _LOGGER.error(f"Failed to start streaming: {e}")

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"http://{self._api_host}:{self._api_port}/ha/stream/stop"
                )
                self._state = False
                self.async_write_ha_state()
                _LOGGER.info("Ya2DLNA streaming stopped")
        except Exception as e:
            _LOGGER.error(f"Failed to stop streaming: {e}")

    async def async_update(self):
        """Update switch state by polling API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self._api_host}:{self._api_port}/ha/stream/status"
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._state = data.get("status") == "streaming"
        except Exception as e:
            _LOGGER.debug(f"Could not update switch state: {e}")