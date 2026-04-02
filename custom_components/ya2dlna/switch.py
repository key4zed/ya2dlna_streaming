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
    # Получаем объединённые данные: сначала options, потом data
    def get_config(key, default=None):
        return config_entry.options.get(key, config_entry.data.get(key, default))
    
    api_host = get_config(CONF_API_HOST, "localhost")
    api_port = get_config(CONF_API_PORT, 8000)
    source_entity = get_config(CONF_SOURCE_ENTITY)
    target_entity = get_config(CONF_TARGET_ENTITY)
    x_token = get_config(CONF_X_TOKEN, "")
    cookie = get_config(CONF_COOKIE, "")
    ruark_pin = get_config(CONF_RUARK_PIN, "")
    mute_yandex_station = get_config(CONF_MUTE_YANDEX_STATION, DEFAULT_MUTE_YANDEX_STATION)

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
        # Сохраняем версию Home Assistant для логирования
        self._ha_version = getattr(hass.config, "version", "unknown")

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

    async def _check_device_availability(self, entity_id: str) -> bool:
        """Проверить доступность устройства в Home Assistant."""
        try:
            state = self.hass.states.get(entity_id)
            if state is None:
                _LOGGER.warning(f"Устройство {entity_id} не найдено в Home Assistant (HA {self._ha_version})")
                return False
            
            # Проверяем атрибут available (если есть)
            available = state.attributes.get("available", True)
            if not available:
                _LOGGER.warning(f"Устройство {entity_id} помечено как недоступное (HA {self._ha_version})")
                return False
            
            # Проверяем состояние (для медиаплееров)
            # Если устройство выключено (state == "off"), оно может быть недоступно для стриминга
            if state.state == "off":
                _LOGGER.warning(f"Устройство {entity_id} выключено (state: off) (HA {self._ha_version})")
                return False
            
            # Для DLNA-устройств также можно проверить дополнительные атрибуты
            # Например, source_list, supported_features и т.д.
            return True
        except Exception as e:
            _LOGGER.error(f"Ошибка при проверке доступности устройства {entity_id} (HA {self._ha_version}): {e}")
            return False

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        # Обновляем конфигурацию из записи (на случай изменения через options flow)
        self._update_config_from_entry()
        
        # Проверить доступность устройств в Home Assistant перед запуском стриминга
        if not await self._check_device_availability(self._source_entity):
            _LOGGER.error(f"Источник {self._source_entity} недоступен. Стриминг не запущен. (HA {self._ha_version})")
            return
        
        if not await self._check_device_availability(self._target_entity):
            _LOGGER.error(f"Приёмник {self._target_entity} недоступен. Стриминг не запущен. (HA {self._ha_version})")
            return
        
        # Определяем device_id выбранных устройств через их атрибуты
        # Для простоты используем entity_id как идентификатор устройства в API
        # В реальности нужно сопоставить entity_id с device_id через API обнаружения
        # Здесь упрощённая логика: отправляем entity_id как device_id
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {"X-Home-Assistant-Version": self._ha_version}
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                # Проверить доступность сервера перед выполнением операций
                if not await self._check_server_availability(session):
                    _LOGGER.error(
                        f"Сервер Ya2DLNA недоступен по адресу {self._api_host}:{self._api_port}. "
                        f"Убедитесь, что аддон запущен и настроен правильно. (HA {self._ha_version})"
                    )
                    return

                # Установить источник
                source_url = f"http://{self._api_host}:{self._api_port}/ha/source/{self._source_entity}"
                _LOGGER.debug(f"Setting source via {source_url}")
                resp = await session.post(source_url)
                if resp.status not in (200, 201, 204):
                    _LOGGER.warning(f"Failed to set source: {resp.status} (HA {self._ha_version})")
                # Установить приёмник
                target_url = f"http://{self._api_host}:{self._api_port}/ha/target/{self._target_entity}"
                _LOGGER.debug(f"Setting target via {target_url}")
                resp = await session.post(target_url)
                if resp.status not in (200, 201, 204):
                    _LOGGER.warning(f"Failed to set target: {resp.status} (HA {self._ha_version})")
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
                    _LOGGER.warning(f"Failed to start streaming: {resp.status} (HA {self._ha_version})")
                else:
                    self._state = True
                    self.async_write_ha_state()
                    _LOGGER.info("Ya2DLNA streaming started")
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout while starting streaming (HA {self._ha_version})")
        except Exception as e:
            _LOGGER.error(f"Failed to start streaming to {self._api_host}:{self._api_port} (HA {self._ha_version}): {e}")

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        # Обновляем конфигурацию из записи (на случай изменения через options flow)
        self._update_config_from_entry()
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {"X-Home-Assistant-Version": self._ha_version}
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                stop_url = f"http://{self._api_host}:{self._api_port}/ha/stream/stop"
                _LOGGER.debug(f"Stopping stream via {stop_url}")
                resp = await session.post(stop_url)
                if resp.status not in (200, 201, 204):
                    _LOGGER.warning(f"Failed to stop streaming: {resp.status} (HA {self._ha_version})")
                else:
                    self._state = False
                    self.async_write_ha_state()
                    _LOGGER.info("Ya2DLNA streaming stopped")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout while stopping streaming")
        except Exception as e:
            _LOGGER.error(f"Failed to stop streaming to {self._api_host}:{self._api_port}: {e}")

    def _update_config_from_entry(self):
        """Обновить конфигурацию из текущей записи конфигурации."""
        try:
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if entry is None:
                _LOGGER.warning(f"Запись конфигурации {self._entry_id} не найдена")
                return
            
            # Получаем объединённые данные: сначала options, потом data
            def get_config(key, default=None):
                return entry.options.get(key, entry.data.get(key, default))
            
            self._api_host = get_config(CONF_API_HOST, "localhost")
            self._api_port = get_config(CONF_API_PORT, 8000)
            self._source_entity = get_config(CONF_SOURCE_ENTITY)
            self._target_entity = get_config(CONF_TARGET_ENTITY)
            self._x_token = get_config(CONF_X_TOKEN, "")
            self._cookie = get_config(CONF_COOKIE, "")
            self._ruark_pin = get_config(CONF_RUARK_PIN, "")
            self._mute_yandex_station = get_config(CONF_MUTE_YANDEX_STATION, DEFAULT_MUTE_YANDEX_STATION)
            
            _LOGGER.debug(f"Конфигурация переключателя обновлена: source={self._source_entity}, target={self._target_entity}")
        except Exception as e:
            _LOGGER.error(f"Ошибка при обновлении конфигурации из записи: {e}")

    async def async_update(self):
        """Update switch state by polling API."""
        # Сначала обновляем конфигурацию из записи (на случай изменения через options flow)
        self._update_config_from_entry()
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {"X-Home-Assistant-Version": self._ha_version}
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                status_url = f"http://{self._api_host}:{self._api_port}/ha/stream/status"
                _LOGGER.debug(f"Polling status via {status_url}")
                async with session.get(status_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._state = data.get("status") == "streaming"
                    else:
                        _LOGGER.debug(f"Status endpoint returned {resp.status}")
                
                # Дополнительная проверка: если переключатель включен, но устройства недоступны,
                # автоматически выключаем переключатель
                if self._state:
                    source_available = await self._check_device_availability(self._source_entity)
                    target_available = await self._check_device_availability(self._target_entity)
                    if not source_available or not target_available:
                        _LOGGER.warning(
                            f"Переключатель включен, но устройства недоступны (источник: {source_available}, приёмник: {target_available}). "
                            "Автоматически выключаем переключатель."
                        )
                        self._state = False
                        self.async_write_ha_state()
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout while updating switch state")
        except Exception as e:
            _LOGGER.debug(f"Could not update switch state from {self._api_host}:{self._api_port}: {e}")