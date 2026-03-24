# Project Documentation Rules (Non-Obvious Only)

- Основная документация находится в `README.md` и `docs/`. Однако многие детали архитектуры и работы системы не документированы и должны быть выведены из кода.
- Проект состоит из двух основных сервисов: API (порт 8000) и DLNA сервер (порт 8080). Они могут работать независимо, но для полного стриминга требуется оба.
- Исходный код организован в пакете `src/` с подпакетами: `core/`, `api/`, `dlna_stream_server/`, `main_stream_service/`, `yandex_station/`, `ruark_audio_system/`.
- Конфигурация через переменные окружения с префиксом `APP_`. Файл `.env` должен быть создан вручную (шаблон в `.env.example` отсутствует).
- Home Assistant addon расположен в `addon/ya2dlna/`. Конфигурация addon описана в `config.yaml`. Добавок использует s6-overlay v3 и требует особой настройки (см. код).
- Поток стриминга: Яндекс.Станция обнаруживается через mDNS, управляется через WebSocket. Треки получаются через Яндекс.Музыку API или радио URL. Поток передаётся на DLNA сервер, который транслирует на DLNA рендерер.
- Критические файлы для понимания архитектуры:
  - `src/main_stream_service/main_stream_manager.py` – основной цикл стриминга.
  - `src/core/dependencies/di_modules.py` – инъекция зависимостей.
  - `src/core/config/settings.py` – настройки.
  - `src/api/endpoints/routers.py` – маршруты API.
  - `src/dlna_stream_server/handlers/dlna_controller.py` – управление DLNA устройством.
- Тесты расположены в `tests/` и используют `pytest-asyncio`. Фикстуры определены в `conftest.py`.
- Проект поддерживает только архитектуры `aarch64` и `amd64` для addon. Остальные архитектуры удалены.