"""Select platform for Ya2DLNA."""
import logging
import aiohttp
import asyncio
from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_HOST, CONF_PORT
from .const import (
    DOMAIN,
    CONF_API_HOST,
    CONF_API_PORT,
    CONF_TARGET_DEVICE_ID,
    CONF_TARGET_FRIENDLY_NAME,
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    ATTR_ACTIVE_TARGET,
    ATTR_AVAILABLE_TARGETS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the select platform."""
    # Получаем объединённые данные: сначала options, потом data
    def get_config(key, default=None):
        return config_entry.options.get(key, config_entry.data.get(key, default))
    
    api_host = get_config(CONF_API_HOST, DEFAULT_API_HOST)
    api_port = get_config(CONF_API_PORT, DEFAULT_API_PORT)
    target_device_id = get_config(CONF_TARGET_DEVICE_ID)
    target_friendly_name = get_config(CONF_TARGET_FRIENDLY_NAME)

    # Создаём select entity для выбора активного таргета
    select_entity = Ya2DLNASelect(
        hass,
        api_host,
        api_port,
        target_device_id,
        target_friendly_name,
        config_entry.entry_id,
    )
    async_add_entities([select_entity], True)


class Ya2DLNASelect(SelectEntity):
    """Representation of a select entity for choosing active DLNA target."""

    def __init__(self, hass, api_host, api_port, target_device_id, target_friendly_name, entry_id):
        """Initialize the select."""
        self._hass = hass
        self._api_host = api_host
        self._api_port = api_port
        self._target_device_id = target_device_id
        self._target_friendly_name = target_friendly_name
        self._entry_id = entry_id
        self._attr_options = []
        self._attr_current_option = None
        self._available_targets = []  # список кортежей (device_id, friendly_name)
        self._attr_name = "Ya2DLNA Active Target"
        self._attr_unique_id = f"{entry_id}_active_target"
        self._attr_icon = "mdi:speaker"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Ya2DLNA Streaming",
            "manufacturer": "Ya2DLNA",
        }

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        # При добавлении обновляем список устройств
        await self.async_update()

    async def async_update(self):
        """Update the select options and current value."""
        await self._fetch_available_targets()
        await self._fetch_active_target()

    async def _fetch_available_targets(self):
        """Получить список доступных DLNA-устройств из аддона."""
        url = f"http://{self._api_host}:{self._api_port}/ha/devices/dlna"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        devices = await resp.json()
                        self._available_targets = []
                        options = []
                        for dev in devices:
                            device_id = dev.get("device_id")
                            friendly_name = dev.get("friendly_name") or dev.get("name", "Unknown")
                            self._available_targets.append((device_id, friendly_name))
                            options.append(friendly_name)
                        self._attr_options = options
                        _LOGGER.debug("Доступные таргеты: %s", self._available_targets)
                    else:
                        _LOGGER.warning("Не удалось получить список устройств: статус %s", resp.status)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error("Ошибка при запросе списка устройств: %s", e)
            self._attr_options = []

    async def _fetch_active_target(self):
        """Получить текущий активный таргет из аддона."""
        url = f"http://{self._api_host}:{self._api_port}/ha/config"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        config = await resp.json()
                        active_target = config.get("active_target")
                        if active_target:
                            # active_target может быть словарём или строкой device_id
                            if isinstance(active_target, dict):
                                device_id = active_target.get("device_id")
                            else:
                                device_id = active_target
                            # Найти friendly_name по device_id
                            friendly_name = None
                            for dev_id, fname in self._available_targets:
                                if dev_id == device_id:
                                    friendly_name = fname
                                    break
                            if friendly_name:
                                self._attr_current_option = friendly_name
                            else:
                                self._attr_current_option = None
                        else:
                            self._attr_current_option = None
                    else:
                        _LOGGER.warning("Не удалось получить конфигурацию: статус %s", resp.status)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error("Ошибка при запросе активного таргета: %s", e)

    async def async_select_option(self, option: str):
        """Select a new target option."""
        # Найти device_id по friendly_name
        device_id = None
        for dev_id, fname in self._available_targets:
            if fname == option:
                device_id = dev_id
                break
        if not device_id:
            _LOGGER.error("Устройство с именем %s не найдено в списке", option)
            return
        # Отправить запрос на установку активного таргета
        url = f"http://{self._api_host}:{self._api_port}/ha/target/{device_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, timeout=10) as resp:
                    if resp.status == 200:
                        self._attr_current_option = option
                        _LOGGER.info("Активный таргет установлен на %s", option)
                    else:
                        _LOGGER.error("Ошибка установки таргета: статус %s", resp.status)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error("Ошибка при установке таргета: %s", e)

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            ATTR_ACTIVE_TARGET: self._attr_current_option,
            ATTR_AVAILABLE_TARGETS: [fname for _, fname in self._available_targets],
        }