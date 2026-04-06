"""Config flow for Ya2DLNA."""
import asyncio
import logging
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector, entity_registry
from .const import (
    DOMAIN,
    CONF_API_HOST,
    CONF_SOURCE_ENTITY,
    CONF_TARGET_ENTITY,
    CONF_API_PORT,
    CONF_X_TOKEN,
    CONF_COOKIE,
    CONF_AUTH_METHOD,
    CONF_RUARK_PIN,
    CONF_MUTE_YANDEX_STATION,
    CONF_TARGET_DEVICE_ID,
    CONF_TARGET_FRIENDLY_NAME,
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_MUTE_YANDEX_STATION,
    AUTH_METHOD_YANDEX_STATION,
    AUTH_METHOD_COOKIES,
    AUTH_METHOD_TOKEN,
)

_LOGGER = logging.getLogger(__name__)

# Домены интеграций Yandex Station, которые мы можем использовать для импорта
YANDEX_STATION_DOMAINS = ["yandex_station", "yandex_station_intents"]


class Ya2DLNAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ya2DLNA."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.auth_method = None
        self.x_token = None
        self.cookie = None
        self.source_entity = None
        self.target_entity = None
        self.api_host = DEFAULT_API_HOST
        self.api_port = DEFAULT_API_PORT
        self.dlna_devices = None  # список кортежей (device_id, friendly_name)
        self.target_device_id = None
        self.target_friendly_name = None

    async def _fetch_dlna_devices(self) -> list:
        """Запросить список DLNA-устройств у аддона."""
        url = f"http://{self.api_host}:{self.api_port}/ha/devices/dlna"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        devices = await resp.json()
                        # Преобразуем в список кортежей (device_id, friendly_name)
                        result = []
                        for dev in devices:
                            device_id = dev.get("device_id")
                            friendly_name = dev.get("friendly_name") or dev.get("name", "Unknown")
                            result.append((device_id, friendly_name))
                        return result
                    else:
                        _LOGGER.error(f"Ошибка при запросе устройств: {resp.status}")
                        return []
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error(f"Не удалось подключиться к аддону: {e}")
            return []
        except Exception as e:
            _LOGGER.error(f"Неизвестная ошибка: {e}")
            return []

    async def _fetch_yandex_stations(self) -> list:
        """Запросить список Яндекс Станций у аддона и вернуть entity_id."""
        url = f"http://{self.api_host}:{self.api_port}/ha/devices/yandex"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        devices = await resp.json()
                        # devices - список объектов YandexStation с полями device_id, name, ip_address, mac_addresses и т.д.
                        if not devices:
                            _LOGGER.info("Аддон не обнаружил Яндекс Станций")
                            return []
                        
                        # Логируем полученные устройства для отладки
                        ha_version = getattr(self.hass.config, "version", "unknown")
                        _LOGGER.info(f"Получено {len(devices)} устройств от аддона (HA {ha_version}):")
                        for i, dev in enumerate(devices):
                            _LOGGER.info(f"  Устройство {i}: device_id={dev.get('device_id')}, name={dev.get('name')}, ip_address={dev.get('ip_address')}, host={dev.get('host')}, extra={dev.get('extra', {})}")
                        
                        # Получить entity registry для определения интеграции
                        registry = entity_registry.async_get(self.hass)
                        yandex_entity_ids = []
                        
                        # Пройти по всем сущностям media_player
                        for entry in registry.entities.values():
                            if entry.domain != "media_player":
                                continue
                            # Проверим, принадлежит ли сущность интеграции Yandex Station
                            # По platform (например, "yandex_station" или "yandex_station_intents")
                            if entry.platform not in YANDEX_STATION_DOMAINS:
                                continue
                            # Получить состояние сущности для получения атрибутов
                            state = self.hass.states.get(entry.entity_id)
                            if not state:
                                continue
                            # Попробуем сопоставить с устройствами от аддона
                            matched = False
                            match_reason = ""
                            for dev in devices:
                                # Сравниваем по friendly_name (name) или device_id (MAC)
                                dev_name = dev.get("name", "").strip()
                                dev_device_id = dev.get("device_id", "").strip()
                                dev_ip = dev.get("ip_address", "").strip()
                                dev_host = dev.get("host", "").strip()
                                # Атрибуты сущности
                                attrs = state.attributes
                                entity_friendly_name = attrs.get("friendly_name", "")
                                entity_device_id = attrs.get("device_id", "")
                                entity_ip = attrs.get("ip_address", "")
                                # Также можно посмотреть unique_id записи (обычно содержит MAC)
                                entry_unique_id = entry.unique_id
                                # Сравнение по device_id (без учёта регистра)
                                if dev_device_id:
                                    dev_device_id_lower = dev_device_id.lower()
                                    entity_device_id_lower = entity_device_id.lower() if entity_device_id else ""
                                    entry_unique_id_lower = entry_unique_id.lower() if entry_unique_id else ""
                                    if dev_device_id_lower == entity_device_id_lower:
                                        matched = True
                                        match_reason = f"device_id exact match {dev_device_id}"
                                        break
                                    if dev_device_id_lower in entry_unique_id_lower:
                                        matched = True
                                        match_reason = f"device_id in unique_id {dev_device_id}"
                                        break
                                # Сравнение по имени
                                if dev_name and dev_name == entity_friendly_name:
                                    matched = True
                                    match_reason = f"name {dev_name}"
                                    break
                                # Сравнение по IP адресу
                                if dev_ip and entity_ip and dev_ip == entity_ip:
                                    matched = True
                                    match_reason = f"IP {dev_ip}"
                                    break
                                if dev_host and entity_ip and dev_host == entity_ip:
                                    matched = True
                                    match_reason = f"host {dev_host}"
                                    break
                                # Сравнение по host (может быть hostname)
                                if dev_host and dev_host in entry_unique_id:
                                    matched = True
                                    match_reason = f"host in unique_id"
                                    break
                            if matched:
                                _LOGGER.debug(f"Сопоставлено устройство {entry.entity_id} по {match_reason}")
                                yandex_entity_ids.append(entry.entity_id)
                            else:
                                _LOGGER.debug(f"Не удалось сопоставить сущность {entry.entity_id} (friendly_name={entity_friendly_name}, device_id={entity_device_id}, ip={entity_ip}) с устройствами аддона")
                        
                        _LOGGER.info(f"Найдено {len(yandex_entity_ids)} Яндекс Станций в Home Assistant (из {len(devices)} обнаруженных аддоном)")
                        return yandex_entity_ids
                    else:
                        _LOGGER.error(f"Ошибка при запросе Яндекс Станций: {resp.status}")
                        return []
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error(f"Не удалось подключиться к аддону: {e}")
            return []
        except Exception as e:
            _LOGGER.error(f"Неизвестная ошибка при сопоставлении Яндекс Станций: {e}")
            return []

    async def async_step_user(self, user_input=None):
        """Handle the initial step: choose authentication method."""
        ha_version = getattr(self.hass.config, "version", "unknown")
        _LOGGER.info(f"Config flow step 'user' (Home Assistant {ha_version})")
        errors = {}
        if user_input is not None:
            self.auth_method = user_input[CONF_AUTH_METHOD]
            if self.auth_method == AUTH_METHOD_YANDEX_STATION:
                return await self.async_step_yandex_station()
            elif self.auth_method == AUTH_METHOD_COOKIES:
                return await self.async_step_cookies()
            elif self.auth_method == AUTH_METHOD_TOKEN:
                return await self.async_step_token()
            else:
                errors["base"] = "unknown_auth_method"
                _LOGGER.error(f"Unknown auth method selected (Home Assistant {ha_version})")

        # Определить доступные методы аутентификации
        auth_methods = [
            (AUTH_METHOD_YANDEX_STATION, "Через компонент Yandex.Station"),
            (AUTH_METHOD_COOKIES, "Cookies"),
            (AUTH_METHOD_TOKEN, "Токен"),
        ]

        data_schema = vol.Schema({
            vol.Required(CONF_AUTH_METHOD): vol.In(dict(auth_methods)),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_yandex_station(self, user_input=None):
        """Handle selection of Yandex Station integration."""
        ha_version = getattr(self.hass.config, "version", "unknown")
        _LOGGER.info(f"Config flow step 'yandex_station' (Home Assistant {ha_version})")
        errors = {}
        if user_input is not None:
            # user_input содержит выбранную интеграцию (например, entry_id)
            entry_id = user_input["entry"]
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry:
                self.x_token = entry.data.get("x_token", "")
                self.cookie = entry.data.get("cookie", "")
                # Проверим, что хотя бы что-то есть
                if not self.x_token and not self.cookie:
                    errors["base"] = "no_auth_data"
                    _LOGGER.error(f"No auth data in selected Yandex Station entry (Home Assistant {ha_version})")
                else:
                    return await self.async_step_config()
            else:
                errors["base"] = "entry_not_found"
                _LOGGER.error(f"Selected Yandex Station entry not found (Home Assistant {ha_version})")

        # Соберём все записи Yandex Station
        yandex_entries = []
        for domain in YANDEX_STATION_DOMAINS:
            yandex_entries.extend(self.hass.config_entries.async_entries(domain))

        if not yandex_entries:
            # Нет интеграций, переключим на метод cookies с уведомлением
            self.auth_method = AUTH_METHOD_COOKIES
            return await self.async_step_cookies()

        # Создадим список для выбора
        entry_options = {entry.entry_id: f"{entry.title} ({entry.domain})" for entry in yandex_entries}

        data_schema = vol.Schema({
            vol.Required("entry"): vol.In(entry_options),
        })

        return self.async_show_form(
            step_id="yandex_station",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_cookies(self, user_input=None):
        """Handle input of cookies."""
        ha_version = getattr(self.hass.config, "version", "unknown")
        _LOGGER.info(f"Config flow step 'cookies' (Home Assistant {ha_version})")
        errors = {}
        description_placeholders = {}
        if self.auth_method == AUTH_METHOD_YANDEX_STATION:
            # Это автоматический переход из-за отсутствия интеграций
            description_placeholders["note"] = "Интеграции Yandex.Station не найдены. Пожалуйста, введите cookie вручную."

        if user_input is not None:
            cookie = user_input[CONF_COOKIE]
            if not cookie.strip():
                errors["base"] = "invalid_cookie"
                _LOGGER.error(f"Invalid cookie provided (Home Assistant {ha_version})")
            else:
                self.cookie = cookie
                self.x_token = ""
                return await self.async_step_config()

        data_schema = vol.Schema({
            vol.Required(CONF_COOKIE): str,
        })

        return self.async_show_form(
            step_id="cookies",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_token(self, user_input=None):
        """Handle input of x-token."""
        ha_version = getattr(self.hass.config, "version", "unknown")
        _LOGGER.info(f"Config flow step 'token' (Home Assistant {ha_version})")
        errors = {}
        if user_input is not None:
            x_token = user_input[CONF_X_TOKEN]
            if not x_token.strip():
                errors["base"] = "invalid_token"
                _LOGGER.error(f"Invalid x-token provided (Home Assistant {ha_version})")
            else:
                self.x_token = x_token
                self.cookie = ""
                return await self.async_step_config()

        data_schema = vol.Schema({
            vol.Required(CONF_X_TOKEN): str,
        })

        return self.async_show_form(
            step_id="token",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_config(self, user_input=None):
        """Handle configuration of devices and API."""
        ha_version = getattr(self.hass.config, "version", "unknown")
        _LOGGER.info(f"Config flow step 'config' (Home Assistant {ha_version})")
        errors = {}
        
        # Получить список DLNA-устройств от аддона
        if self.dlna_devices is None:
            self.dlna_devices = await self._fetch_dlna_devices()
            _LOGGER.debug(f"Получено DLNA устройств: {len(self.dlna_devices)}")
        
        # Получить список Яндекс Станций от аддона и сопоставить с entity_id
        yandex_entity_ids = await self._fetch_yandex_stations()
        _LOGGER.debug(f"Найдено Яндекс Станций в HA: {len(yandex_entity_ids)}")
        
        if user_input is not None:
            # Сохраняем данные
            self.source_entity = user_input[CONF_SOURCE_ENTITY]
            self.api_host = user_input.get(CONF_API_HOST, DEFAULT_API_HOST)
            self.api_port = user_input.get(CONF_API_PORT, DEFAULT_API_PORT)
            self.ruark_pin = user_input.get(CONF_RUARK_PIN, "")
            self.mute_yandex_station = user_input.get(CONF_MUTE_YANDEX_STATION, DEFAULT_MUTE_YANDEX_STATION)
            
            # Определяем выбранное DLNA-устройство
            selected_device = user_input.get(CONF_TARGET_DEVICE_ID)
            if selected_device and selected_device != "manual":
                # Найти friendly_name по device_id
                friendly_name = None
                for device_id, name in self.dlna_devices:
                    if device_id == selected_device:
                        friendly_name = name
                        break
                self.target_device_id = selected_device
                self.target_friendly_name = friendly_name or selected_device
                self.target_entity = ""  # очищаем старый entity
            else:
                # Ручной ввод (запасной вариант)
                self.target_entity = user_input.get(CONF_TARGET_ENTITY, "")
                self.target_device_id = ""
                self.target_friendly_name = ""

            # Создаём финальную запись
            data = {
                CONF_AUTH_METHOD: self.auth_method,
                CONF_X_TOKEN: self.x_token,
                CONF_COOKIE: self.cookie,
                CONF_SOURCE_ENTITY: self.source_entity,
                CONF_TARGET_ENTITY: self.target_entity,
                CONF_TARGET_DEVICE_ID: self.target_device_id,
                CONF_TARGET_FRIENDLY_NAME: self.target_friendly_name,
                CONF_API_HOST: self.api_host,
                CONF_API_PORT: self.api_port,
                CONF_RUARK_PIN: self.ruark_pin,
                CONF_MUTE_YANDEX_STATION: self.mute_yandex_station,
            }
            _LOGGER.info(f"Creating config entry for Ya2DLNA (Home Assistant {ha_version})")
            return self.async_create_entry(title="Ya2DLNA Streaming", data=data)

        # Селектор для источника (Яндекс Станции)
        selector_config = {
            "filter": [
                {"domain": "media_player", "integration": "yandex_station"},
                {"domain": "media_player", "integration": "yandex_station_intents"},
            ],
            "multiple": False,
        }
        if yandex_entity_ids:
            selector_config["entity_ids"] = yandex_entity_ids
        source_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(**selector_config)
        )
        
        # Подготовить опции для выбора DLNA-устройств
        device_options = []
        if self.dlna_devices:
            for device_id, friendly_name in self.dlna_devices:
                device_options.append((device_id, friendly_name))
        device_options.append(("manual", "Ввести entity_id вручную"))
        
        # Схема данных
        fields = {
            vol.Required(CONF_SOURCE_ENTITY): source_selector,
            vol.Optional(CONF_API_PORT, default=self.api_port): int,
            vol.Optional(CONF_RUARK_PIN, default=""): str,
            vol.Optional(CONF_MUTE_YANDEX_STATION, default=DEFAULT_MUTE_YANDEX_STATION): bool,
        }
        
        if device_options:
            fields[vol.Required(CONF_TARGET_DEVICE_ID, default=device_options[0][0])] = vol.In(dict(device_options))
        else:
            # Если устройств нет, показываем только ручной ввод
            fields[vol.Required(CONF_TARGET_ENTITY)] = str
        
        # Добавляем поле для ручного ввода entity_id (скрытое по умолчанию)
        # Будем показывать только если выбрано "manual"
        # Пока просто добавим как optional
        fields[vol.Optional(CONF_TARGET_ENTITY, default="")] = str
        
        data_schema = vol.Schema(fields)

        return self.async_show_form(
            step_id="config",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return Ya2DLNAOptionsFlow(config_entry)


class Ya2DLNAOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Ya2DLNA."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self._ya2dlna_config_entry = config_entry
        self.dlna_devices = None
        super().__init__()

    async def _fetch_dlna_devices(self) -> list:
        """Запросить список DLNA-устройств у аддона."""
        # Получаем текущие настройки API
        config_data = self._ya2dlna_config_entry.data
        config_options = self._ya2dlna_config_entry.options
        def get_value(key, default=None):
            return config_options.get(key, config_data.get(key, default))
        api_host = get_value(CONF_API_HOST, DEFAULT_API_HOST)
        api_port = get_value(CONF_API_PORT, DEFAULT_API_PORT)
        url = f"http://{api_host}:{api_port}/ha/devices/dlna"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        devices = await resp.json()
                        result = []
                        for dev in devices:
                            device_id = dev.get("device_id")
                            friendly_name = dev.get("friendly_name") or dev.get("name", "Unknown")
                            result.append((device_id, friendly_name))
                        return result
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error(f"Не удалось подключиться к аддону: {e}")
            return []

    async def _fetch_yandex_stations(self) -> list:
        """Запросить список Яндекс Станций у аддона и вернуть entity_id."""
        config_data = self._ya2dlna_config_entry.data
        config_options = self._ya2dlna_config_entry.options
        def get_value(key, default=None):
            return config_options.get(key, config_data.get(key, default))
        api_host = get_value(CONF_API_HOST, DEFAULT_API_HOST)
        api_port = get_value(CONF_API_PORT, DEFAULT_API_PORT)
        url = f"http://{api_host}:{api_port}/ha/devices/yandex"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        devices = await resp.json()
                        if not devices:
                            _LOGGER.info("Аддон не обнаружил Яндекс Станций")
                            return []
                        
                        # Получить entity registry для определения интеграции
                        registry = entity_registry.async_get(self.hass)
                        yandex_entity_ids = []
                        
                        # Пройти по всем сущностям media_player
                        for entry in registry.entities.values():
                            if entry.domain != "media_player":
                                continue
                            # Проверим, принадлежит ли сущность интеграции Yandex Station
                            if entry.platform not in YANDEX_STATION_DOMAINS:
                                continue
                            # Получить состояние сущности для получения атрибутов
                            state = self.hass.states.get(entry.entity_id)
                            if not state:
                                continue
                            # Попробуем сопоставить с устройствами от аддона
                            matched = False
                            for dev in devices:
                                dev_name = dev.get("name", "").strip()
                                dev_device_id = dev.get("device_id", "").strip()
                                attrs = state.attributes
                                entity_friendly_name = attrs.get("friendly_name", "")
                                entity_device_id = attrs.get("device_id", "")
                                entry_unique_id = entry.unique_id
                                if (dev_device_id and (dev_device_id == entity_device_id or dev_device_id in entry_unique_id)):
                                    matched = True
                                    break
                                if dev_name and dev_name == entity_friendly_name:
                                    matched = True
                                    break
                            if matched:
                                yandex_entity_ids.append(entry.entity_id)
                        
                        _LOGGER.info(f"Найдено {len(yandex_entity_ids)} Яндекс Станций в Home Assistant (из {len(devices)} обнаруженных аддоном)")
                        return yandex_entity_ids
                    else:
                        _LOGGER.error(f"Ошибка при запросе Яндекс Станций: {resp.status}")
                        return []
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error(f"Не удалось подключиться к аддону: {e}")
            return []
        except Exception as e:
            _LOGGER.error(f"Неизвестная ошибка при сопоставлении Яндекс Станций: {e}")
            return []

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        ha_version = getattr(self.hass.config, "version", "unknown")
        _LOGGER.info(f"Options flow step 'init' (Home Assistant {ha_version})")
        errors = {}
        
        # Получить список DLNA-устройств от аддона
        if self.dlna_devices is None:
            self.dlna_devices = await self._fetch_dlna_devices()
        
        # Получить список Яндекс Станций от аддона и сопоставить с entity_id
        yandex_entity_ids = await self._fetch_yandex_stations()
        
        if user_input is not None:
            # Определяем выбранное DLNA-устройство
            selected_device = user_input.get(CONF_TARGET_DEVICE_ID)
            target_device_id = ""
            target_friendly_name = ""
            target_entity = ""
            if selected_device and selected_device != "manual":
                # Найти friendly_name по device_id
                friendly_name = None
                for device_id, name in self.dlna_devices:
                    if device_id == selected_device:
                        friendly_name = name
                        break
                target_device_id = selected_device
                target_friendly_name = friendly_name or selected_device
                target_entity = ""  # очищаем старый entity
            else:
                # Ручной ввод (запасной вариант)
                target_entity = user_input.get(CONF_TARGET_ENTITY, "")
                target_device_id = ""
                target_friendly_name = ""
            
            # Сохраняем данные
            data = {
                CONF_SOURCE_ENTITY: user_input.get(CONF_SOURCE_ENTITY),
                CONF_TARGET_ENTITY: target_entity,
                CONF_TARGET_DEVICE_ID: target_device_id,
                CONF_TARGET_FRIENDLY_NAME: target_friendly_name,
                CONF_API_HOST: user_input.get(CONF_API_HOST, DEFAULT_API_HOST),
                CONF_API_PORT: user_input.get(CONF_API_PORT, DEFAULT_API_PORT),
                CONF_RUARK_PIN: user_input.get(CONF_RUARK_PIN, ""),
                CONF_MUTE_YANDEX_STATION: user_input.get(CONF_MUTE_YANDEX_STATION, DEFAULT_MUTE_YANDEX_STATION),
            }
            _LOGGER.info(f"Updating options for Ya2DLNA (Home Assistant {ha_version})")
            return self.async_create_entry(title="", data=data)

        # Получим текущие значения из data и options
        config_data = self._ya2dlna_config_entry.data
        config_options = self._ya2dlna_config_entry.options
        
        def get_value(key, default=None):
            # Сначала options, потом data, потом default
            return config_options.get(key, config_data.get(key, default))
        
        current_source = get_value(CONF_SOURCE_ENTITY, "")
        current_target = get_value(CONF_TARGET_ENTITY, "")
        current_target_device_id = get_value(CONF_TARGET_DEVICE_ID, "")
        current_target_friendly_name = get_value(CONF_TARGET_FRIENDLY_NAME, "")
        current_api_host = get_value(CONF_API_HOST, DEFAULT_API_HOST)
        current_api_port = get_value(CONF_API_PORT, DEFAULT_API_PORT)
        current_ruark_pin = get_value(CONF_RUARK_PIN, "")
        current_mute_yandex_station = get_value(CONF_MUTE_YANDEX_STATION, DEFAULT_MUTE_YANDEX_STATION)

        # Селектор для источника (Яндекс Станции)
        selector_config = {
            "filter": [
                {"domain": "media_player", "integration": "yandex_station"},
                {"domain": "media_player", "integration": "yandex_station_intents"},
            ],
            "multiple": False,
        }
        if yandex_entity_ids:
            selector_config["entity_ids"] = yandex_entity_ids
        source_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(**selector_config)
        )
        
        # Подготовить опции для выбора DLNA-устройств
        device_options = []
        if self.dlna_devices:
            for device_id, friendly_name in self.dlna_devices:
                device_options.append((device_id, friendly_name))
        device_options.append(("manual", "Ввести entity_id вручную"))
        
        # Определяем текущее выбранное устройство
        current_selected = "manual"
        if current_target_device_id:
            current_selected = current_target_device_id
        elif current_target:
            current_selected = "manual"
        
        # Схема данных
        fields = {
            vol.Required(CONF_SOURCE_ENTITY, default=current_source): source_selector,
            vol.Optional(CONF_API_PORT, default=current_api_port): int,
            vol.Optional(CONF_RUARK_PIN, default=current_ruark_pin): str,
            vol.Optional(CONF_MUTE_YANDEX_STATION, default=current_mute_yandex_station): bool,
        }
        
        if device_options:
            fields[vol.Required(CONF_TARGET_DEVICE_ID, default=current_selected)] = vol.In(dict(device_options))
        else:
            # Если устройств нет, показываем только ручной ввод
            fields[vol.Required(CONF_TARGET_ENTITY, default=current_target)] = str
        
        # Добавляем поле для ручного ввода entity_id (скрытое по умолчанию)
        # Пока просто добавим как optional
        fields[vol.Optional(CONF_TARGET_ENTITY, default=current_target)] = str
        
        data_schema = vol.Schema(fields)
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )