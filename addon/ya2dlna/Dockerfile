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

# Установка PYTHONPATH для корректного импорта модулей core
ENV PYTHONPATH=/app/src

# Создание директории для конфигурации
RUN mkdir -p /data

# Убедимся, что run.sh исполняемый
RUN chmod +x /app/run.sh

# Используем run.sh как entrypoint, чтобы избежать запуска s6-overlay-suexec
ENTRYPOINT ["/app/run.sh"]