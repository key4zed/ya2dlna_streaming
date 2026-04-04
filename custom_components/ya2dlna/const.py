"""Constants for the Ya2DLNA integration."""

DOMAIN = "ya2dlna"
DEFAULT_NAME = "Ya2DLNA Streaming"

# Параметры интеграции (должны быть только эти)
CONF_API_HOST = "api_host"
CONF_SOURCE_ENTITY = "source_entity"
CONF_TARGET_ENTITY = "target_entity"
CONF_API_PORT = "api_port"
CONF_X_TOKEN = "x_token"
CONF_COOKIE = "cookie"
CONF_RUARK_PIN = "ruark_pin"
CONF_MUTE_YANDEX_STATION = "mute_yandex_station"
CONF_AUTH_METHOD = "auth_method"
# Новые параметры для выбора таргета через аддон
CONF_TARGET_DEVICE_ID = "target_device_id"
CONF_TARGET_FRIENDLY_NAME = "target_friendly_name"

# Значения по умолчанию
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000
DEFAULT_MUTE_YANDEX_STATION = True

# Методы аутентификации (используются только в UI config_flow)
AUTH_METHOD_YANDEX_STATION = "yandex_station"
AUTH_METHOD_COOKIES = "cookies"
AUTH_METHOD_TOKEN = "token"

# Платформы
PLATFORM_SWITCH = "switch"
PLATFORM_SELECT = "select"

# Атрибуты
ATTR_ACTIVE_TARGET = "active_target"
ATTR_AVAILABLE_TARGETS = "available_targets"