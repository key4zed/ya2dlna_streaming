import asyncio
import re
import urllib.parse
from logging import getLogger
from typing import Any, Dict, List, Literal, Optional

import aiohttp
import upnpclient

from core.config.settings import settings
from ruark_audio_system.constants import META_INFO

SESSION_ID_REGEX = re.compile(r"<sessionId>(.*?)</sessionId>")
POWER_STATUS_REGEX = re.compile(r"<value><u8>(.*?)</u8></value>")

logger = getLogger(__name__)

PlayModeType = Literal["NORMAL", "SHUFFLE", "REPEAT_ALL"]
SeekUnitType = Literal["REL_TIME", "ABS_TIME", "ABS_COUNT", "TRACK_NR"]


class DLNAController:
    """Универсальный контроллер для DLNA‑рендереров."""

    def __init__(
            self,
            device_name: Optional[str] = None,
            device: Optional[upnpclient.Device] = None
    ) -> None:
        """
        Инициализация контроллера.

        :param device_name: имя устройства для поиска (если device не указан)
        :param device: готовый объект upnpclient.Device (если уже найден)
        """
        self.device_name = device_name
        self.device: Optional[upnpclient.Device] = device
        self.ip: Optional[str] = None
        self.services: Dict[str, Any] = {}
        self.av_transport = None
        self.connection_manager = None
        self.rendering_control = None

        if self.device is None and self.device_name:
            self.refresh_device()
        elif self.device is not None:
            self._setup_services()

    def refresh_device(self) -> None:
        """Обновление устройства по имени."""
        logger.info(f"🔄 Обновление устройства {self.device_name}")
        self.device = self.find_device(self.device_name)
        if not self.device:
            logger.warning(f"⚠ Устройство '{self.device_name}' не найдено в сети!")
            return
        self._setup_services()

    def _setup_services(self) -> None:
        """Настройка сервисов после обнаружения устройства."""
        self.ip = self.get_device_ip()
        self.services = {
            service.service_type: service for service in self.device.services
        }
        self.av_transport = self.services.get(
            "urn:schemas-upnp-org:service:AVTransport:1"
        )
        self.connection_manager = self.services.get(
            "urn:schemas-upnp-org:service:ConnectionManager:1"
        )
        self.rendering_control = self.services.get(
            "urn:schemas-upnp-org:service:RenderingControl:1"
        )
        logger.info(f"Устройство настроено: {self.device.friendly_name} "
                    f"({self.device.location})")

    def find_device(self, device_name: str) -> Optional[upnpclient.Device]:
        """Находит устройство по имени."""
        logger.info(f"Начинаем поиск устройства: {device_name}")
        try:
            devices = upnpclient.discover()
            logger.info(f"Найдено {len(devices)} устройств")
            for device in devices:
                try:
                    logger.info(
                        f"Проверяем устройство: {device.friendly_name}"
                    )
                    if device_name in device.friendly_name:
                        logger.info(
                            "Найдено подходящее устройство: "
                            f"{device.friendly_name}"
                        )
                        return device
                except Exception as e:
                    logger.error(
                        "Ошибка при обработке устройства "
                        f"{device}: {str(e)}"
                    )
                    continue
            logger.info(f"Не найдено устройств с именем: {device_name}")
            return None
        except Exception as e:
            logger.error(f"Error during device discovery: {str(e)}")
            return None

    def get_device_ip(self) -> Optional[str]:
        """Получает IP‑адрес устройства."""
        if self.device:
            parsed_url = urllib.parse.urlparse(self.device.location)
            return parsed_url.hostname
        return None

    def print_available_services(self):
        """Выводит список всех поддерживаемых сервисов."""
        logger.info("\n📡 Доступные UPnP сервисы:")
        for service in self.services:
            logger.info(f" - {service}")

    #  ConnectionManager
    async def get_protocol_info(self) -> Dict[str, str]:
        """Получение списка поддерживаемых форматов."""
        if self.connection_manager is None:
            logger.warning("❌ connection_manager не инициализирован, возвращаем пустой словарь")
            return {}
        return await asyncio.to_thread(self.connection_manager.GetProtocolInfo)

    async def get_current_connection_ids(self) -> List[str]:
        """Получение списка активных соединений."""
        if self.connection_manager is None:
            logger.warning("❌ connection_manager не инициализирован, возвращаем пустой список")
            return []
        return (await asyncio.to_thread(
            self.connection_manager.GetCurrentConnectionIDs
        ))["ConnectionIDs"]

    async def get_current_connection_info(
        self, connection_id: int
    ) -> Dict[str, Any]:
        """Получение информации о соединении."""
        if self.connection_manager is None:
            logger.warning("❌ connection_manager не инициализирован, возвращаем пустой словарь")
            return {}
        return await asyncio.to_thread(
            self.connection_manager.GetCurrentConnectionInfo,
            ConnectionID=connection_id
        )

    #   AVTransport
    async def set_av_transport_uri(self, uri: str) -> None:
        """Установка нового потока."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, пропускаем установку URI")
            return
        metadata = self.generate_metadata_with_fake_duration(uri)
        await asyncio.to_thread(
            self.av_transport.SetAVTransportURI,
            InstanceID=0,
            CurrentURI=uri,
            CurrentURIMetaData=metadata
        )
        logger.info(f"🎵 Поток установлен: {uri}")

    async def play(self) -> None:
        """Запуск воспроизведения."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, пропускаем воспроизведение")
            return
        await asyncio.to_thread(
            self.av_transport.Play, InstanceID=0, Speed="1"
        )
        logger.info("▶ Воспроизведение запущено")

    async def pause(self) -> None:
        """Приостановка воспроизведения."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, пропускаем паузу")
            return
        await asyncio.to_thread(self.av_transport.Pause, InstanceID=0)
        logger.info("⏸ Воспроизведение приостановлено")

    async def stop(self) -> None:
        """Остановка воспроизведения."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, пропускаем остановку")
            return
        playing = await self.is_playing()
        if playing:
            await asyncio.to_thread(self.av_transport.Stop, InstanceID=0)
            logger.info("⏹ Воспроизведение остановлено")

    async def next_track(self) -> None:
        """Переключение на следующий трек."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, пропускаем next_track")
            return
        await asyncio.to_thread(self.av_transport.Next, InstanceID=0)
        logger.info("⏭ Следующий трек")

    async def previous_track(self) -> None:
        """Переключение на предыдущий трек."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, пропускаем previous_track")
            return
        await asyncio.to_thread(self.av_transport.Previous, InstanceID=0)
        logger.info("⏮ Предыдущий трек")

    async def seek(self, target: str, unit: SeekUnitType = "REL_TIME") -> None:
        """Перемотка на указанное время (например, '00:01:30')."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, пропускаем перемотку")
            return
        await asyncio.to_thread(
            self.av_transport.Seek,
            InstanceID=0,
            Unit=unit,
            Target=target
        )
        logger.info(f"⏩ Перемотка на {target}")

    async def get_media_info(self) -> Dict[str, Any]:
        """Получение информации о текущем медиафайле."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, возвращаем пустой словарь")
            return {}
        return await asyncio.to_thread(
            self.av_transport.GetMediaInfo, InstanceID=0
        )

    async def get_position_info(self) -> Dict[str, Any]:
        """Получение информации о текущей позиции воспроизведения."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, возвращаем пустой словарь")
            return {}
        return await asyncio.to_thread(
            self.av_transport.GetPositionInfo, InstanceID=0
        )

    async def get_transport_info(self) -> Dict[str, Any]:
        """Получение информации о состоянии транспорта."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, возвращаем пустой словарь")
            return {}
        return await asyncio.to_thread(
            self.av_transport.GetTransportInfo,
            InstanceID=0
        )

    async def get_transport_settings(self) -> Dict[str, Any]:
        """Получение настроек воспроизведения."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, возвращаем пустой словарь")
            return {}
        return await asyncio.to_thread(
            self.av_transport.GetTransportSettings,
            InstanceID=0
        )

    async def is_playing(self, timeout: float = 5.0) -> bool:
        """Проверка, воспроизводится ли что‑либо, с защитой по таймауту."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, считаем что не воспроизводится")
            return False
        try:
            state = await asyncio.wait_for(
                self.get_transport_info(), timeout=timeout
            )
            return state.get("CurrentTransportState") == "PLAYING"
        except asyncio.TimeoutError:
            logger.warning("⚠️ Timeout при get_transport_info()")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке is_playing: {e}")
            return False

    async def set_play_mode(self, mode: PlayModeType) -> None:
        """Установка режима воспроизведения."""
        if self.av_transport is None:
            logger.warning("❌ av_transport не инициализирован, пропускаем установку режима воспроизведения")
            return
        await asyncio.to_thread(
            self.av_transport.SetPlayMode,
            InstanceID=0,
            NewPlayMode=mode
        )
        logger.info(f"🔄 Установлен режим воспроизведения: {mode}")

    #   RenderingControl
    async def get_volume(self) -> int:
        """Получение текущего уровня громкости."""
        if self.rendering_control is None:
            logger.warning("❌ rendering_control не инициализирован, возвращаем 0")
            return 0
        result = await asyncio.to_thread(
            self.rendering_control.GetVolume,
            InstanceID=0,
            Channel="Master"
        )
        return result["CurrentVolume"]

    async def set_volume(self, volume: int) -> None:
        """Установка громкости (0‑100)."""
        if self.rendering_control is None:
            logger.warning("❌ rendering_control не инициализирован, пропускаем установку громкости")
            return
        # Проверяем, поддерживает ли устройство SetVolume
        if not hasattr(self.rendering_control, "SetVolume"):
            logger.warning("❌ Устройство не поддерживает SetVolume, пропускаем установку громкости")
            return
        try:
            await asyncio.to_thread(
                self.rendering_control.SetVolume,
                InstanceID=0,
                Channel="Master",
                DesiredVolume=volume
            )
            logger.info(f"🔊 Громкость установлена на {volume}")
        except AttributeError as e:
            logger.warning(f"❌ Ошибка AttributeError при установке громкости: {e}")
        except Exception as e:
            logger.warning(f"❌ Неожиданная ошибка при установке громкости: {e}")

    async def get_mute(self) -> bool:
        """Получение состояния mute."""
        if self.rendering_control is None:
            logger.warning("❌ rendering_control не инициализирован, возвращаем False")
            return False
        result = await asyncio.to_thread(
            self.rendering_control.GetMute,
            InstanceID=0,
            Channel="Master"
        )
        return bool(result["CurrentMute"])

    async def set_mute(self, mute: bool) -> None:
        """Отключение/включение звука."""
        if self.rendering_control is None:
            logger.warning("❌ rendering_control не инициализирован, пропускаем установку mute")
            return
        await asyncio.to_thread(
            self.rendering_control.SetMute,
            InstanceID=0,
            Channel="Master",
            DesiredMute=int(mute)
        )
        logger.info("🔇 Звук отключен" if mute else "🔊 Звук включен")

    async def fade_out(
            self,
            start_volume: int,
            min_volume: int = 2,
            step: int = 6,
            delay: float = 0.1
    ):
        """Плавное уменьшение громкости в несколько шагов."""
        if self.rendering_control is None:
            logger.warning("❌ rendering_control не инициализирован, пропускаем fade_out")
            return
        
        volume = start_volume - start_volume % 2

        logger.info(
            f"🔉 Плавное снижение громкости: "
            f"{volume} ➝ {min_volume} шагом {step}")

        try:
            for v in range(volume, min_volume - 1, -step):
                logger.info(f"  ➤ Устанавливаем громкость: {v}")
                await self.set_volume(v)
                await asyncio.sleep(delay)

            logger.info("✅ Плавное снижение громкости завершено")

        except Exception as e:
            logger.error(f"❌ Ошибка при снижении громкости: {e}")

    async def list_presets(self) -> str:
        """Получение списка пресетов."""
        if self.rendering_control is None:
            logger.warning("❌ rendering_control не инициализирован, возвращаем пустую строку")
            return ""
        result = await asyncio.to_thread(
            self.rendering_control.ListPresets,
            InstanceID=0
        )
        return result["CurrentPresetNameList"]

    async def select_preset(self, preset_name: str) -> None:
        """Выбор пресета."""
        if self.rendering_control is None:
            logger.warning("❌ rendering_control не инициализирован, пропускаем выбор пресета")
            return
        await asyncio.to_thread(
            self.rendering_control.SelectPreset,
            InstanceID=0,
            PresetName=preset_name
        )
        logger.info(f"🎛 Выбран пресет: {preset_name}")

    def generate_metadata_with_fake_duration(self, uri: str) -> str:
        """Генерация DIDL‑Lite метаданных с длительностью 999999 часов."""
        logger.info(f"🔊 Генерируем метаданные для {uri}")
        return META_INFO.format(url=uri)

    async def print_status(self) -> None:
        """Вывод текущего состояния устройства."""
        if self.device is None:
            logger.warning("❌ Устройство не инициализировано, невозможно вывести статус")
            return
        logger.info("🎶 Текущее состояние DLNA‑устройства:")
        volume = await self.get_volume()
        mute = await self.get_mute()
        media_info = await self.get_media_info()
        position_info = await self.get_position_info()
        transport_info = await self.get_transport_info()

        logger.info(f"🔊 Громкость: {volume}")
        logger.info(f"🔇 Mute: {mute}")
        logger.info(f"📀 Медиа: {media_info}")
        logger.info(f"⏱ Позиция: {position_info}")
        logger.info(f"🚀 Транспорт: {transport_info}")

    # Методы, специфичные для Ruark R5, с заглушками для универсального контроллера
    async def get_session_id(self) -> str:
        """Заглушка для получения session_id (только для Ruark)."""
        logger.warning("⚠️ Универсальный DLNA‑контроллер не поддерживает session_id")
        return ""

    async def get_power_status(self) -> str:
        """Заглушка для статуса питания (предполагаем, что устройство включено)."""
        logger.warning("⚠️ Универсальный DLNA‑контроллер не поддерживает управление питанием")
        return "1"

    async def turn_power_on(self) -> bool:
        """Заглушка для включения питания (ничего не делает)."""
        logger.warning("⚠️ Универсальный DLNA‑контроллер не поддерживает включение питания")
        return True

    async def turn_power_off(self) -> bool:
        """Заглушка для выключения питания (ничего не делает)."""
        logger.warning("⚠️ Универсальный DLNA‑контроллер не поддерживает выключение питания")
        return True


class RuarkR5Controller(DLNAController):
    """Контроллер для Ruark R5 с поддержкой специфичных функций (PIN)."""

    _session_id: str

    def __init__(
            self,
            device_name: str = "Ruark R5",
            device: Optional[upnpclient.Device] = None
    ) -> None:
        super().__init__(device_name=device_name, device=device)
        self.print_available_services()

    async def get_session_id(self) -> str:
        """Получение session_id (требует PIN)."""
        if not settings.ruark_pin:
            logger.warning("⚠️ PIN не указан, невозможно получить session_id")
            return ""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.ip}/fsapi/CREATE_SESSION/"
                    f"?pin={settings.ruark_pin}"
                ) as response:
                    content = await response.text()
                    self._session_id = (
                        SESSION_ID_REGEX.search(content).group(1)
                    )
                    return self._session_id
        except Exception as e:
            logger.error(f"Ошибка при получении session_id: {e}")
            return ""

    async def get_power_status(self) -> str:
        """Получение статуса питания (требует PIN и session_id)."""
        if not settings.ruark_pin:
            logger.warning("⚠️ PIN не указан, невозможно получить статус питания")
            return ""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.ip}/fsapi/GET/"
                    f"netRemote.sys.power?pin={settings.ruark_pin}"
                    f"&sid={self._session_id}"
                ) as response:
                    content = await response.text()
                    status = POWER_STATUS_REGEX.search(content).group(1)
                    logger.info(f"🔌 Статус питания: {status}")
                    return status
        except Exception as e:
            logger.error(f"Ошибка при получении статуса питания: {e}")
            return ""

    async def turn_power_on(self) -> bool:
        """Включение питания (требует PIN и session_id)."""
        if not settings.ruark_pin:
            logger.warning("⚠️ PIN не указан, невозможно включить питание")
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.ip}/fsapi/SET/"
                    f"netRemote.sys.power?pin={settings.ruark_pin}"
                    f"&sid={self._session_id}&value=1"
                ) as response:
                    if response.status == 200:
                        status = await self.get_power_status()
                        if status == "1":
                            logger.info("🔌 Питание включено")
                            return True
        except Exception as e:
            logger.error(f"Ошибка при включении питания: {e}")
            return False
        return False

    async def turn_power_off(self) -> bool:
        """Выключение питания (требует PIN и session_id)."""
        if not settings.ruark_pin:
            logger.warning("⚠️ PIN не указан, невозможно выключить питание")
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.ip}/fsapi/SET/"
                    f"netRemote.sys.power?pin={settings.ruark_pin}"
                    f"&sid={self._session_id}&value=0"
                ) as response:
                    if response.status == 200:
                        status = await self.get_power_status()
                        if status == "0":
                            logger.info("🔌 Питание выключено")
                            return True
        except Exception as e:
            logger.error(f"Ошибка при выключении питания: {e}")
            return False
        return False