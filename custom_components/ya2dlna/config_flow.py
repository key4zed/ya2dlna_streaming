"""Config flow for Ya2DLNA."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import (
    DOMAIN,
    CONF_SOURCE_ENTITY,
    CONF_TARGET_ENTITY,
    CONF_API_HOST,
    CONF_API_PORT,
    CONF_X_TOKEN,
    CONF_COOKIE,
    CONF_AUTH_METHOD,
    CONF_RUARK_PIN,
    CONF_MUTE_YANDEX_STATION,
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

    async def async_step_user(self, user_input=None):
        """Handle the initial step: choose authentication method."""
        ha_version = self.hass.config.version
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
        ha_version = self.hass.config.version
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
        ha_version = self.hass.config.version
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
        ha_version = self.hass.config.version
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
        ha_version = self.hass.config.version
        _LOGGER.info(f"Config flow step 'config' (Home Assistant {ha_version})")
        errors = {}
        if user_input is not None:
            # Сохраняем данные
            self.source_entity = user_input[CONF_SOURCE_ENTITY]
            self.target_entity = user_input[CONF_TARGET_ENTITY]
            self.api_host = user_input.get(CONF_API_HOST, DEFAULT_API_HOST)
            self.api_port = user_input.get(CONF_API_PORT, DEFAULT_API_PORT)
            self.ruark_pin = user_input.get(CONF_RUARK_PIN, "")
            self.mute_yandex_station = user_input.get(CONF_MUTE_YANDEX_STATION, DEFAULT_MUTE_YANDEX_STATION)

            # Создаём финальную запись
            data = {
                CONF_AUTH_METHOD: self.auth_method,
                CONF_X_TOKEN: self.x_token,
                CONF_COOKIE: self.cookie,
                CONF_SOURCE_ENTITY: self.source_entity,
                CONF_TARGET_ENTITY: self.target_entity,
                CONF_API_HOST: self.api_host,
                CONF_API_PORT: self.api_port,
                CONF_RUARK_PIN: self.ruark_pin,
                CONF_MUTE_YANDEX_STATION: self.mute_yandex_station,
            }
            _LOGGER.info(f"Creating config entry for Ya2DLNA (Home Assistant {ha_version})")
            return self.async_create_entry(title="Ya2DLNA Streaming", data=data)

        # Селектор для источника (Яндекс Станции)
        source_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(
                filter=[
                    {"domain": "media_player", "integration": "yandex_station"},
                    {"domain": "media_player", "integration": "yandex_station_intents"},
                ],
                multiple=False,
            )
        )
        # Селектор для цели (DLNA-рендереры)
        target_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(
                filter=[
                    {"domain": "media_player", "integration": "dlna_dmr"},
                ],
                multiple=False,
            )
        )

        data_schema = vol.Schema({
            vol.Required(CONF_SOURCE_ENTITY): source_selector,
            vol.Required(CONF_TARGET_ENTITY): target_selector,
            vol.Optional(CONF_API_HOST, default=self.api_host): str,
            vol.Optional(CONF_API_PORT, default=self.api_port): int,
            vol.Optional(CONF_RUARK_PIN, default=""): str,
            vol.Optional(CONF_MUTE_YANDEX_STATION, default=DEFAULT_MUTE_YANDEX_STATION): bool,
        })

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
        super().__init__(config_entry)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        ha_version = self.hass.config.version
        _LOGGER.info(f"Options flow step 'init' (Home Assistant {ha_version})")
        errors = {}
        if user_input is not None:
            # Проверим, что выбранные сущности существуют
            source_entity = user_input.get(CONF_SOURCE_ENTITY)
            target_entity = user_input.get(CONF_TARGET_ENTITY)
            
            # Проверка доступности сущностей (опционально)
            # Пока просто сохраняем
            _LOGGER.info(f"Updating options for Ya2DLNA (Home Assistant {ha_version})")
            return self.async_create_entry(title="", data=user_input)

        # Получим текущие значения из data и options
        # В Home Assistant options переопределяют data, поэтому используем get с объединением
        config_data = self.config_entry.data
        config_options = self.config_entry.options
        
        def get_value(key, default=None):
            # Сначала options, потом data, потом default
            return config_options.get(key, config_data.get(key, default))
        
        current_source = get_value(CONF_SOURCE_ENTITY, "")
        current_target = get_value(CONF_TARGET_ENTITY, "")
        current_api_host = get_value(CONF_API_HOST, DEFAULT_API_HOST)
        current_api_port = get_value(CONF_API_PORT, DEFAULT_API_PORT)
        current_ruark_pin = get_value(CONF_RUARK_PIN, "")
        current_mute_yandex_station = get_value(CONF_MUTE_YANDEX_STATION, DEFAULT_MUTE_YANDEX_STATION)

        # Селектор для источника (Яндекс Станции)
        source_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(
                filter=[
                    {"domain": "media_player", "integration": "yandex_station"},
                    {"domain": "media_player", "integration": "yandex_station_intents"},
                ],
                multiple=False,
            )
        )
        # Селектор для цели (DLNA-рендереры)
        target_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(
                filter=[
                    {"domain": "media_player", "integration": "dlna_dmr"},
                ],
                multiple=False,
            )
        )

        data_schema = vol.Schema({
            vol.Required(CONF_SOURCE_ENTITY, default=current_source): source_selector,
            vol.Required(CONF_TARGET_ENTITY, default=current_target): target_selector,
            vol.Optional(CONF_API_HOST, default=current_api_host): str,
            vol.Optional(CONF_API_PORT, default=current_api_port): int,
            vol.Optional(CONF_RUARK_PIN, default=current_ruark_pin): str,
            vol.Optional(CONF_MUTE_YANDEX_STATION, default=current_mute_yandex_station): bool,
        })
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )