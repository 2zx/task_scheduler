import os
import json


from .config import setup_logging, SCIP_PARAMS
from .fetch import get_tasks, get_calendar_slots, get_leaves
from .db import get_db_connection, close_connection
from .scheduler.model import SchedulingModel

def main():
    """Punto di ingresso principale per l'applicazione di scheduling"""
    # Configura il logging
    logger = setup_logging()
    logger.info("Avvio dell'applicazione di scheduling")

    try:
        # Ottieni la connessione al database
        conn, ssh_server = get_db_connection()

        # Recupera i dati necessari utilizzando la configurazione dai parametri
        # Non è necessario passare esplicitamente task_ids, lo farà la funzione stessa
        tasks_df = get_tasks()

        if tasks_df.empty:
            logger.error("Nessun task trovato per la pianificazione")
            return

        task_ids = tasks_df['id'].tolist()
        logger.info(f"Pianificazione delle attività con IDs: {task_ids}")

        calendar_slots_df = get_calendar_slots(task_ids)
        logger.info(f"Recuperati {len(calendar_slots_df)} slot di calendario")

        leaves_df = get_leaves(task_ids)
        logger.info(f"Recuperate {len(leaves_df)} assenze")

        # Crea e risolvi il modello di ottimizzazione
        model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)
        success = model.solve()

        if success:
            # Ottieni la soluzione come DataFrame
            solution_df = model.get_solution_dataframe()
            logger.info(f"Soluzione trovata con {len(solution_df)} assegnazioni di slot")

            # Salva la soluzione in formato JSON
            solution = model.solution
            os.makedirs(os.path.dirname(SCIP_PARAMS['output_file']), exist_ok=True)
            with open(SCIP_PARAMS['output_file'], 'w') as f:
                json.dump(solution, f, indent=2, default=str)
            logger.info(f"Soluzione salvata in {SCIP_PARAMS['output_file']}")

            # Stampa un riassunto della pianificazione in formato dettagliato
            from src.scheduler.utils import format_schedule_output
            formatted_output = format_schedule_output(solution_df, tasks_df)
            print(formatted_output)

            # Stampa un riassunto numerico
            print("\nRIEPILOGO NUMERICO:")
            for task_id, task_data in solution['tasks'].items():
                task_name = tasks_df[tasks_df['id'] == task_id]['name'].iloc[0]
                print(f"Attività: {task_name} (ID: {task_id})")
                print(f"  Ore pianificate: {len(task_data)}")
                dates = set(slot['date'] for slot in task_data)
                print(f"  Giorni utilizzati: {len(dates)}")
                print(f"  Date: {', '.join(sorted(dates))}")
                print()
        else:
            logger.error("Impossibile trovare una soluzione valida")

    except Exception as e:
        logger.exception(f"Errore durante l'esecuzione: {str(e)}")

    finally:
        # Chiudi le connessioni
        close_connection(conn, ssh_server)
        logger.info("Applicazione terminata")

if __name__ == "__main__":
    main()
