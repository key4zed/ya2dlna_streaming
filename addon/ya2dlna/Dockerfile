ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM $BUILD_FROM

# Установка зависимостей
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg

# Копирование исходного кода
COPY . /app
WORKDIR /app

# Установка Python-зависимостей
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Установка PYTHONPATH для корректного импорта модулей core
ENV PYTHONPATH=/app/src

# Создание директории для конфигурации
RUN mkdir -p /data

# Создание директорий для s6-overlay
RUN mkdir -p /etc/services.d/api /etc/services.d/dlna /etc/cont-init.d

# Скрипт инициализации для создания .env файла
RUN echo '#!/bin/sh' > /etc/cont-init.d/01-setup-env && \
    echo 'set -e' >> /etc/cont-init.d/01-setup-env && \
    echo '' >> /etc/cont-init.d/01-setup-env && \
    echo 'echo "=== Running s6-overlay init script ==="' >> /etc/cont-init.d/01-setup-env && \
    echo '' >> /etc/cont-init.d/01-setup-env && \
    echo '# Установка значений по умолчанию для переменных, если они пусты' >> /etc/cont-init.d/01-setup-env && \
    echo ': ${local_server_port_dlna:=8001}' >> /etc/cont-init.d/01-setup-env && \
    echo ': ${local_server_port_api:=8000}' >> /etc/cont-init.d/01-setup-env && \
    echo ': ${debug:=false}' >> /etc/cont-init.d/01-setup-env && \
    echo '' >> /etc/cont-init.d/01-setup-env && \
    echo '# Создание конфигурационного файла .env из опций аддона' >> /etc/cont-init.d/01-setup-env && \
    echo '# Записываем только непустые значения' >> /etc/cont-init.d/01-setup-env && \
    echo '{' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "${local_server_port_dlna}" ] && echo "APP_LOCAL_SERVER_PORT_DLNA=${local_server_port_dlna}"' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "${local_server_port_api}" ] && echo "APP_LOCAL_SERVER_PORT_API=${local_server_port_api}"' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "${debug}" ] && echo "APP_DEBUG=${debug}"' >> /etc/cont-init.d/01-setup-env && \
    echo '} > /app/.env' >> /etc/cont-init.d/01-setup-env && \
    echo '' >> /etc/cont-init.d/01-setup-env && \
    echo 'echo "Created /app/.env with the following content:"' >> /etc/cont-init.d/01-setup-env && \
    echo 'cat /app/.env' >> /etc/cont-init.d/01-setup-env && \
    chmod +x /etc/cont-init.d/01-setup-env

# Скрипт для API сервиса
RUN echo '#!/bin/sh' > /etc/services.d/api/run && \
    echo 'set -e' >> /etc/services.d/api/run && \
    echo '' >> /etc/services.d/api/run && \
    echo 'echo "Starting API service..."' >> /etc/services.d/api/run && \
    echo 'export PYTHONPATH=/app/src' >> /etc/services.d/api/run && \
    echo 'cd /app' >> /etc/services.d/api/run && \
    echo 'exec python3 -m src.api.main' >> /etc/services.d/api/run && \
    chmod +x /etc/services.d/api/run

# Скрипт для DLNA сервиса
RUN echo '#!/bin/sh' > /etc/services.d/dlna/run && \
    echo 'set -e' >> /etc/services.d/dlna/run && \
    echo '' >> /etc/services.d/dlna/run && \
    echo 'echo "Starting DLNA service..."' >> /etc/services.d/dlna/run && \
    echo 'export PYTHONPATH=/app/src' >> /etc/services.d/dlna/run && \
    echo 'cd /app' >> /etc/services.d/dlna/run && \
    echo 'exec python3 -m src.dlna_stream_server.main' >> /etc/services.d/dlna/run && \
    chmod +x /etc/services.d/dlna/run

# s6-overlay будет автоматически запускать сервисы из /etc/services.d
# Не устанавливаем S6_OVERLAY_SUEXEC=0 (оставляем suexec включенным по умолчанию)
# ENTRYPOINT не указываем, так как базовый образ уже имеет s6-overlay init как entrypoint