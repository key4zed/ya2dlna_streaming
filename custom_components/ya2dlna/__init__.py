"""Custom component for Ya2DLNA streaming."""
import asyncio
import logging
import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    CONF_API_HOST,
    CONF_API_PORT,
    CONF_YA_MUSIC_TOKEN,
    CONF_RUARK_PIN,
    CONF_MUTE_YANDEX_STATION,
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_MUTE_YANDEX_STATION,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the component."""
    return True


async def _send_settings_to_addon(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Отправить настройки интеграции на аддон."""
    # Получаем объединённые данные: сначала options, потом data
    def get_config(key, default=None):
        return entry.options.get(key, entry.data.get(key, default))
    
    api_host = get_config(CONF_API_HOST, DEFAULT_API_HOST)
    api_port = get_config(CONF_API_PORT, DEFAULT_API_PORT)
    ya_music_token = get_config(CONF_YA_MUSIC_TOKEN, "")
    ruark_pin = get_config(CONF_RUARK_PIN, "")
    mute_yandex_station = get_config(CONF_MUTE_YANDEX_STATION, DEFAULT_MUTE_YANDEX_STATION)
    
    if not ya_music_token:
        _LOGGER.warning("ya_music_token не указан. Аддон не сможет получить glagol токен.")
    else:
        _LOGGER.info(f"ya_music_token присутствует (длина {len(ya_music_token)} символов)")
    
    settings = {
        "ya_music_token": ya_music_token,
        "ruark_pin": ruark_pin,
        "mute_yandex_station": mute_yandex_station,
        # Остальные поля оставляем по умолчанию
        "stream_quality": "high",
        "yandex_music_timeout": 30,
        "yandex_music_cache_ttl": 300,
    }
    
    # Логируем настройки без чувствительных данных
    safe_settings = settings.copy()
    if ya_music_token:
        if len(ya_music_token) > 8:
            safe_settings["ya_music_token"] = ya_music_token[:4] + "***" + ya_music_token[-4:]
        else:
            safe_settings["ya_music_token"] = "***"
    if ruark_pin:
        safe_settings["ruark_pin"] = "***"
    
    url = f"http://{api_host}:{api_port}/settings"
    _LOGGER.info(f"Отправка настроек на аддон: {url}, настройки: {safe_settings}")
    # Детальное логирование для отладки (DEBUG уровень)
    _LOGGER.debug(f"Полный JSON настроек: {settings}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=settings, timeout=10) as resp:
                if resp.status in (200, 201, 204):
                    _LOGGER.info("Настройки успешно отправлены на аддон")
                else:
                    response_text = await resp.text()
                    _LOGGER.warning(f"Не удалось отправить настройки: статус {resp.status}, тело: {response_text}")
    except asyncio.TimeoutError:
        _LOGGER.error("Таймаут при отправке настроек на аддон")
    except Exception as e:
        _LOGGER.error(f"Ошибка при отправке настроек на аддон: {e}")


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

    # Отправить настройки на аддон
    await _send_settings_to_addon(hass, entry)

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