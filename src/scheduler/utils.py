import logging
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)


def sort_tasks_by_priority(tasks_df):
    """
    Ordina i task per priorità in modo centralizzato.

    REGOLA: priority_score più alto = priorità più alta
    Ordinamento: DESCENDING (dal più alto al più basso)

    Args:
        tasks_df (DataFrame): DataFrame con i task da ordinare

    Returns:
        DataFrame: DataFrame ordinato per priorità
    """
    if 'priority_score' not in tasks_df.columns:
        logger.warning("Colonna 'priority_score' non trovata, nessun ordinamento applicato")
        return tasks_df.copy()

    # Ordinamento DESCENDING: priority_score più alto = priorità più alta
    sorted_df = tasks_df.sort_values('priority_score', ascending=False)

    logger.info(f"Task ordinati per priorità (DESC): {sorted_df[['id', 'priority_score']].to_dict('records')}")

    return sorted_df


def generate_user_working_slots(task_calendar_df, leave_df, start_date, end_date):
    """
    Genera gli slot di lavoro disponibili per ogni task, tenendo conto del calendario
    e delle assenze.

    Args:
        task_calendar_df (DataFrame): DataFrame con gli slot del calendario per ogni task
        leave_df (DataFrame): DataFrame con le assenze per ogni task
        start_date (datetime): Data di inizio per la generazione degli slot
        end_date (datetime): Data di fine per la generazione degli slot

    Returns:
        dict: Dizionario con task_id come chiave e lista di datetime come valore
    """
    logger.info(f"Generazione slot di lavoro dal {start_date} al {end_date}")
    slots_by_task = {}

    # Verifica che le date siano valide per prevenire loop infiniti
    if start_date >= end_date:
        logger.error("Data di inizio maggiore o uguale alla data di fine")
        return slots_by_task

    # Imposta un limite massimo di giorni per sicurezza (es. 90 giorni)
    max_days = 90
    if (end_date - start_date).days > max_days:
        logger.warning(f"Intervallo di date troppo ampio, limitato a {max_days} giorni")
        end_date = start_date + timedelta(days=max_days)

    for task_id in task_calendar_df["task_id"].unique():
        task_slots = []
        calendar = task_calendar_df[task_calendar_df["task_id"] == task_id]
        leaves = leave_df[leave_df["task_id"] == task_id]

        logger.debug(f"Elaborazione task_id: {task_id}, con {len(calendar)} slot di calendario e {len(leaves)} assenze")

        current = start_date
        while current < end_date:
            dow = current.weekday()
            day_calendar = calendar[calendar["dayofweek"].astype(int) == dow]
            for _, row in day_calendar.iterrows():
                for h in range(int(row["hour_from"]), int(row["hour_to"])):
                    slot = current.replace(hour=h, minute=0, second=0, microsecond=0)
                    if not is_in_leave(slot, leaves):
                        task_slots.append(slot)
            current += timedelta(days=1)

        slots_by_task[task_id] = sorted(task_slots)
        logger.debug(f"Task {task_id}: generati {len(task_slots)} slot disponibili")

    return slots_by_task

def is_in_leave(slot, leaves_df):
    """
    Verifica se uno slot temporale è all'interno di un periodo di assenza.

    Args:
        slot (datetime): Lo slot temporale da verificare
        leaves_df (DataFrame): DataFrame con le assenze

    Returns:
        bool: True se lo slot è in un periodo di assenza, False altrimenti
    """
    # Converti lo slot in date per un confronto coerente
    if isinstance(slot, datetime):
        slot_date = slot.date()
    else:
        slot_date = slot

    for _, row in leaves_df.iterrows():
        # Normalizza le date di inizio e fine
        date_from = row["date_from"]
        date_to = row["date_to"]

        if isinstance(date_from, datetime):
            date_from = date_from.date()
        if isinstance(date_to, datetime):
            date_to = date_to.date()

        # Ora confronta solo le date, non i datetime
        if date_from <= slot_date <= date_to:
            return True

    return False


def format_schedule_output(solution_df, tasks_df):
    """
    Formatta l'output della soluzione in un formato leggibile.

    Args:
        solution_df (DataFrame): DataFrame con la soluzione dello scheduling
        tasks_df (DataFrame): DataFrame con le informazioni sui task

    Returns:
        str: Stringa formattata con la pianificazione
    """
    # Controlla che solution_df non sia vuoto
    if solution_df is None or solution_df.empty:
        return "Nessuna pianificazione disponibile."

    output = []
    output.append("PIANIFICAZIONE ATTIVITÀ\n")
    output.append("=" * 80 + "\n")

    try:
        # Raggruppa per data
        solution_df["date"] = pd.to_datetime(solution_df["date"])
        dates = solution_df["date"].dt.date.unique()

        for date in sorted(dates):
            output.append(f"\nData: {date.strftime('%d/%m/%Y')} ({date.strftime('%A')})\n")
            output.append("-" * 80 + "\n")

            # Filtra per data corrente
            day_df = solution_df[solution_df["date"].dt.date == date]

            # Ordina per ora e task
            day_df = day_df.sort_values(["hour", "task_id"])

            for _, row in day_df.iterrows():
                task_id = row["task_id"]
                task_name = row["task_name"]
                hour = int(row["hour"])

                # Formatta l'orario (es. 9:00 - 10:00)
                time_slot = f"{hour:02d}:00 - {(hour+1):02d}:00"

                output.append(f"{time_slot}  |  {task_name} (ID: {task_id})\n")

    except Exception as e:
        logger.error(f"Errore durante la formattazione dell'output: {str(e)}")
        return "Errore nella formattazione dell'output della pianificazione."

    return "".join(output)
