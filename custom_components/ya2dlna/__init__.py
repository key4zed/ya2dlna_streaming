"""Custom component for Ya2DLNA streaming."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Forward setup to switch platform
    # Try new method first, fallback to old for compatibility
    try:
        await hass.config_entries.async_forward_entry_setups(entry, ["switch"])
    except AttributeError:
        # Fallback for older Home Assistant versions
        await hass.config_entries.async_forward_entry_setup(entry, "switch")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Try new method first, fallback to old for compatibility
    try:
        await hass.config_entries.async_forward_entry_unloads(entry, ["switch"])
    except AttributeError:
        # Fallback for older Home Assistant versions
        await hass.config_entries.async_forward_entry_unload(entry, "switch")
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True