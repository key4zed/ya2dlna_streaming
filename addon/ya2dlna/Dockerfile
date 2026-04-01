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

# Настройка s6-overlay v3
ENV S6_OVERLAY_SUEXEC=0

# Создание всех необходимых директорий для s6-overlay
RUN mkdir -p /etc/services.d/api /etc/services.d/dlna /etc/cont-init.d

# Создание скрипта инициализации для создания .env файла из переменных окружения с значениями по умолчанию
# Записываем только непустые значения
RUN echo '#!/bin/sh' > /etc/cont-init.d/01-setup-env && \
    echo '# Установка значений по умолчанию для переменных, если они пусты' >> /etc/cont-init.d/01-setup-env && \
    echo ': ${local_server_host:=0.0.0.0}' >> /etc/cont-init.d/01-setup-env && \
    echo ': ${local_server_port_dlna:=8001}' >> /etc/cont-init.d/01-setup-env && \
    echo ': ${local_server_port_api:=8000}' >> /etc/cont-init.d/01-setup-env && \
    echo ': ${stream_quality:=192}' >> /etc/cont-init.d/01-setup-env && \
    echo ': ${debug:=false}' >> /etc/cont-init.d/01-setup-env && \
    echo ': ${mute_yandex_station:=true}' >> /etc/cont-init.d/01-setup-env && \
    echo '{' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "$ya_music_token" ] && echo "APP_YA_MUSIC_TOKEN=$ya_music_token"' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "$x_token" ] && echo "APP_X_TOKEN=$x_token"' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "$cookie" ] && echo "APP_COOKIE=$cookie"' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "$ruark_pin" ] && echo "APP_RUARK_PIN=$ruark_pin"' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "$local_server_host" ] && echo "APP_LOCAL_SERVER_HOST=$local_server_host"' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "$local_server_port_dlna" ] && echo "APP_LOCAL_SERVER_PORT_DLNA=$local_server_port_dlna"' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "$local_server_port_api" ] && echo "APP_LOCAL_SERVER_PORT_API=$local_server_port_api"' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "$stream_quality" ] && echo "APP_STREAM_QUALITY=$stream_quality"' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "$debug" ] && echo "APP_DEBUG=$debug"' >> /etc/cont-init.d/01-setup-env && \
    echo '  [ -n "$mute_yandex_station" ] && echo "APP_MUTE_YANDEX_STATION=$mute_yandex_station"' >> /etc/cont-init.d/01-setup-env && \
    echo '} > /app/.env' >> /etc/cont-init.d/01-setup-env && \
    chmod +x /etc/cont-init.d/01-setup-env

# Скрипт для API сервиса
RUN echo '#!/bin/sh' > /etc/services.d/api/run && \
    echo 'export PYTHONPATH=/app/src' >> /etc/services.d/api/run && \
    echo 'exec python3 -m src.api.main' >> /etc/services.d/api/run && \
    chmod +x /etc/services.d/api/run

# Скрипт для DLNA сервиса
RUN echo '#!/bin/sh' > /etc/services.d/dlna/run && \
    echo 'export PYTHONPATH=/app/src' >> /etc/services.d/dlna/run && \
    echo 'exec python3 -m src.dlna_stream_server.main' >> /etc/services.d/dlna/run && \
    chmod +x /etc/services.d/dlna/run

# Удаляем старый run.sh, если он не нужен (можно оставить для обратной совместимости)
RUN chmod +x /app/run.sh 2>/dev/null || true

# s6-overlay будет автоматически запускать сервисы из /etc/services.d
# ENTRYPOINT оставляем по умолчанию (s6-overlay init)