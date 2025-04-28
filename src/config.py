import os
import logging
from logging.handlers import RotatingFileHandler
import dotenv

# Carica le variabili d'ambiente dal file .env
dotenv.load_dotenv()

# Parametri di connessione al database
DB_PARAMS = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "scip_db"),
    "user": os.getenv("DB_USER", "scip_user"),
    "password": os.getenv("DB_PASSWORD", "scip_password"),
}

# Parametri SSH tunnel (se necessario)
SSH_PARAMS = {
    "enabled": os.getenv("SSH_ENABLED", "false").lower() == "true",
    "ssh_host": os.getenv("SSH_HOST", ""),
    "ssh_port": int(os.getenv("SSH_PORT", "22")),
    "ssh_username": os.getenv("SSH_USERNAME", ""),
    "ssh_key_path": os.getenv("SSH_KEY_PATH", "/app/ssh_key"),
    "remote_bind_host": os.getenv("REMOTE_BIND_HOST", "localhost"),
    "remote_bind_port": int(os.getenv("REMOTE_BIND_PORT", "5432")),
}

# Parametri SCIP
SCIP_PARAMS = {
    "time_limit": int(os.getenv("SCIP_TIME_LIMIT", "3600")),  # secondi
    "gap_limit": float(os.getenv("SCIP_GAP_LIMIT", "0.01")),  # 1%
    "threads": int(os.getenv("SCIP_THREADS", "4")),
    "output_file": os.getenv("SCIP_OUTPUT_FILE", "/app/data/schedule.json"),
}

# Configurazione task
TASK_CONFIG = {
    "task_ids": [int(id.strip()) for id in os.getenv("TASK_IDS", "").split(",") if id.strip()],
    "task_limit": int(os.getenv("TASK_LIMIT", "20")),
}

# Configurazione logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "/app/logs/scheduler.log")


def setup_logging():
    """Configura il sistema di logging"""
    log_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Assicurati che la directory dei log esista
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    # Configura file handler con rotazione
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(log_formatter)

    # Configura console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)

    # Configura il logger root
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return root_logger
