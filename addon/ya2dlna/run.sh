#!/bin/sh
set -e

# Создание конфигурационного файла .env из опций аддона
cat > /app/.env <<EOF
APP_YA_MUSIC_TOKEN=${ya_music_token}
APP_RUARK_PIN=${ruark_pin}
APP_LOCAL_SERVER_HOST=${local_server_host}
APP_LOCAL_SERVER_PORT_DLNA=${local_server_port_dlna}
APP_LOCAL_SERVER_PORT_API=${local_server_port_api}
APP_STREAM_QUALITY=${stream_quality}
APP_DEBUG=${debug}
EOF

# Запуск приложения
cd /app
exec python3 -m src.main