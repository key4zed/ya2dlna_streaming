import logging

import aiohttp

from core.config.settings import settings

logger = logging.getLogger(__name__)


class AuthException(Exception):
    """Исключение при ошибках авторизации."""
    pass


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
    # Если заданы x_token и cookie, используем новый метод (пока не реализован)
    # Пока что используем старый метод с ya_music_token, возможно полученным через x_token
    ya_music_token = settings.ya_music_token
    if not ya_music_token and hasattr(settings, 'x_token') and settings.x_token:
        try:
            ya_music_token = await get_music_token_via_x_token(settings.x_token)
        except AuthException as e:
            logger.error(f"Не удалось получить ya_music_token через x_token: {e}")
            # Продолжим без токена, что вызовет ошибку ниже
            pass
    if not ya_music_token:
        logger.error("❌ Не указан ya_music_token и нет x_token для его автоматического получения")
        raise AuthException("Не указан токен Яндекс.Музыки (ya_music_token)")

    url = "https://quasar.yandex.net/glagol/token"
    params = {"device_id": device_id, "platform": platform}

    headers = {
        "Authorization": f"OAuth {ya_music_token}",
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
                    logger.info("✅ Токен успешно получен")
                    return token
                else:
                    logger.error(
                        f"❌ Ошибка получения токена: {response_data}"
                    )
                    raise AuthException(f"Ошибка получения токена: {response_data}")
        except Exception as e:
            logger.error(f"❌ Ошибка получения токена: {e}")
            raise AuthException(f"Ошибка получения токена: {e}")
