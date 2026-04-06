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

    # Log Home Assistant version for debugging
    ha_version = getattr(hass.config, "version", "unknown")
    _LOGGER.info(
        f"Setting up Ya2DLNA integration (Home Assistant {ha_version})"
    )

    # Log config entry data (without sensitive info)
    safe_data = {k: v for k, v in entry.data.items() if k not in ["x_token", "cookie", "ruark_pin"]}
    _LOGGER.info(f"Config entry data: {safe_data}")
    _LOGGER.info(f"Config entry options: {entry.options}")

    # Forward setup to switch and select platforms
    # Try new method first, fallback to old for compatibility
    platforms = ["switch", "select"]
    try:
        await hass.config_entries.async_forward_entry_setups(entry, platforms)
        _LOGGER.info(f"Platforms {platforms} forwarded successfully")
    except AttributeError:
        # Fallback for older Home Assistant versions
        _LOGGER.warning(
            f"Home Assistant {ha_version} does not support async_forward_entry_setups, using old method"
        )
        for platform in platforms:
            await hass.config_entries.async_forward_entry_setup(entry, platform)
            _LOGGER.info(f"Platform {platform} forwarded (old method)")
    except Exception as e:
        _LOGGER.error(f"Error forwarding platforms: {e}", exc_info=True)
        return False
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    platforms = ["switch", "select"]
    # Try new method first, fallback to old for compatibility
    try:
        await hass.config_entries.async_forward_entry_unloads(entry, platforms)
    except AttributeError:
        # Fallback for older Home Assistant versions
        for platform in platforms:
            await hass.config_entries.async_forward_entry_unload(entry, platform)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True