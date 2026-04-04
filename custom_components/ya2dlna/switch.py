"""Switch platform for Ya2DLNA."""
import logging
import aiohttp
import asyncio
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_HOST, CONF_PORT
from .const import (
    DOMAIN,
    CONF_API_HOST,
    CONF_SOURCE_ENTITY,
    CONF_TARGET_ENTITY,
    CONF_API_PORT,
    CONF_X_TOKEN,
    CONF_COOKIE,
    CONF_RUARK_PIN,
    CONF_MUTE_YANDEX_STATION,
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_MUTE_YANDEX_STATION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switch platform."""
    # Получаем объединённые данные: сначала options, потом data
    def get_config(key, default=None):
        return config_entry.options.get(key, config_entry.data.get(key, default))
    
    # API host теперь настраивается пользователем
    api_host = get_config(CONF_API_HOST, DEFAULT_API_HOST)
    api_port = get_config(CONF_API_PORT, DEFAULT_API_PORT)
    source_entity = get_config(CONF_SOURCE_ENTITY)
    target_entity = get_config(CONF_TARGET_ENTITY)
    x_token = get_config(CONF_X_TOKEN, "")
    cookie = get_config(CONF_COOKIE, "")
    ruark_pin = get_config(CONF_RUARK_PIN, "")
    mute_yandex_station = get_config(CONF_MUTE_YANDEX_STATION, DEFAULT_MUTE_YANDEX_STATION)

    # Создаём основной switch для управления стримингом
    streaming_switch = Ya2DLNASwitch(
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
    
    # Создаём дополнительный switch для управления mute_yandex_station
    mute_switch = Ya2DLNAMuteSwitch(
        hass,
        api_host,
        api_port,
        config_entry.entry_id,
        mute_yandex_station,
    )
    
    async_add_entities([streaming_switch, mute_switch])


class Ya2DLNASwitch(SwitchEntity):
    """Representation of a streaming switch."""

    def __init__(self, hass, api_host, api_port, source_entity, target_entity, x_token, cookie, ruark_pin, mute_yandex_station, entry_id):
        """Initialize the switch."""
        self.hass = hass
        self._api_host = api_host  # Настраиваемый API хост
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

    def _normalize_mac(self, mac: str) -> str:
        """Нормализовать MAC-адрес: привести к нижнему регистру и удалить разделители."""
        if not mac:
            return mac
        # Удаляем все не-шестнадцатеричные символы (двоеточия, тире, точки)
        import re
        mac_clean = re.sub(r'[^a-fA-F0-9]', '', mac)
        # Приводим к нижнему регистру
        mac_clean = mac_clean.lower()
        # Можно вернуть в формате с двоеточиями, но для сравнения достаточно clean
        return mac_clean

    async def _get_device_info(self, entity_id: str) -> dict:
        """Получить информацию об устройстве из Home Assistant для передачи в API."""
        try:
            state = self.hass.states.get(entity_id)
            if state is None:
                _LOGGER.debug(f"Устройство {entity_id} не найдено в состоянии Home Assistant (HA {self._ha_version})")
                return {}
            
            # Логируем все атрибуты устройства для отладки
            _LOGGER.debug(f"Состояние устройства {entity_id}: state={state.state}, attributes={dict(state.attributes)}")
            
            # Определяем domain устройства
            domain = ""
            if "." in entity_id:
                domain = entity_id.split(".")[0]
            
            info = {
                "entity_id": entity_id,
                "ip_address": "",
                "mac_addresses": [],
                "platform": "",
                "friendly_name": "",
                "renderer_url": "",
                "extra": {}
            }
            
            _LOGGER.debug(f"Начинаем сбор информации об устройстве {entity_id} (domain: {domain}) (HA {self._ha_version})")
            
            # Извлекаем IP адрес из атрибутов
            ip_address = None
            
            # Для Яндекс Станций: атрибут host или ip_address
            if domain == "media_player" and "yandex_station" in entity_id:
                ip_address = state.attributes.get("host") or state.attributes.get("ip_address")
                _LOGGER.debug(f"Яндекс Станция {entity_id}: host={state.attributes.get('host')}, ip_address={state.attributes.get('ip_address')} -> ip_address={ip_address}")
            # Для DLNA устройств: извлекаем из ssdp_location или host
            elif domain == "media_player" and ("dlna" in entity_id.lower() or state.attributes.get("ssdp_location")):
                # Пробуем извлечь IP из ssdp_location (URL)
                ssdp_location = state.attributes.get("ssdp_location")
                _LOGGER.debug(f"DLNA устройство {entity_id}: ssdp_location={ssdp_location}")
                if ssdp_location:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(ssdp_location)
                        if parsed.hostname:
                            ip_address = parsed.hostname
                            _LOGGER.debug(f"Извлечён IP из ssdp_location: {ip_address}")
                            # Если это доменное имя, а не IP, оставляем как есть
                            # (add-on сам разрешит его)
                    except Exception as e:
                        _LOGGER.debug(f"Ошибка при парсинге ssdp_location: {e}")
                        pass
                if not ip_address:
                    ip_address = state.attributes.get("host") or state.attributes.get("ip_address")
                    _LOGGER.debug(f"IP из host/ip_address атрибутов: {ip_address}")
            # Для других устройств
            else:
                ip_address = state.attributes.get("host") or state.attributes.get("ip_address")
                _LOGGER.debug(f"Другое устройство {entity_id}: host={state.attributes.get('host')}, ip_address={state.attributes.get('ip_address')} -> ip_address={ip_address}")
            
            if ip_address:
                info["ip_address"] = ip_address
                _LOGGER.debug(f"Установлен IP адрес для {entity_id}: {ip_address}")
            
            # Извлекаем MAC адрес(ы)
            mac_address = state.attributes.get("mac_address")
            _LOGGER.debug(f"MAC адрес из атрибута mac_address для {entity_id}: {mac_address}")
            if mac_address:
                if isinstance(mac_address, list):
                    info["mac_addresses"] = [self._normalize_mac(m) for m in mac_address]
                    _LOGGER.debug(f"MAC адреса (список) после нормализации: {info['mac_addresses']}")
                else:
                    info["mac_addresses"] = [self._normalize_mac(mac_address)]
                    _LOGGER.debug(f"MAC адрес (строка) после нормализации: {info['mac_addresses']}")
            # Для DLNA устройств может быть два MAC адреса (Ethernet и Wi-Fi)
            # Проверяем дополнительные атрибуты
            elif domain == "media_player" and ("dlna" in entity_id.lower() or state.attributes.get("ssdp_location")):
                mac_addresses = []
                # Проверяем стандартные атрибуты
                for attr in ["mac_address_ethernet", "mac_address_wifi", "mac_address_wireless"]:
                    mac = state.attributes.get(attr)
                    if mac:
                        _LOGGER.debug(f"Найден MAC адрес в атрибуте {attr}: {mac}")
                        if isinstance(mac, list):
                            mac_addresses.extend([self._normalize_mac(m) for m in mac])
                        else:
                            mac_addresses.append(self._normalize_mac(mac))
                if mac_addresses:
                    info["mac_addresses"] = list(set(mac_addresses))  # Убираем дубликаты
                    _LOGGER.debug(f"MAC адреса после удаления дубликатов: {info['mac_addresses']}")
                else:
                    _LOGGER.debug(f"MAC адреса не найдены в дополнительных атрибутах для {entity_id}")
            
            # Платформа (для Яндекс Станций)
            platform = state.attributes.get("platform")
            if platform:
                info["platform"] = platform
            
            # Friendly name (для DLNA)
            friendly_name = state.attributes.get("friendly_name") or state.attributes.get("device_name")
            if friendly_name:
                info["friendly_name"] = friendly_name
            
            # Renderer URL (для DLNA)
            renderer_url = state.attributes.get("ssdp_location") or state.attributes.get("location")
            if renderer_url:
                info["renderer_url"] = renderer_url
            
            # Дополнительные атрибуты
            extra = {}
            if domain:
                extra["domain"] = domain
            
            # Добавляем manufacturer и model если есть
            manufacturer = state.attributes.get("manufacturer")
            if manufacturer:
                extra["manufacturer"] = manufacturer
            model = state.attributes.get("model")
            if model:
                extra["model"] = model
            
            # Добавляем device_id если есть (для Яндекс Станций)
            device_id = state.attributes.get("device_id") or state.attributes.get("unique_id")
            if device_id:
                extra["device_id"] = device_id
            
            # Добавляем информацию о типе устройства
            if "yandex_station" in entity_id.lower() or platform:
                extra["device_type"] = "yandex_station"
            elif "dlna" in entity_id.lower() or renderer_url:
                extra["device_type"] = "dlna_renderer"
            
            info["extra"] = extra
            
            _LOGGER.debug(f"Информация об устройстве {entity_id}: {info}")
            return info
        except Exception as e:
            _LOGGER.error(f"Ошибка при получении информации об устройстве {entity_id} (HA {self._ha_version}): {e}")
            return {}

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

                # Получить информацию об устройствах
                source_info = await self._get_device_info(self._source_entity)
                target_info = await self._get_device_info(self._target_entity)
                _LOGGER.debug(f"Информация об источнике {self._source_entity}: {source_info}")
                _LOGGER.debug(f"Информация о приёмнике {self._target_entity}: {target_info}")
                
                # Установить источник с передачей дополнительной информации
                source_url = f"http://{self._api_host}:{self._api_port}/ha/source/{self._source_entity}"
                _LOGGER.debug(f"Установка источника через {source_url} с данными: {source_info}")
                resp = await session.post(
                    source_url,
                    json=source_info
                )
                response_text = await resp.text()
                _LOGGER.debug(f"Ответ от установки источника: статус {resp.status}, текст: {response_text if resp.status != 200 else 'OK'}")
                if resp.status not in (200, 201, 204):
                    _LOGGER.error(f"Не удалось установить источник: {resp.status} (HA {self._ha_version}). Ответ: {response_text}")
                    # Продолжаем, возможно устройство будет найдено другими методами
                else:
                    _LOGGER.debug(f"Источник успешно установлен")
                
                # Установить приёмник с передачей дополнительной информации
                target_url = f"http://{self._api_host}:{self._api_port}/ha/target/{self._target_entity}"
                _LOGGER.debug(f"Установка приёмника через {target_url} с данными: {target_info}")
                resp = await session.post(
                    target_url,
                    json=target_info
                )
                response_text = await resp.text()
                _LOGGER.debug(f"Ответ от установки приёмника: статус {resp.status}, текст: {response_text if resp.status != 200 else 'OK'}")
                if resp.status not in (200, 201, 204):
                    _LOGGER.error(f"Не удалось установить приёмник: {resp.status} (HA {self._ha_version}). Ответ: {response_text}")
                    # Продолжаем, возможно устройство будет найдено другими методами
                else:
                    _LOGGER.debug(f"Приёмник успешно установлен")
                
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
                response_text = await resp.text()
                if resp.status not in (200, 201, 204):
                    _LOGGER.error(f"Failed to start streaming: {resp.status} (HA {self._ha_version}). Ответ: {response_text}")
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
            
            # API host теперь настраивается
            self._api_host = get_config(CONF_API_HOST, DEFAULT_API_HOST)
            self._api_port = get_config(CONF_API_PORT, DEFAULT_API_PORT)
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


class Ya2DLNAMuteSwitch(SwitchEntity):
    """Переключатель для управления mute_yandex_station (отключение звука на Яндекс.Станции)."""
    
    def __init__(self, hass, api_host, api_port, entry_id, initial_mute_state):
        """Initialize the mute switch."""
        self.hass = hass
        self._api_host = api_host  # Настраиваемый API хост
        self._api_port = api_port
        self._entry_id = entry_id
        self._state = initial_mute_state  # True = mute включен (звук отключен), False = mute выключен (звук включен)
        self._attr_name = "Ya2DLNA Mute Station"
        self._attr_unique_id = f"ya2dlna_mute_switch_{entry_id}"
        self._ha_version = getattr(hass.config, "version", "unknown")
    
    @property
    def is_on(self):
        """Return true if mute is enabled (sound is muted)."""
        return self._state
    
    async def async_turn_on(self, **kwargs):
        """Turn the mute on (mute sound on Yandex Station)."""
        await self._set_mute_state(True)
    
    async def async_turn_off(self, **kwargs):
        """Turn the mute off (unmute sound on Yandex Station)."""
        await self._set_mute_state(False)
    
    async def _set_mute_state(self, mute_state: bool):
        """Установить состояние mute и обновить конфигурацию."""
        try:
            # Обновляем состояние в конфигурации интеграции (options)
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if entry is None:
                _LOGGER.error(f"Запись конфигурации {self._entry_id} не найдена")
                return
            
            # Создаем обновленные options
            new_options = dict(entry.options)
            new_options[CONF_MUTE_YANDEX_STATION] = mute_state
            
            # Обновляем запись конфигурации
            self.hass.config_entries.async_update_entry(entry, options=new_options)
            
            # Обновляем внутреннее состояние
            self._state = mute_state
            self.async_write_ha_state()
            
            _LOGGER.info(f"Mute Yandex Station установлен в {mute_state}")
            
            # Если стриминг сейчас активен, можно отправить команду на обновление параметров
            # Но это не обязательно, так как при следующем запуске стриминга будет использовано новое значение
            # Можно отправить API запрос для обновления параметров на лету, но это сложнее
            # Пока просто обновляем конфигурацию
            
        except Exception as e:
            _LOGGER.error(f"Ошибка при установке mute состояния: {e}")
    
    async def async_update(self):
        """Update switch state from configuration."""
        try:
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if entry is None:
                return
            
            # Получаем текущее значение из конфигурации
            def get_config(key, default=None):
                return entry.options.get(key, entry.data.get(key, default))
            
            current_mute = get_config(CONF_MUTE_YANDEX_STATION, DEFAULT_MUTE_YANDEX_STATION)
            self._state = current_mute
        except Exception as e:
            _LOGGER.debug(f"Could not update mute switch state: {e}")