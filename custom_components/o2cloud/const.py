"""Constantes para integración O2 Cloud."""

DOMAIN = "o2cloud"
CONF_VALIDATION_KEY = "validation_key"
CONF_COOKIES = "cookies"
CONF_USER_AGENT = "user_agent"
CONF_FOLDER_NAME = "folder_name"
CONF_FOLDER_ID = "folder_id"
CONF_REFRESH_INTERVAL = "refresh_interval"
CONF_INCLUDE_SOFT_DELETED = "include_soft_deleted"
CONF_MAX_UPLOAD_SIZE_MB = "max_upload_size_mb"

DEFAULT_REFRESH_INTERVAL = 30  # minutos
DEFAULT_MAX_UPLOAD_SIZE_MB = 1024  # 1GB
DEFAULT_INCLUDE_SOFT_DELETED = False

API_BASE_URL = "https://cloud.o2online.es/sapi/"
# El binario del archivo se sube a un host separado (Synchronoss OMH).
UPLOAD_BASE_URL = "https://upload.cloud.o2online.es/sapi/upload/file"

# Timeouts
REQUEST_TIMEOUT = 30
UPLOAD_TIMEOUT = 300

# Service names
SERVICE_UPLOAD_BACKUP = "upload_backup"
SERVICE_PRUNE_BACKUPS = "prune_backups"
SERVICE_REFRESH_QUOTA = "refresh_quota"
SERVICE_TEST_CONNECTION = "test_connection"

# Entity IDs
ATTR_FILE_PATH = "file_path"
ATTR_REMOTE_NAME = "remote_name"
ATTR_MAX_BACKUPS = "max_backups"
ATTR_MAX_DAYS = "max_days"

# Update coordinator
# Nota: la sesión de O2 caduca por inactividad (~30-45 min). Cada refresco
# hace una petición real a /sapi, así que actúa como keepalive. Se mantiene
# muy por debajo del timeout para no dejar caducar la sesión.
COORDINATOR_UPDATE_INTERVAL = 10  # minutos
