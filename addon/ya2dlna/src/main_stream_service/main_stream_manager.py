import asyncio
from logging import getLogger
from typing import Optional

import aiohttp
from injector import inject

from core.authorization.token_storage import token_storage
from core.config.settings import settings
from core.device_manager import DeviceManager, DeviceEvent, DeviceEventType
from dlna_stream_server.handlers.dlna_controller import DLNAController
from main_stream_service.yandex_music_api import YandexMusicAPI
from yandex_station.constants import (
    ALICE_ACTIVE_STATES,
    DLNA_IDLE_VOLUME,
    STREAMING_RESTART_DELAY,
)
from yandex_station.models import Track
from yandex_station.station_controls import YandexStationControls
from yandex_station.station_ws_control import YandexStationClient

logger = getLogger(__name__)


class MainStreamManager:
    """Класс для управления стримингом с Яндекс.Станции на DLNA-устройство."""

    @inject
    def __init__(
        self,
        station_ws_client: YandexStationClient,
        station_controls: YandexStationControls,
        dlna_controls: DLNAController,
        yandex_music_api: Optional[YandexMusicAPI],
        device_manager: DeviceManager,
    ) -> None:
        self._ws_client = station_ws_client
        self._station_controls = station_controls
        self._dlna_controls = dlna_controls
        self._yandex_music_api = yandex_music_api
        self._device_manager = device_manager
        self._stream_server_url = settings.local_server_host
        self._dlna_volume = 0
        self._stream_state_running = False
        self._tasks: list[asyncio.Task] = []
        self._device_monitoring_task: Optional[asyncio.Task] = None
        # Параметры стриминга, передаваемые через API
        self._current_x_token: Optional[str] = None
        self._current_cookie: Optional[str] = None
        self._current_ruark_pin: Optional[str] = None
        self._current_mute_yandex_station: bool = True
        # Подписываемся на события устройств
        self._device_manager.add_callback(self._handle_device_event)

    def get_status(self) -> str:
        """Получить текущий статус стриминга."""
        return "streaming" if self._stream_state_running else "idle"

    def set_streaming_params(
        self,
        x_token: Optional[str] = None,
        cookie: Optional[str] = None,
        ruark_pin: Optional[str] = None,
        mute_yandex_station: bool = True,
    ) -> None:
        """Установить параметры стриминга, переданные через API."""
        self._current_x_token = x_token
        self._current_cookie = cookie
        self._current_ruark_pin = ruark_pin
        self._current_mute_yandex_station = mute_yandex_station
        
        # Сохраняем токены в глобальное хранилище для использования в других модулях
        if x_token is not None:
            token_storage.x_token = x_token
        if cookie is not None:
            token_storage.cookie = cookie
        
        # Устанавливаем PIN в DLNA контроллере
        if hasattr(self._dlna_controls, 'set_ruark_pin'):
            self._dlna_controls.set_ruark_pin(ruark_pin)
        
        logger.info(f"Параметры стриминга установлены: x_token={'***' if x_token else None}, "
                   f"cookie={'***' if cookie else None}, ruark_pin={'***' if ruark_pin else None}, "
                   f"mute_yandex_station={mute_yandex_station}")

    def _handle_device_event(self, event: DeviceEvent) -> None:
        """Обработчик событий устройств."""
        logger.debug(f"Получено событие устройства: {event.event_type} для {event.device.name}")
        
        # Если стриминг не запущен, игнорируем события
        if not self._stream_state_running:
            return
        
        # Проверяем, связано ли событие с активными устройствами
        active_source = self._device_manager.get_active_source()
        active_target = self._device_manager.get_active_target()
        
        source_device_id = active_source.device_id if active_source else None
        target_device_id = active_target.device_id if active_target else None
        
        event_device_id = event.device.device_id
        
        # Если устройство удалено или стало недоступным
        if event.event_type in (DeviceEventType.DEVICE_REMOVED, DeviceEventType.DEVICE_UNAVAILABLE):
            # Проверяем, является ли это устройство активным источником или приёмником
            if event_device_id == source_device_id or event_device_id == target_device_id:
                logger.warning(f"Активное устройство {event.device.name} стало недоступным. Останавливаем стриминг.")
                # Запускаем остановку стриминга в фоне
                asyncio.create_task(self._stop_due_to_device_unavailable())

    async def _stop_due_to_device_unavailable(self) -> None:
        """Остановить стриминг из-за недоступности устройства."""
        try:
            logger.info("Автоматическая остановка стриминга из-за недоступности устройства")
            await self.stop()
        except Exception as e:
            logger.error(f"Ошибка при автоматической остановке стриминга: {e}")

    async def start(self) -> None:
        """Запуск всех стриминговых процессов."""
        if self._stream_state_running or self._tasks:
            logger.info("⚠️ Стриминг уже запущен")
            return

        logger.info("🎵 Запуск стриминга")
        self._stream_state_running = True

        # Запускаем мониторинг устройств
        await self._start_device_monitoring()

        # Запуск WebSocket-клиента
        logger.info("🔄 Запуск WebSocket клиента")
        await self._station_controls.start_ws_client()
        logger.info("🎬 Запуск обёртки стриминга")
        stream_task = asyncio.create_task(self._wrap_streaming())
        logger.info("✅ WebSocket клиент запущен")
        self._tasks.append(stream_task)

    async def _start_device_monitoring(self) -> None:
        """Запустить мониторинг устройств."""
        try:
            await self._device_manager.start_monitoring(interval=30.0)
            logger.info("Мониторинг устройств запущен")
        except Exception as e:
            logger.error(f"Не удалось запустить мониторинг устройств: {e}")

    async def _stop_device_monitoring(self) -> None:
        """Остановить мониторинг устройств."""
        try:
            await self._device_manager.stop_monitoring()
            logger.info("Мониторинг устройств остановлен")
        except Exception as e:
            logger.error(f"Не удалось остановить мониторинг устройств: {e}")

    async def stop(self) -> None:
        """Остановка всех стриминговых процессов."""
        logger.info("🛑 Остановка стриминга...")
        self._stream_state_running = False
        
        # Остановка DLNA-воспроизведения с обработкой ошибок
        try:
            await self._dlna_controls.stop()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при остановке DLNA: {e}")
        
        # Остановка стрима на стрим-сервере
        try:
            await self._stop_stream_on_stream_server()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при остановке стрим-сервера: {e}")
        
        # Восстановление громкости DLNA
        try:
            await self._dlna_controls.set_volume(self._dlna_volume)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при установке громкости DLNA: {e}")
        
        # Выключение питания DLNA (если поддерживается)
        try:
            await self._dlna_controls.turn_power_off()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при выключении питания DLNA: {e}")
        
        # Включение звука Яндекс Станции
        try:
            await self._station_controls.unmute()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при включении звука станции: {e}")
        
        # Остановка WebSocket-клиента
        try:
            await self._station_controls.stop_ws_client()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при остановке WebSocket-клиента: {e}")

        # Отмена всех активных задач
        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("✅ Стриминг остановлен")

    async def streaming(self) -> None:
        """Основной поток управления стримингом."""
        try:
            logger.info("📡 Поток streaming() стартовал")
            await self._prepare_devices()

            last_alice_state = await self._station_controls.get_alice_state()
            last_track = Track(
                id="0",
                type="",
                artist="",
                title="",
                duration=0,
                progress=0,
                playing=False,
            )
            stuck_track_count = 0
            last_track_progress = 0
            volume_set_count = 0
            speak_count = 0

            while self._stream_state_running:
                track = await self._station_controls.get_current_track()
                current_alice_state = await self._station_controls.get_alice_state()

                # Если данные не получены, пропускаем цикл
                if track is None or current_alice_state is None:
                    logger.debug("Не удалось получить данные от станции, пропускаем цикл")
                    await asyncio.sleep(1)
                    continue

                if current_alice_state != last_alice_state:
                    current_volume = await self._station_controls.get_volume()
                    if current_volume is None:
                        logger.debug("Не удалось получить громкость станции")
                    elif (
                        current_alice_state in ALICE_ACTIVE_STATES
                        and volume_set_count < 1
                    ):
                        volume_set_count += 1
                        speak_count += 1

                        self._dlna_volume = await self._dlna_controls.get_volume()
                        await self._dlna_controls.set_volume(DLNA_IDLE_VOLUME)

                        if current_volume == 0:
                            await self._station_controls.unmute()

                if current_alice_state == "IDLE":
                    if not track.playing:
                        if last_track_progress == track.progress:
                            await self._dlna_controls.stop()
                        else:
                            stuck_track_count += 1
                            if stuck_track_count > 2:
                                logger.warning("⚠️ Трек застрял, перезапускаем")
                                if not await self._recover_stuck_track(
                                    track, last_track_progress
                                ):
                                    stuck_track_count = 0
                                else:
                                    logger.warning(
                                        "⚠️ Не удалось перезапустить трек через stop/play"
                                    )
                                    stuck_track_count = 0

                    if (
                        last_track_progress != track.progress
                        and track.type == "FmRadio"
                        and not await self._dlna_controls.is_playing()
                    ):
                        logger.info("🔁 Возобновляем воспроизведение радио")
                        await self._send_track_to_stream_server(
                            track_url=await self._station_controls.get_radio_url(),
                            radio=True,
                        )
                        await asyncio.sleep(1)

                    if track.id == last_track.id:
                        track = await self._station_controls.get_current_track()
                        if track is None:
                            logger.debug("Не удалось получить трек после обновления, пропускаем цикл")
                            continue

                    if last_track.id != track.id and track.playing:
                        if track.type == "FmRadio":
                            track_url = await self._station_controls.get_radio_url()
                            logger.info(f"🎵 URL радиостанции: {track_url}")
                        else:
                            if self._yandex_music_api is None:
                                logger.warning(
                                    "⚠️ Трек Яндекс.Музыки не может быть обработан, "
                                    "так как отсутствует токен Яндекс.Музыки. "
                                    "Пропускаем трек."
                                )
                                # Пропускаем этот трек, обновляем last_track, чтобы не зацикливаться
                                last_track = track
                                continue
                            track_url = await self._yandex_music_api.get_file_info(
                                track_id=track.id,
                                quality=settings.stream_quality,
                            )
                        if track_url is not None:
                            await self._send_track_to_stream_server(
                                track_url,
                                radio=(track.type == "FmRadio"),
                            )
                            last_track = track
                        else:
                            logger.warning(f"⚠️ Не удалось получить URL для трека {track.id}, пропускаем")
                            last_track = track

                    if speak_count > 0 and track.playing:
                        logger.info("🔁 Возвращаем громкость DLNA‑устройства")
                        await self._dlna_controls.set_volume(self._dlna_volume)

                        for _ in range(30):
                            if await self._dlna_controls.is_playing():
                                logger.info("▶️ DLNA‑устройство начало играть")
                                if self._current_mute_yandex_station:
                                    await self._station_controls.fade_out_alice_volume()
                                speak_count = 0
                                break
                            await asyncio.sleep(0.1)
                        else:
                            logger.warning(
                                "⚠️ DLNA‑устройство так и не начало играть, "
                                "перезапуск трека на стрим сервере"
                            )
                            track_url = await self._get_track_url(track)
                            if track_url is not None:
                                await self._send_track_to_stream_server(track_url)
                            await self._station_controls.fade_out_alice_volume()
                            speak_count = 0

                    if speak_count > 0 and not track.playing:
                        await self._dlna_controls.set_volume(self._dlna_volume)

                    current_volume = await self._station_controls.get_volume()

                    if (
                        (
                            current_volume > 0
                            and track.duration - track.progress > 10
                            and track.type != "FmRadio"
                        )
                        or (track.type == "FmRadio" and track.playing)
                    ) and track.playing:
                        if self._current_mute_yandex_station:
                            await self._station_controls.fade_out_alice_volume()

                    volume_set_count = 0

                if (
                    track.duration - track.progress < 1
                    and current_alice_state == "IDLE"
                    and track.playing
                    and track.type != "FmRadio"
                ):
                    await self._station_controls.unmute()

                self._log_current_track(track, current_alice_state, last_alice_state)
                last_track_progress = track.progress
                last_alice_state = current_alice_state
                logger.debug("💤 Цикл стриминга работает")
                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            logger.info("🛑 Стриминг завершён по команде остановки")
        except Exception as e:
            logger.error(f"❌ Ошибка в стриминге: {e}")
            raise

    async def _wrap_streaming(self) -> None:
        """Обёртка, которая следит за потоком стриминга и перезапускает его при падении."""
        while self._stream_state_running:
            try:
                logger.info("🚀 Запуск потока стриминга")
                await self.streaming()
            except asyncio.CancelledError:
                logger.info("🛑 Поток стриминга остановлен")
                break
            except Exception as e:
                logger.error(f"❌ Поток стриминга упал с ошибкой: {e}")
                logger.info(
                    f"🔁 Перезапуск стриминга через {STREAMING_RESTART_DELAY} секунд..."
                )
                await asyncio.sleep(STREAMING_RESTART_DELAY)
                logger.debug("🔄 Перезапуск потока после падения")

    async def _prepare_devices(self) -> None:
        """Подготовка устройств к стримингу."""
        logger.info("🔧 Подготовка устройств к стримингу...")
        await asyncio.sleep(1)
        await self._station_controls.set_default_volume()
        await self._dlna_controls.get_session_id()
        if await self._dlna_controls.get_power_status() == "0":
            await self._dlna_controls.turn_power_on()
        self._dlna_volume = await self._dlna_controls.get_volume()

    async def _send_track_to_stream_server(
        self, track_url: str, radio: bool = False
    ) -> Optional[dict]:
        """Отправляет ссылку на трек на стрим-сервер."""
        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"🎵 Отправляем трек на стрим сервер: {track_url}")
                async with session.post(
                    f"http://{self._stream_server_url}:"
                    f"{settings.local_server_port_dlna}/set_stream",
                    params={"yandex_url": track_url, "radio": str(radio).lower()},
                ) as resp:
                    response = await resp.json()
                    logger.debug(f"Ответ от DLNA API: {response}")
                    return response
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка при отправке трека на DLNA‑устройство: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Непредвиденная ошибка при отправке трека: {e}")
            return None

    async def _get_track_url(self, track: Track) -> Optional[str]:
        """Возвращает URL для трека (радио или Яндекс.Музыки)."""
        if track.type == "FmRadio":
            return await self._station_controls.get_radio_url()
        else:
            if self._yandex_music_api is None:
                logger.warning(
                    "⚠️ Трек Яндекс.Музыки не может быть обработан, "
                    "так как отсутствует токен Яндекс.Музыки."
                )
                return None
            return await self._yandex_music_api.get_file_info(
                track_id=track.id,
                quality=settings.stream_quality,
            )

    async def _stop_stream_on_stream_server(self) -> Optional[dict]:
        """Останавливает стрим на стрим-сервере."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://{self._stream_server_url}:"
                f"{settings.local_server_port_dlna}/stop_stream"
            ) as resp:
                response = await resp.json()
                logger.info(f"Ответ от стрим сервера: {response.get('message')}")
                return response

    async def _recover_stuck_track(self, track: Track, last_progress: int) -> bool:
        """Пытается перезапустить застрявший трек."""
        logger.warning(
            "⚠️ Track.playing=False при IDLE, но прогресс меняется — пробуем перезапустить"
        )
        for _ in range(3):
            await self._station_controls.stop()
            await asyncio.sleep(0.3)
            await self._station_controls.play()
            await asyncio.sleep(0.7)

            updated_track = await self._station_controls.get_current_track()
            if updated_track.id == track.id and updated_track.progress > last_progress:
                logger.info("✅ Трек успешно перезапущен")
                return True
        return False

    def _log_current_track(self, track: Track, state: str, last_state: str) -> None:
        """Логирует информацию о текущем треке."""
        logger.info(
            f"🎵 Сейчас играет: {track.id} - {track.artist} - "
            f"{track.title} - {track.progress}/{track.duration}, "
            f"статус Алисы: {state}, "
            f"предыдущий статус Алисы: {last_state}, "
            f"проигрывание: {track.playing}"
        )
