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

# Parametri OrTools
ORTOOLS_PARAMS = {
    "time_limit": int(os.getenv("ORTOOLS_TIME_LIMIT", "30")),  # Ridotto a 30 secondi per performance
    "num_search_workers": int(os.getenv("ORTOOLS_WORKERS", "4")),
    "log_search_progress": os.getenv("ORTOOLS_LOG_PROGRESS", "false").lower() == "true",
    "output_file": os.getenv("ORTOOLS_OUTPUT_FILE", "/app/data/schedule.json"),
}

# Parametri Scheduler Ibrido
SCHEDULER_CONFIG = {
    "greedy_threshold_tasks": int(os.getenv("GREEDY_THRESHOLD_TASKS", "50")),
    "greedy_threshold_hours": int(os.getenv("GREEDY_THRESHOLD_HOURS", "1000")),
    "greedy_threshold_users": int(os.getenv("GREEDY_THRESHOLD_USERS", "10")),
    "greedy_threshold_avg_hours": int(os.getenv("GREEDY_THRESHOLD_AVG_HOURS", "100")),
    "ortools_timeout_seconds": int(os.getenv("ORTOOLS_TIMEOUT_SECONDS", "30")),
    "ortools_fallback_timeout": int(os.getenv("ORTOOLS_FALLBACK_TIMEOUT", "60")),
    "hybrid_mode": os.getenv("HYBRID_MODE", "true").lower() == "true",
    # Limite massimo orizzonte temporale in giorni (default: 10 anni = 3650 giorni)
    # Questo parametro controlla il limite massimo di giorni che il sistema
    # può considerare per la pianificazione prima di arrendersi
    "max_horizon_days": int(os.getenv("MAX_HORIZON_DAYS", "3650")),  # 10 anni come default
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
    root_logger = logging.getLogger()

    # Se il logger è già configurato, non aggiungere handler duplicati
    if root_logger.handlers:
        return root_logger

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
    root_logger.setLevel(getattr(logging, LOG_LEVEL))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return root_logger
