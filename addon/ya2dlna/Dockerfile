ARG BUILD_FROM
FROM $BUILD_FROM

# Установка зависимостей
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    upnp-tools

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