ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM $BUILD_FROM

# Отключение s6-overlay-suexec для избежания ошибки "can only run as pid 1"
ENV S6_OVERLAY_SUEXEC=0

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
COPY services.d/api /etc/services.d/api
COPY services.d/dlna /etc/services.d/dlna
RUN chmod +x /etc/services.d/api/run /etc/services.d/dlna/run

# CMD не нужен, так как s6-overlay запустит службы