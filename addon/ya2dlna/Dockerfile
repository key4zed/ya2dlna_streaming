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
RUN pip3 install --no-cache-dir -r requirements.txt

# Создание директории для конфигурации
RUN mkdir -p /data

# Скрипт запуска
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]