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
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
)

_LOGGER = logging.getLogger(__name__)

class Ya2DLNAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ya2DLNA."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Проверка, что сущности существуют
            source = user_input[CONF_SOURCE_ENTITY]
            target = user_input[CONF_TARGET_ENTITY]
            # Можно добавить дополнительную валидацию
            return self.async_create_entry(title="Ya2DLNA Streaming", data=user_input)

        # Получить список медиа-плееров
        media_players = self.hass.states.async_entity_ids("media_player")
        source_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player", multiple=False)
        )
        target_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player", multiple=False)
        )

        data_schema = vol.Schema({
            vol.Required(CONF_SOURCE_ENTITY): source_selector,
            vol.Required(CONF_TARGET_ENTITY): target_selector,
            vol.Optional(CONF_API_HOST, default=DEFAULT_API_HOST): str,
            vol.Optional(CONF_API_PORT, default=DEFAULT_API_PORT): int,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
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
        })
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )