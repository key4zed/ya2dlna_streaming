import logging

import aiohttp

from core.config.settings import settings
from core.authorization.yandex_session_adapted import YandexSessionAdapted, AuthException

logger = logging.getLogger(__name__)


async def get_music_token_via_x_token(x_token: str) -> str:
    """Получить OAuth-токен Яндекс.Музыки через x-token."""
    url = "https://oauth.mobile.yandex.net/1/token"
    payload = {
        "client_secret": "53bc75238f0c4d08a118e51fe9203300",
        "client_id": "23cabbbdc6cd418abb4b39c32c41195d",
        "grant_type": "x-token",
        "access_token": x_token,
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, data=payload) as response:
                response_data = await response.json()
                if "access_token" in response_data:
                    token = response_data["access_token"]
                    logger.info("✅ Токен Яндекс.Музыки успешно получен через x-token")
                    return token
                else:
                    logger.error(f"❌ Ошибка получения токена Яндекс.Музыки: {response_data}")
                    raise AuthException(f"Ошибка получения токена Яндекс.Музыки: {response_data}")
        except Exception as e:
            logger.error(f"❌ Ошибка получения токена Яндекс.Музыки: {e}")
            raise AuthException(f"Ошибка получения токена Яндекс.Музыки: {e}")


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
                    raise AuthException(f"Ошибка получения токена: {response_data}")
        except Exception as e:
            logger.error(f"❌ Ошибка получения токена: {e}")
            raise AuthException(f"Ошибка получения токена: {e}")


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
            raise AuthException(f"Ошибка получения токена: {response_data}")
    except Exception as e:
        logger.error(f"❌ Ошибка получения токена через YandexSession: {e}")
        raise AuthException(f"Ошибка получения токена через YandexSession: {e}")
    finally:
        await session.close()
