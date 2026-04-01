from typing import Optional
import asyncio
import logging
from injector import Module, provider, singleton
from yandex_music import ClientAsync

from core.config.settings import settings
from core.device_manager import DeviceManager
from dlna_stream_server.handlers.dlna_controller import DLNAController, RuarkR5Controller
from dlna_stream_server.handlers.stream_handler import StreamHandler
from main_stream_service.main_stream_manager import MainStreamManager
from main_stream_service.yandex_music_api import YandexMusicAPI
from yandex_station.mdns_device_finder import DeviceFinder
from yandex_station.protobuf_parser import Protobuf
from yandex_station.station_controls import YandexStationControls
from yandex_station.station_ws_control import YandexStationClient
from core.authorization.yandex_tokens import get_music_token_via_x_token, AuthException

logger = logging.getLogger(__name__)


class NullYandexMusicAPI(YandexMusicAPI):
    """Заглушка YandexMusicAPI, которая ничего не делает (используется когда токен отсутствует)"""
    def __init__(self):
        # Создаём клиент с фейковым токеном, но он никогда не будет использоваться
        super().__init__(ClientAsync("fake_token"))
        self._is_null = True

    async def get_track_url(self, track_id: int, quality: Optional[str] = None, codecs: Optional[str] = None) -> Optional[str]:
        logger.debug("NullYandexMusicAPI: запрос к треку игнорируется")
        return None

    async def search_track(self, query: str) -> Optional[int]:
        logger.debug("NullYandexMusicAPI: поиск трека игнорируется")
        return None

    async def get_album_tracks(self, album_id: int) -> Optional[list[int]]:
        logger.debug("NullYandexMusicAPI: получение треков альбома игнорируется")
        return None

    async def get_playlist_tracks(self, user_id: str, playlist_id: str) -> Optional[list[int]]:
        logger.debug("NullYandexMusicAPI: получение треков плейлиста игнорируется")
        return None


class MainStreamManagerModule(Module):
    """Класс для управления зависимостями MainStreamManager"""
    @singleton
    @provider
    def provide_main_stream_manager(
        self,
        station_ws_client: YandexStationClient,
        station_controls: YandexStationControls,
        dlna_controls: DLNAController,
        yandex_music_api: Optional[YandexMusicAPI]
    ) -> MainStreamManager:
        return MainStreamManager(
            station_ws_client=station_ws_client,
            station_controls=station_controls,
            dlna_controls=dlna_controls,
            yandex_music_api=yandex_music_api
        )


class DeviceFinderModule(Module):
    """Класс для управления зависимостями DeviceFinder"""
    @singleton
    @provider
    def provide_device_finder(self) -> DeviceFinder:
        return DeviceFinder()


class YandexStationClientModule(Module):
    """Класс для управления зависимостями Yandex Station Client"""
    @singleton
    @provider
    def provide_yandex_station_client(self) -> YandexStationClient:
        return YandexStationClient(device_finder=DeviceFinder())


class YandexStationControlsModule(Module):
    """Класс для управления зависимостями Yandex Station Controls"""
    @singleton
    @provider
    def provide_yandex_station_controls(
        self,
        ws_client: YandexStationClient,
        protobuf: Protobuf
    ) -> YandexStationControls:
        return YandexStationControls(ws_client, protobuf)


class YandexMusicAPIModule(Module):
    """Класс для управления зависимостями Yandex Music API"""
    @singleton
    @provider
    def provide_yandex_music_api(self) -> YandexMusicAPI:
        ya_music_token = settings.ya_music_token
        if not ya_music_token and settings.x_token and settings.x_token.strip():
            # Попытаться получить ya_music_token через x_token
            try:
                # Создаём новый event loop, так как мы в синхронном контексте
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                ya_music_token = loop.run_until_complete(
                    get_music_token_via_x_token(settings.x_token)
                )
                loop.close()
                logger.info("✅ ya_music_token успешно получен через x_token")
            except (AuthException, Exception) as e:
                logger.error(f"❌ Не удалось получить ya_music_token через x_token: {e}")
                ya_music_token = None
        if not ya_music_token:
            logger.warning("ya_music_token не указан, используется NullYandexMusicAPI")
            return NullYandexMusicAPI()
        client = ClientAsync(ya_music_token)
        return YandexMusicAPI(client=client)


class DLNAControllerModule(Module):
    """Класс для управления зависимостями DLNA‑контроллера (RuarkR5Controller или универсальный)"""
    @singleton
    @provider
    def provide_dlna_controller(
        self,
    ) -> DLNAController:
        # Используем имя устройства из настроек, если указано, иначе "DLNA Renderer"
        device_name = settings.dlna_device_name or "DLNA Renderer"
        if settings.ruark_pin:
            # Если указан PIN, используем RuarkR5Controller
            return RuarkR5Controller(device_name=device_name)
        else:
            # Иначе используем универсальный DLNA‑контроллер
            return DLNAController(device_name=device_name)


class StreamHandlerModule(Module):
    """Класс для управления зависимостями StreamHandler"""
    @singleton
    @provider
    def provide_stream_handler(
        self, dlna_controls: DLNAController
    ) -> StreamHandler:
        return StreamHandler(dlna_controls)


class ProtobufModule(Module):
    """Класс для управления зависимостями Protobuf"""
    @singleton
    @provider
    def provide_protobuf(self) -> Protobuf:
        return Protobuf()


class DeviceManagerModule(Module):
    """Класс для управления зависимостями DeviceManager"""
    @singleton
    @provider
    def provide_device_manager(self) -> DeviceManager:
        return DeviceManager()


class RuarkR5ControllerModule(DLNAControllerModule):
    """Алиас для обратной совместимости (старое название модуля)"""
    pass
