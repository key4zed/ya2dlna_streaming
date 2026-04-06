"""Select platform for Ya2DLNA."""
import logging
import aiohttp
import asyncio
from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.entity import DeviceInfo
from .const import (
    DOMAIN,
    CONF_API_HOST,
    CONF_API_PORT,
    CONF_TARGET_DEVICE_ID,
    CONF_TARGET_FRIENDLY_NAME,
    CONF_ENABLE_FILE_LOGGING,
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_ENABLE_FILE_LOGGING,
    ATTR_ACTIVE_TARGET,
    ATTR_AVAILABLE_TARGETS,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DEVICE_NAME,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the select platform."""
    _LOGGER.info(f"Загрузка платформы select для entry {config_entry.entry_id}")
    # Получаем объединённые данные: сначала options, потом data
    def get_config(key, default=None):
        return config_entry.options.get(key, config_entry.data.get(key, default))
    
    # Проверяем, включено ли файловое логирование
    enable_file_logging = get_config(CONF_ENABLE_FILE_LOGGING, DEFAULT_ENABLE_FILE_LOGGING)
    _LOGGER.info(f"Файловое логирование: {'включено' if enable_file_logging else 'отключено'}")
    
    # Настраиваем файловое логирование для отладки, если включено
    if enable_file_logging:
        import os
        log_file = os.path.join(hass.config.config_dir, "custom_components", "ya2dlna", "ya2dlna.log")
        try:
            # Создаём директорию если её нет
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            # Добавляем FileHandler к логгеру интеграции
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(formatter)
            _LOGGER.addHandler(file_handler)
            _LOGGER.info(f"Файловое логирование включено: {log_file}")
        except Exception as e:
            _LOGGER.error(f"Не удалось настроить файловое логирование: {e}")
    
    api_host = get_config(CONF_API_HOST, DEFAULT_API_HOST)
    api_port = get_config(CONF_API_PORT, DEFAULT_API_PORT)
    target_device_id = get_config(CONF_TARGET_DEVICE_ID)
    target_friendly_name = get_config(CONF_TARGET_FRIENDLY_NAME)
    _LOGGER.debug(f"Конфигурация select: api_host={api_host}, api_port={api_port}, target_device_id={target_device_id}, target_friendly_name={target_friendly_name}, enable_file_logging={enable_file_logging}")

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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            name=DEVICE_NAME,
        )

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
        _LOGGER.debug(f"GET запрос к {url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        devices = await resp.json()
                        _LOGGER.debug(f"GET ответ: статус {resp.status}, тело: {devices}")
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
                        try:
                            response_text = await resp.text()
                            _LOGGER.warning(f"Не удалось получить список устройств: статус {resp.status}, тело: {response_text}")
                        except:
                            _LOGGER.warning(f"Не удалось получить список устройств: статус {resp.status}, тело недоступно")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error("Ошибка при запросе списка устройств: %s", e)
            self._attr_options = []

    async def _fetch_active_target(self):
        """Получить текущий активный таргет из аддона."""
        url = f"http://{self._api_host}:{self._api_port}/ha/config"
        _LOGGER.debug(f"GET запрос к {url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        config = await resp.json()
                        _LOGGER.debug(f"GET ответ: статус {resp.status}, тело: {config}")
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
                        try:
                            response_text = await resp.text()
                            _LOGGER.warning(f"Не удалось получить конфигурацию: статус {resp.status}, тело: {response_text}")
                        except:
                            _LOGGER.warning(f"Не удалось получить конфигурацию: статус {resp.status}, тело недоступно")
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
        _LOGGER.debug(f"POST запрос к {url} (тело запроса отсутствует)")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, timeout=10) as resp:
                    if resp.status == 200:
                        self._attr_current_option = option
                        _LOGGER.info("Активный таргет установлен на %s", option)
                    else:
                        try:
                            response_text = await resp.text()
                            _LOGGER.error(f"Ошибка установки таргета: статус {resp.status}, тело ответа: {response_text}")
                        except:
                            _LOGGER.error(f"Ошибка установки таргета: статус {resp.status}, тело ответа недоступно")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error(f"Ошибка при установке таргета: {e}")

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            ATTR_ACTIVE_TARGET: self._attr_current_option,
            ATTR_AVAILABLE_TARGETS: [fname for _, fname in self._available_targets],
        }