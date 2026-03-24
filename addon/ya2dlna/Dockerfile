# Используем легковесный образ Python без s6-overlay
FROM python:3.11-alpine

# Установка системных зависимостей
RUN apk add --no-cache \
    ffmpeg

# Копирование исходного кода
COPY . /app
WORKDIR /app

# Установка Python-зависимостей
RUN pip3 install --no-cache-dir -r requirements.txt

# Установка PYTHONPATH для корректного импорта модулей core
ENV PYTHONPATH=/app/src

# Создание директории для конфигурации
RUN mkdir -p /data

# Убедимся, что run.sh исполняемый
RUN chmod +x /app/run.sh

# Используем run.sh как entrypoint
ENTRYPOINT ["/app/run.sh"]