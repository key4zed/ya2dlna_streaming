import logging

import aiohttp

from core.config.settings import settings
from core.authorization.yandex_session_adapted import YandexSessionAdapted

logger = logging.getLogger(__name__)


async def get_device_token(device_id: str, platform: str) -> str:
    """Получить glagol токен для устройства, используя доступные методы авторизации."""
    # Если заданы x_token и cookie, используем новый метод
    if hasattr(settings, 'x_token') and settings.x_token:
        cookie = getattr(settings, 'cookie', None)
        return await get_device_token_via_session(device_id, platform, settings.x_token, cookie)
    # Иначе используем старый метод с ya_music_token
    return await get_device_token_via_oauth(device_id, platform)


async def get_device_token_with_auth(device_id: str, platform: str, x_token: str, cookie: str | None = None) -> str:
    """Получить glagol токен с использованием переданных x_token и cookie (динамическая авторизация)."""
    return await get_device_token_via_session(device_id, platform, x_token, cookie)


async def get_device_token_via_oauth(device_id: str, platform: str) -> str:
    """Получить glagol токен через OAuth Яндекс Музыки (старый метод)."""
    url = "https://quasar.yandex.net/glagol/token"
    params = {"device_id": device_id, "platform": platform}

    headers = {
        "Authorization": f"OAuth {settings.ya_music_token}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                url, headers=headers, params=params
            ) as response:
                response_data = await response.json()
                if (response_data.get("status") == "ok" and
                        "token" in response_data):
                    token = response_data["token"]
                    logger.info("✅ Токен успешно получен (через OAuth Яндекс Музыки)")
                    return token
                else:
                    logger.error(
                        f"❌ Ошибка получения токена: {response_data}"
                    )
                    return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения токена: {e}")
            return None


async def get_device_token_via_session(device_id: str, platform: str, x_token: str, cookie: str | None = None) -> str:
    """Получить glagol токен через YandexSession (новый метод)."""
    logger.info("Получение glagol токена через YandexSession...")
    session = YandexSessionAdapted(x_token=x_token, cookie=cookie)
    try:
        # Используем метод get из YandexSessionAdapted, который уже включает авторизацию
        params = {"device_id": device_id, "platform": platform}
        r = await session.get("https://quasar.yandex.net/glagol/token", params=params)
        response_data = await r.json()
        if response_data.get("status") == "ok" and "token" in response_data:
            token = response_data["token"]
            logger.info("✅ Токен успешно получен (через YandexSession)")
            return token
        else:
            logger.error(f"❌ Ошибка получения токена: {response_data}")
            return None
    except Exception as e:
        logger.error(f"❌ Ошибка получения токена через YandexSession: {e}")
        return None
    finally:
        await session.close()
