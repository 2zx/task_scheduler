import logging
import psycopg2
from sqlalchemy import create_engine
from sshtunnel import SSHTunnelForwarder
from .config import DB_PARAMS, SSH_PARAMS

logger = logging.getLogger(__name__)

# Variabili globali per memorizzare le connessioni
_connection = None
_ssh_server = None
_engine = None


def get_sqlalchemy_engine():
    """
    Crea o restituisce un engine SQLAlchemy esistente per l'uso con pandas.

    Returns:
        sqlalchemy.Engine: Engine SQLAlchemy per pandas
    """
    global _engine, _ssh_server

    # Se esiste già un engine valido, lo restituisce
    if _engine is not None:
        try:
            # Testa la connessione
            with _engine.connect() as conn:
                conn.execute("SELECT 1")
            logger.debug("Riutilizzo engine SQLAlchemy esistente")
            return _engine
        except Exception as e:
            logger.warning(f"Engine SQLAlchemy esistente non più valido: {str(e)}")
            _engine = None

    # Se non esiste un engine valido, ne crea uno nuovo
    try:
        # Se il tunnel SSH è abilitato, crealo se non esiste già
        if SSH_PARAMS["enabled"]:
            if _ssh_server is None or not _ssh_server.is_active:
                logger.info(f"Creazione tunnel SSH verso {SSH_PARAMS['ssh_host']}")
                _ssh_server = SSHTunnelForwarder(
                    (SSH_PARAMS["ssh_host"], SSH_PARAMS["ssh_port"]),
                    ssh_username=SSH_PARAMS["ssh_username"],
                    ssh_pkey=SSH_PARAMS["ssh_key_path"],
                    remote_bind_address=(
                        SSH_PARAMS["remote_bind_host"],
                        SSH_PARAMS["remote_bind_port"]
                    )
                )
                _ssh_server.start()
                logger.info(f"Tunnel SSH stabilito sulla porta locale {_ssh_server.local_bind_port}")

            # Crea la stringa di connessione per SQLAlchemy
            connection_string = (
                f"postgresql://{DB_PARAMS['user']}:{DB_PARAMS['password']}"
                f"@localhost:{_ssh_server.local_bind_port}/{DB_PARAMS['database']}"
            )
        else:
            # Crea la stringa di connessione per SQLAlchemy senza tunnel
            connection_string = (
                f"postgresql://{DB_PARAMS['user']}:{DB_PARAMS['password']}"
                f"@{DB_PARAMS['host']}:{DB_PARAMS['port']}/{DB_PARAMS['database']}"
            )

        # Crea l'engine SQLAlchemy
        _engine = create_engine(connection_string, pool_pre_ping=True)
        logger.info("Engine SQLAlchemy creato con successo")

        return _engine

    except Exception as e:
        logger.error(f"Errore durante la creazione dell'engine SQLAlchemy: {str(e)}")
        if _ssh_server and _ssh_server.is_active:
            _ssh_server.stop()
            _ssh_server = None
        return None


def get_db_connection():
    """
    Crea o restituisce una connessione esistente al database, utilizzando un tunnel SSH se necessario.
    Riutilizza le connessioni esistenti se possibile.

    Returns:
        tuple: (connection, ssh_server) dove ssh_server è None se non utilizzato
    """
    global _connection, _ssh_server

    # Se esiste già una connessione valida, la restituisce
    if _connection is not None:
        try:
            # Verifica che la connessione sia ancora valida
            cursor = _connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            logger.debug("Riutilizzo connessione esistente al database")
            return _connection, _ssh_server
        except Exception as e:
            logger.warning(f"Connessione esistente non più valida: {str(e)}")
            # Se la connessione non è più valida, la chiude e ne crea una nuova
            close_connection(_connection, _ssh_server)
            _connection = None
            _ssh_server = None

    # Se non esiste una connessione valida, ne crea una nuova
    try:
        # Se il tunnel SSH è abilitato, crealo
        if SSH_PARAMS["enabled"]:
            logger.info(f"Creazione tunnel SSH verso {SSH_PARAMS['ssh_host']}")
            _ssh_server = SSHTunnelForwarder(
                (SSH_PARAMS["ssh_host"], SSH_PARAMS["ssh_port"]),
                ssh_username=SSH_PARAMS["ssh_username"],
                ssh_pkey=SSH_PARAMS["ssh_key_path"],
                remote_bind_address=(
                    SSH_PARAMS["remote_bind_host"],
                    SSH_PARAMS["remote_bind_port"]
                )
            )
            _ssh_server.start()
            logger.info(f"Tunnel SSH stabilito sulla porta locale {_ssh_server.local_bind_port}")

            # Aggiorna i parametri di connessione per utilizzare il tunnel
            conn_params = DB_PARAMS.copy()
            conn_params["host"] = "localhost"
            conn_params["port"] = _ssh_server.local_bind_port
            # Aggiungi un timeout alla connessione
            conn_params["connect_timeout"] = 10
        else:
            conn_params = DB_PARAMS.copy()
            # Aggiungi un timeout alla connessione
            conn_params["connect_timeout"] = 10

        # Stabilisci la connessione al database
        logger.info(f"Connessione al database {conn_params['database']} su {conn_params['host']}")
        _connection = psycopg2.connect(**conn_params)
        logger.info("Connessione al database stabilita con successo")

        return _connection, _ssh_server

    except Exception as e:
        logger.error(f"Errore durante la connessione al database: {str(e)}")
        if _ssh_server and _ssh_server.is_active:
            _ssh_server.stop()
            _ssh_server = None
        # Ritorna None, None in caso di errore per gestire correttamente nel chiamante
        return None, None


def close_connection(conn=None, ssh_server=None):
    """
    Chiude la connessione al database e il tunnel SSH.
    Se non vengono specificati parametri, chiude le connessioni globali.

    Args:
        conn: La connessione al database (opzionale)
        ssh_server: Il server SSH tunnel (opzionale)
    """
    global _connection, _ssh_server, _engine

    # Se non vengono specificati parametri, utilizza le variabili globali
    if conn is None:
        conn = _connection
    if ssh_server is None:
        ssh_server = _ssh_server

    if conn:
        try:
            conn.close()
            logger.info("Connessione al database chiusa")
        except Exception as e:
            logger.warning(f"Errore durante la chiusura della connessione al database: {str(e)}")

        # Se era la connessione globale, resetta la variabile
        if conn is _connection:
            _connection = None

    # Chiudi l'engine SQLAlchemy se esiste
    if _engine is not None:
        try:
            _engine.dispose()
            logger.info("Engine SQLAlchemy chiuso")
        except Exception as e:
            logger.warning(f"Errore durante la chiusura dell'engine SQLAlchemy: {str(e)}")
        _engine = None

    if ssh_server and ssh_server.is_active:
        try:
            ssh_server.stop()
            logger.info("Tunnel SSH chiuso")
        except Exception as e:
            logger.warning(f"Errore durante la chiusura del tunnel SSH: {str(e)}")

        # Se era il server SSH globale, resetta la variabile
        if ssh_server is _ssh_server:
            _ssh_server = None
