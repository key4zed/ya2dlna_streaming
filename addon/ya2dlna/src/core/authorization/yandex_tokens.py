import logging
from typing import Optional

import aiohttp

from core.authorization.token_storage import token_storage

logger = logging.getLogger(__name__)


class AuthException(Exception):
    """Исключение при ошибках авторизации."""
    pass




async def get_device_token(device_id: str, platform: str) -> str:
    """Получить glagol токен для устройства, используя доступные методы авторизации."""
    # Используем токен из хранилища
    ya_music_token = token_storage.ya_music_token
    
    if not ya_music_token:
        logger.error("❌ Не указан ya_music_token")
        raise AuthException("Не указан токен Яндекс.Музыки (ya_music_token).")

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
