# Project Coding Rules (Non-Obvious Only)

- Импорты используют `core.*` (не `src.core.*`), потому что `PYTHONPATH` установлен в `/app/src`. Убедитесь, что переменная окружения `PYTHONPATH` корректно задана в Dockerfile и окружении.
- Dependency Injection реализована через библиотеку `injector`. Модули определены в `src/core/dependencies/di_modules.py`, главный контейнер строится в `src/core/dependencies/main_di_container.py`. Используйте `@inject` декоратор для инжекции зависимостей.
- Логирование ведётся на русском языке (сообщения в логах), но имена переменных и функций — на английском. Это проектное соглашение.
- Если `APP_YA_MUSIC_TOKEN` не установлен, Yandex Music API возвращает `None`, и стриминг через Яндекс.Музыку отключается. Проверяйте наличие токена перед использованием `YandexMusicAPI`.
- Для управления Ruark R5 требуется `APP_RUARK_PIN`. Если PIN не задан, используется универсальный `DLNAController`. Выбор контроллера происходит автоматически в `DLNAControllerModule`.
- В Docker Compose используется сетевой режим `host` (network_mode: "host"), поэтому порты сервисов (8001, 8080) доступны напрямую на хосте. Учитывайте это при настройке фаервола и пробросе портов.
- Для addon Home Assistant критически важно установить `init: false` в config.yaml и `S6_OVERLAY_SUEXEC=0` в Dockerfile, чтобы избежать ошибки "s6-overlay-suexec: fatal: can only run as pid 1". Сервисные скрипты должны быть исполняемыми.
- Основной поток стриминга находится в `src/main_stream_service/main_stream_manager.py`. Он управляет взаимодействием между Яндекс.Станцией, DLNA сервером и DLNA рендерером. Не изменяйте логику без понимания всего потока.
- API endpoints определены в `src/api/endpoints/`. Они используют FastAPI и внедрённые зависимости.
- Тесты используют `pytest-asyncio` с автоматическим режимом (asyncio_mode=auto). Фикстуры определены в `conftest.py`. Моки создаются через `unittest.mock.MagicMock`.