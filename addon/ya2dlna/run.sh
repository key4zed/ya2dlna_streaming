#!/bin/sh
set -e

echo "=== Starting run.sh ==="

# Установка значений по умолчанию для переменных, если они пусты
: ${local_server_host:=0.0.0.0}
: ${local_server_port_dlna:=8001}
: ${local_server_port_api:=8000}
: ${stream_quality:=192}
: ${debug:=false}
: ${mute_yandex_station:=true}

# Создание конфигурационного файла .env из опций аддона
cat > /app/.env <<EOF
APP_YA_MUSIC_TOKEN=${ya_music_token}
APP_X_TOKEN=${x_token}
APP_COOKIE=${cookie}
APP_RUARK_PIN=${ruark_pin}
APP_LOCAL_SERVER_HOST=${local_server_host}
APP_LOCAL_SERVER_PORT_DLNA=${local_server_port_dlna}
APP_LOCAL_SERVER_PORT_API=${local_server_port_api}
APP_STREAM_QUALITY=${stream_quality}
APP_DEBUG=${debug}
APP_MUTE_YANDEX_STATION=${mute_yandex_station}
EOF

# Установка PYTHONPATH для корректного импорта модулей core
export PYTHONPATH=/app/src
echo "PYTHONPATH=$PYTHONPATH"
echo "sys.path:"
python3 -c "import sys; print(sys.path)"

# Проверка содержимого файлов
echo "=== Checking /app/src/api/main.py ==="
head -10 /app/src/api/main.py
echo "=== Checking /app/src/dlna_stream_server/main.py ==="
head -10 /app/src/dlna_stream_server/main.py

# Запуск API сервиса в фоне
cd /app
PYTHONPATH=/app/src python3 -m src.api.main &
API_PID=$!

# Запуск DLNA сервера в фоне
PYTHONPATH=/app/src python3 -m src.dlna_stream_server.main &
DLNA_PID=$!

echo "API PID: $API_PID, DLNA PID: $DLNA_PID"

# Ожидание завершения любого из процессов
wait $API_PID $DLNA_PID