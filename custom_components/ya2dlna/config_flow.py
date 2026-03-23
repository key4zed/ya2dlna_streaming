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
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
)

_LOGGER = logging.getLogger(__name__)

# Домены интеграций Yandex Station, которые мы можем использовать для импорта
YANDEX_STATION_DOMAINS = ["yandex_station", "yandex_station_intents"]


class Ya2DLNAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ya2DLNA."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.imported_x_token = None
        self.imported_cookie = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Проверка, что сущности существуют
            source = user_input[CONF_SOURCE_ENTITY]
            target = user_input[CONF_TARGET_ENTITY]
            # Можно добавить дополнительную валидацию
            return self.async_create_entry(title="Ya2DLNA Streaming", data=user_input)

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

        # Попытаться найти интеграции Yandex Station для импорта данных
        yandex_entries = []
        for domain in YANDEX_STATION_DOMAINS:
            yandex_entries.extend(self.hass.config_entries.async_entries(domain))

        # Если есть хотя бы одна запись, предложим импортировать
        import_options = []
        if yandex_entries:
            for entry in yandex_entries:
                import_options.append(
                    f"{entry.title} ({entry.domain})"
                )

        # Определить значения по умолчанию для x_token и cookie
        default_x_token = ""
        default_cookie = ""
        if len(yandex_entries) == 1:
            # Автоматически подставляем данные из единственной найденной интеграции
            entry = yandex_entries[0]
            default_x_token = entry.data.get("x_token", "")
            default_cookie = entry.data.get("cookie", "")
            # Также можно попробовать получить cookie из сессии, но это сложнее
            # Пока просто используем то, что есть в data

        data_schema = vol.Schema({
            vol.Required(CONF_SOURCE_ENTITY): source_selector,
            vol.Required(CONF_TARGET_ENTITY): target_selector,
            vol.Optional(CONF_API_HOST, default=DEFAULT_API_HOST): str,
            vol.Optional(CONF_API_PORT, default=DEFAULT_API_PORT): int,
            vol.Optional(CONF_X_TOKEN, default=default_x_token): str,
            vol.Optional(CONF_COOKIE, default=default_cookie): str,
        })

        note = ""
        if yandex_entries:
            note = f" Найдены интеграции: {', '.join(import_options)}. Значения x-token и cookie были автоматически подставлены, если они доступны."
        else:
            note = " Если вы используете интеграцию YandexStation, вы можете взять x-token и cookie из её настроек. Оставьте пустыми, если используете OAuth токен Яндекс Музыки."

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "note": note
            },
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
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema({
            vol.Optional(
                CONF_API_HOST,
                default=self.config_entry.options.get(CONF_API_HOST, DEFAULT_API_HOST),
            ): str,
            vol.Optional(
                CONF_API_PORT,
                default=self.config_entry.options.get(CONF_API_PORT, DEFAULT_API_PORT),
            ): int,
            vol.Optional(
                CONF_X_TOKEN,
                default=self.config_entry.options.get(CONF_X_TOKEN, ""),
            ): str,
            vol.Optional(
                CONF_COOKIE,
                default=self.config_entry.options.get(CONF_COOKIE, ""),
            ): str,
        })
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )