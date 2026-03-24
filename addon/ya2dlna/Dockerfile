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

# Создание директории для конфигурации
RUN mkdir -p /data

# Копирование служб s6
COPY services.d/ /etc/services.d/
RUN chmod +x /etc/services.d/api/run /etc/services.d/dlna/run

# Создание конфигурационного файла .env через cont-init.d
RUN mkdir -p /etc/cont-init.d && \
    echo '#!/bin/sh' > /etc/cont-init.d/01-create-env && \
    echo 'cat > /app/.env <<EOF' >> /etc/cont-init.d/01-create-env && \
    echo "APP_YA_MUSIC_TOKEN=\${ya_music_token}" >> /etc/cont-init.d/01-create-env && \
    echo "APP_X_TOKEN=\${x_token}" >> /etc/cont-init.d/01-create-env && \
    echo "APP_COOKIE=\${cookie}" >> /etc/cont-init.d/01-create-env && \
    echo "APP_RUARK_PIN=\${ruark_pin}" >> /etc/cont-init.d/01-create-env && \
    echo "APP_LOCAL_SERVER_HOST=\${local_server_host}" >> /etc/cont-init.d/01-create-env && \
    echo "APP_LOCAL_SERVER_PORT_DLNA=\${local_server_port_dlna}" >> /etc/cont-init.d/01-create-env && \
    echo "APP_LOCAL_SERVER_PORT_API=\${local_server_port_api}" >> /etc/cont-init.d/01-create-env && \
    echo "APP_STREAM_QUALITY=\${stream_quality}" >> /etc/cont-init.d/01-create-env && \
    echo "APP_DEBUG=\${debug}" >> /etc/cont-init.d/01-create-env && \
    echo "APP_MUTE_YANDEX_STATION=\${mute_yandex_station}" >> /etc/cont-init.d/01-create-env && \
    echo 'EOF' >> /etc/cont-init.d/01-create-env && \
    chmod +x /etc/cont-init.d/01-create-env

# CMD не нужен, так как s6-overlay запустит службы