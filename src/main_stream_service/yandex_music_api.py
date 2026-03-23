import asyncio
import logging
import time
from functools import lru_cache
from typing import Optional, List

from yandex_music import ClientAsync
from yandex_music.exceptions import YandexMusicError, NetworkError, UnauthorizedError

from core.config.settings import settings

logger = logging.getLogger(__name__)


class YandexMusicAPI:
    """Класс для работы с API Яндекс.Музыки"""

    _client: ClientAsync
    _cache: dict
    _cache_ttl: int

    def __init__(self, client: ClientAsync):
        self._client = client
        self._cache = {}
        self._cache_ttl = settings.yandex_music_cache_ttl

    async def _request_with_timeout(self, coro, timeout: int = None):
        """Выполняет асинхронную операцию с таймаутом"""
        if timeout is None:
            timeout = settings.yandex_music_timeout
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"Таймаут запроса к Яндекс.Музыке (timeout={timeout} сек)")
            raise
        except YandexMusicError as e:
            logger.error(f"Ошибка Яндекс.Музыки: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            raise

    def _get_cache_key(self, track_id: int, quality: Optional[str], codecs: Optional[str]) -> str:
        """Генерирует ключ кэша"""
        return f"{track_id}:{quality}:{codecs}"

    def _get_from_cache(self, key: str) -> Optional[str]:
        """Получает значение из кэша, если оно ещё актуально"""
        if key in self._cache:
            timestamp, value = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                logger.debug(f"Кэш попадание для ключа {key}")
                return value
            else:
                del self._cache[key]
        return None

    def _set_to_cache(self, key: str, value: str):
        """Сохраняет значение в кэш"""
        self._cache[key] = (time.time(), value)
        # Очистка устаревших записей (простая, можно улучшить)
        if len(self._cache) > 100:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]

    async def get_file_info(
        self,
        track_id: int,
        quality: str = None,
        codecs: str = None,
        max_retries: int = 3,
    ) -> Optional[str]:
        """
        Возвращает прямую ссылку на трек с заданным качеством.
        Применяет кэширование и повторные попытки при ошибках.
        """
        cache_key = self._get_cache_key(track_id, quality, codecs)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            logger.info(f"✅ Используется кэшированная ссылка для трека {track_id}")
            return cached

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔍 Запрос информации о треке {track_id} (попытка {attempt}/{max_retries})")
                # Получаем трек с таймаутом
                track = await self._request_with_timeout(
                    self._client.tracks(track_id)
                )
                if not track:
                    logger.warning(f"Трек {track_id} не найден")
                    return None

                # Получаем информацию для скачивания
                download_info = await self._request_with_timeout(
                    track[0].get_download_info_async(get_direct_links=True)
                )
                if not download_info:
                    logger.warning(f"Нет информации для скачивания трека {track_id}")
                    return None

                logger.debug(f"Получены ссылки для скачивания: {download_info}")

                # Фильтрация по кодекам
                candidates = [
                    info for info in download_info
                    if not codecs or info.codec == codecs
                ]
                if not candidates:
                    logger.warning(f"Нет подходящих кодеков для трека {track_id}")
                    return None

                # Выбор качества
                if quality:
                    quality_int = int(quality)
                    logger.info(f"🔍 Ищем ссылку с качеством: {quality_int} kbps")
                    for info in candidates:
                        if info.bitrate_in_kbps == quality_int:
                            logger.info(f"✅ Найдена: {info.direct_link}")
                            self._set_to_cache(cache_key, info.direct_link)
                            return info.direct_link
                    logger.warning(f"Качество {quality_int} kbps не найдено, используем лучшее")

                # Лучшее качество
                best = max(candidates, key=lambda x: x.bitrate_in_kbps, default=None)
                if best:
                    logger.info(
                        f"✅ Лучшее качество: {best.bitrate_in_kbps} "
                        f"kbps — {best.direct_link}"
                    )
                    self._set_to_cache(cache_key, best.direct_link)
                    return best.direct_link

                return None

            except (asyncio.TimeoutError, NetworkError) as e:
                logger.warning(f"Сетевая ошибка при запросе трека {track_id}: {e}")
                if attempt == max_retries:
                    logger.error(f"Не удалось получить ссылку после {max_retries} попыток")
                    return None
                # Экспоненциальная задержка
                delay = 2 ** attempt
                logger.info(f"Повтор через {delay} секунд...")
                await asyncio.sleep(delay)
            except UnauthorizedError as e:
                logger.error(f"Ошибка авторизации Яндекс.Музыки: {e}")
                return None
            except YandexMusicError as e:
                logger.error(f"Ошибка API Яндекс.Музыки: {e}")
                return None
            except Exception as e:
                logger.error(f"Неожиданная ошибка при обработке трека {track_id}: {e}")
                return None

        return None
