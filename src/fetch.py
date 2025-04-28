import pandas as pd
import logging
from .config import TASK_CONFIG
from .db import get_db_connection

logger = logging.getLogger(__name__)


def get_pending_tasks(limit=20):
    """
    Ottiene i task non completati con ore pianificate.

    Args:
        limit (int): Numero massimo di task da recuperare

    Returns:
        list: Lista degli ID dei task
    """
    logger.info(f"Recupero dei task non completati (limite: {limit})")

    query = '''
        SELECT t.id
        FROM project_task t
        inner join project_task_type pt on t.stage_id = pt.id
        WHERE t.planned_hours > 0
          AND pt.closed = false
        ORDER BY priority DESC
        LIMIT %s
    '''

    try:
        conn, server = get_db_connection()
        if conn is None:
            logger.error("Impossibile connettersi al database per recuperare i task non completati")
            return []

        cursor = conn.cursor()
        cursor.execute(query, (limit,))
        task_ids = [row[0] for row in cursor.fetchall()]
        cursor.close()

        logger.info(f"Recuperati {len(task_ids)} task non completati")
        return task_ids
    except Exception as e:
        logger.error(f"Errore nel recupero dei task non completati: {str(e)}")
        return []


def get_tasks(task_ids=None):
    """
    Recupera le informazioni sui task specificati.
    Se task_ids è None, utilizzerà la configurazione da TASK_CONFIG.

    Args:
        task_ids (list, optional): Lista degli ID dei task da recuperare

    Returns:
        DataFrame: DataFrame con le informazioni sui task
    """
    # Se task_ids non è specificato, usa la configurazione
    if task_ids is None:
        task_ids = TASK_CONFIG["task_ids"]

        # Se la lista dei task è vuota, recupera i task non completati
        if not task_ids:
            task_ids = get_pending_tasks(TASK_CONFIG["task_limit"])

    if not task_ids:
        logger.warning("Nessun task specificato e nessun task pendente trovato")
        return pd.DataFrame()

    logger.info(f"Recupero informazioni per {len(task_ids)} task: {task_ids}")

    query = '''
        SELECT id, name, user_id, planned_hours
        FROM project_task
        WHERE id = ANY(%s)
    '''

    try:
        conn, server = get_db_connection()
        if conn is None:
            logger.error("Impossibile connettersi al database per recuperare le informazioni sui task")
            return pd.DataFrame()

        df = pd.read_sql(query, conn, params=(task_ids,))
        logger.info(f"Recuperati dettagli per {len(df)} task")
        return df
    except Exception as e:
        logger.error(f"Errore nel recupero delle informazioni sui task: {str(e)}")
        return pd.DataFrame()


def get_calendar_slots(task_ids=None):
    """
    Recupera gli slot di calendario per i task specificati.

    Args:
        task_ids (list, optional): Lista degli ID dei task

    Returns:
        DataFrame: DataFrame con gli slot di calendario
    """
    # Se task_ids non è specificato, usa la configurazione
    if task_ids is None:
        task_ids = TASK_CONFIG["task_ids"]

        # Se la lista dei task è vuota, recupera i task non completati
        if not task_ids:
            task_ids = get_pending_tasks(TASK_CONFIG["task_limit"])

    if not task_ids:
        logger.warning("Nessun task specificato per il recupero degli slot di calendario")
        return pd.DataFrame()

    logger.info(f"Recupero slot di calendario per {len(task_ids)} task")

    query = '''
        SELECT t.id as task_id, rca.dayofweek, rca.hour_from, rca.hour_to
        FROM project_task t
        JOIN hr_employee e ON e.id = t.employee_id
        JOIN resource_calendar rc ON rc.id = e.resource_calendar_id
        JOIN resource_calendar_attendance rca ON rca.calendar_id = rc.id
        WHERE t.id = ANY(%s)
    '''

    try:
        conn, server = get_db_connection()
        if conn is None:
            logger.error("Impossibile connettersi al database per recuperare gli slot di calendario")
            return pd.DataFrame()

        df = pd.read_sql(query, conn, params=(task_ids,))
        logger.info(f"Recuperati {len(df)} slot di calendario")
        return df
    except Exception as e:
        logger.error(f"Errore nel recupero degli slot di calendario: {str(e)}")
        return pd.DataFrame()


def get_leaves(task_ids=None):
    """
    Recupera le assenze per i task specificati.

    Args:
        task_ids (list, optional): Lista degli ID dei task

    Returns:
        DataFrame: DataFrame con le assenze
    """
    # Se task_ids non è specificato, usa la configurazione
    if task_ids is None:
        task_ids = TASK_CONFIG["task_ids"]

        # Se la lista dei task è vuota, recupera i task non completati
        if not task_ids:
            task_ids = get_pending_tasks(TASK_CONFIG["task_limit"])

    if not task_ids:
        logger.warning("Nessun task specificato per il recupero delle assenze")
        return pd.DataFrame()

    logger.info(f"Recupero assenze per {len(task_ids)} task")

    query = '''
        SELECT t.id as task_id, l.date_from, l.date_to
        FROM project_task t
        JOIN hr_employee e ON e.id = t.employee_id
        JOIN hr_leave l ON l.employee_id = e.id
        JOIN hr_leave_type lt on l.holiday_status_id = lt.id
        WHERE l.state = 'validate' AND t.id = ANY(%s)
        AND (lt.name not ilike '%trasferta%' AND lt.name not ilike '%mart%')
    '''

    try:
        conn, server = get_db_connection()
        if conn is None:
            logger.error("Impossibile connettersi al database per recuperare le assenze")
            return pd.DataFrame()

        # Assicurati che task_ids sia una lista e non vuota
        if not task_ids:
            logger.warning("Lista di task vuota per il recupero delle assenze")
            return pd.DataFrame()

        # In PostgreSQL, per l'operatore ANY bisogna usare una lista
        # Modifichiamo la query per usare IN invece di ANY
        modified_query = '''
            SELECT t.id as task_id, l.date_from, l.date_to
            FROM project_task t
            JOIN hr_employee e ON e.id = t.employee_id
            JOIN hr_leave l ON l.employee_id = e.id
            JOIN hr_leave_type lt on l.holiday_status_id = lt.id
            WHERE l.state = 'validate' AND t.id IN %s
            AND (lt.name not ilike '%%trasferta%%' AND lt.name not ilike '%%smart%%')
        '''

        # Convertiamo la lista in una tupla per l'operatore IN
        task_ids_tuple = tuple(task_ids)

        # Per un solo elemento, assicuriamoci che sia una tupla valida
        if len(task_ids_tuple) == 1:
            task_ids_tuple = (task_ids_tuple[0],)

        # Formattiamo il parametro come richiesto da psycopg2
        df = pd.read_sql(modified_query, conn, params=(task_ids_tuple,))

        logger.info(f"Recuperate {len(df)} assenze")
        return df
    except Exception as e:
        logger.error(f"Errore nel recupero delle assenze: {str(e)}")
        return pd.DataFrame()
