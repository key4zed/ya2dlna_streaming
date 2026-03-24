# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Build/Test Commands

- **Run tests**: `pytest` (uses pytest-asyncio, configured in pytest.ini)
- **Run single test**: `pytest tests/test_client.py -v`
- **Build Docker image**: `docker build -t ya2dlna .`
- **Run services via Docker Compose**: `docker-compose up -d` (starts API on port 8001 and DLNA on port 8080)
- **Run API service manually**: `python -m src.api.main`
- **Run DLNA server manually**: `python -m src.dlna_stream_server.main`

## Configuration

- Settings are loaded from `.env` file with prefix `APP_` (e.g., `APP_YA_MUSIC_TOKEN`).
- Configuration class is `Settings` in `src/core/config/settings.py`.
- Environment variable `DOCKER_ENV=true` is used to detect Docker environment.

## Dependency Injection

- Uses `injector` library for DI.
- Modules are defined in `src/core/dependencies/di_modules.py`.
- Main container is built in `src/core/dependencies/main_di_container.py`.
- Services are injected via `@inject` decorator.

## Code Style

- Type annotations are used extensively.
- Async/await pattern for all I/O operations.
- Logging via standard `logging` module with Russian messages in logs.
- Docstrings are in Russian, but variable/function names are in English.
- Imports follow: standard library, third-party, local modules.

## Testing

- Tests are in `tests/` directory.
- Uses `pytest-asyncio` for async tests.
- Fixtures are defined in `conftest.py`.
- Mocking is done with `unittest.mock.MagicMock`.

## Home Assistant Add‑on

- Add‑on configuration is in `addon/ya2dlna/config.yaml`.
- Uses s6‑overlay v3; requires `init: false` in config to avoid PID 1 conflict.
- Set `S6_OVERLAY_SUEXEC=0` in Dockerfile to disable suexec.
- Service scripts are in `addon/ya2dlna/services.d/` (must be executable).
- The add‑on supports only `aarch64` and `amd64` architectures (deprecated `armhf`, `armv7`, `i386` removed).

## Critical Patterns

- Device discovery: Yandex Stations via mDNS, DLNA renderers via UPnP.
- Streaming flow: Yandex Station → DLNA server → DLNA renderer.
- The main streaming loop is in `src/main_stream_service/main_stream_manager.py`.
- API endpoints are defined in `src/api/endpoints/`.
- DLNA stream server uses `upnpclient` to control renderers.

## Gotchas

- If `APP_YA_MUSIC_TOKEN` is not set, Yandex Music streaming is disabled (API returns `None`).
- Ruark R5 controller is used only when `APP_RUARK_PIN` is set.
- The DLNA device name can be configured via `APP_DLNA_DEVICE_NAME`.
- In Docker, network mode is `host` for both services (ports 8001 and 8080).
- Home Assistant integration expects API host `hassio` when running as add‑on, otherwise `localhost`.