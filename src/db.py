import logging
import psycopg2
from sshtunnel import SSHTunnelForwarder
from .config import DB_PARAMS, SSH_PARAMS

logger = logging.getLogger(__name__)


def get_db_connection():
    """
    Crea una connessione al database, utilizzando un tunnel SSH se necessario.

    Returns:
        tuple: (connection, ssh_server) dove ssh_server è None se non utilizzato
    """
    ssh_server = None

    try:
        # Se il tunnel SSH è abilitato, crealo
        if SSH_PARAMS["enabled"]:
            logger.info(f"Creazione tunnel SSH verso {SSH_PARAMS['ssh_host']}")
            ssh_server = SSHTunnelForwarder(
                (SSH_PARAMS["ssh_host"], SSH_PARAMS["ssh_port"]),
                ssh_username=SSH_PARAMS["ssh_username"],
                ssh_pkey=SSH_PARAMS["ssh_key_path"],
                remote_bind_address=(
                    SSH_PARAMS["remote_bind_host"],
                    SSH_PARAMS["remote_bind_port"]
                )
            )
            ssh_server.start()
            logger.info(f"Tunnel SSH stabilito sulla porta locale {ssh_server.local_bind_port}")

            # Aggiorna i parametri di connessione per utilizzare il tunnel
            conn_params = DB_PARAMS.copy()
            conn_params["host"] = "localhost"
            conn_params["port"] = ssh_server.local_bind_port
        else:
            conn_params = DB_PARAMS

        # Stabilisci la connessione al database
        logger.info(f"Connessione al database {conn_params['database']} su {conn_params['host']}")
        conn = psycopg2.connect(**conn_params)
        logger.info("Connessione al database stabilita con successo")

        return conn, ssh_server

    except Exception as e:
        logger.error(f"Errore durante la connessione al database: {str(e)}")
        if ssh_server and ssh_server.is_active:
            ssh_server.stop()
        raise


def close_connection(conn, ssh_server=None):
    """
    Chiude la connessione al database e il tunnel SSH se presente.

    Args:
        conn: La connessione al database
        ssh_server: Il server SSH tunnel (opzionale)
    """
    if conn:
        conn.close()
        logger.info("Connessione al database chiusa")

    if ssh_server and ssh_server.is_active:
        ssh_server.stop()
        logger.info("Tunnel SSH chiuso")
