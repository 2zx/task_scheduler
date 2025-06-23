import os
import json
import time
import signal
import cmd
import logging

from .config import setup_logging, ORTOOLS_PARAMS
from .fetch import get_tasks, get_calendar_slots, get_leaves
from .db import get_db_connection, close_connection
from .scheduler.model import SchedulingModel

# Flag per controllare il flusso dell'applicazione
running = True


def signal_handler(sig, frame):
    """Gestisce i segnali di interruzione in modo elegante"""
    global running
    print("\nRicevuto segnale di terminazione. Chiusura in corso...")
    running = False


class SchedulerShell(cmd.Cmd):
    """Shell interattiva per il controllo dello scheduler"""
    intro = 'Benvenuto nel Task Scheduler. Digita "help" o "?" per vedere i comandi disponibili.\n'
    prompt = 'scheduler> '
    logger = None

    def __init__(self, logger):
        super().__init__()
        self.logger = logger

    def do_run(self, arg):
        """Esegue il processo di pianificazione: run [task_ids]
        Se non vengono specificati task_ids, verranno utilizzati quelli configurati o i task pendenti."""
        self.logger.info("Avvio manuale del processo di pianificazione")

        # Parsing degli argomenti opzionali
        task_ids = None
        if arg:
            try:
                task_ids = [int(id.strip()) for id in arg.split() if id.strip()]
                self.logger.info(f"Utilizzo dei task IDs specificati: {task_ids}")
            except ValueError:
                print("Errore: gli ID dei task devono essere numeri interi")
                return

        success = run_scheduler(task_ids)
        if success:
            print("\nPianificazione completata con successo.")
        else:
            print("\nLa pianificazione non è stata completata correttamente.")

    def do_status(self, arg):
        """Mostra lo stato attuale del sistema e le statistiche."""
        try:
            # Verifica la connessione al database
            conn, ssh_server = get_db_connection()
            if conn is None:
                print("Stato: Database non disponibile")
                return

            # Controlla se esiste un file di output
            output_exists = os.path.exists(ORTOOLS_PARAMS['output_file'])

            # Ottieni statistiche sui task pendenti
            pending_count = len(get_tasks())

            print("\nSTATO DEL SISTEMA:")
            print("Database: Connesso")
            print(f"File di output: {'Presente' if output_exists else 'Non presente'}")
            print(f"Task pendenti: {pending_count}")

            # Se esiste un file di output, mostra quando è stato generato
            if output_exists:
                mod_time = os.path.getmtime(ORTOOLS_PARAMS['output_file'])
                mod_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mod_time))
                print(f"Ultima pianificazione: {mod_time_str}")

            # Chiudi la connessione
            close_connection(conn, ssh_server)

        except Exception as e:
            print(f"Errore durante il recupero dello stato: {str(e)}")

    def do_list(self, arg):
        """Elenca i task pendenti disponibili per la pianificazione."""
        try:
            print("\nRecupero dei task pendenti in corso...")
            tasks_df = get_tasks()

            if tasks_df.empty:
                print("Nessun task pendente trovato.")
                return

            print("\nTASK PENDENTI:")
            print("-" * 80)
            print(f"{'ID':<6} {'Nome':<50} {'Utente ID':<10} {'Ore pianificate':<15}")
            print("-" * 80)

            for _, row in tasks_df.iterrows():
                print(f"{row['id']:<6} {row['name'][:48]:<50} {row['user_id']:<10} {row['planned_hours']:<15}")

            print(f"\nTotale: {len(tasks_df)} task pendenti")

        except Exception as e:
            print(f"Errore durante il recupero dei task: {str(e)}")

    def do_exit(self, arg):
        """Esce dall'applicazione."""
        print("Chiusura dell'applicazione...")
        global running
        running = False
        return True

    # Alias per la leggibilità
    do_quit = do_exit

    def emptyline(self):
        """Non fare nulla quando viene premuto solo Invio."""
        pass


def run_scheduler(task_ids=None):
    """Esegue il processo di pianificazione una volta"""
    logger = logging.getLogger()
    logger.info("Avvio del processo di scheduling")

    try:
        # Ottieni la connessione al database con un timeout
        logger.info("Tentativo di connessione al database...")
        conn, ssh_server = get_db_connection()

        if conn is None:
            logger.error("Impossibile stabilire una connessione al database. Terminazione.")
            return False

        # Recupera i dati necessari utilizzando la configurazione dai parametri
        tasks_df = get_tasks(task_ids)

        if tasks_df.empty:
            logger.error("Nessun task trovato per la pianificazione")
            return False

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
            os.makedirs(os.path.dirname(ORTOOLS_PARAMS['output_file']), exist_ok=True)
            with open(ORTOOLS_PARAMS['output_file'], 'w') as f:
                json.dump(solution, f, indent=2, default=str)
            logger.info(f"Soluzione salvata in {ORTOOLS_PARAMS['output_file']}")

            # Genera visualizzazioni grafiche
            try:
                from src.scheduler.visualization import ScheduleVisualizer
                visualizer = ScheduleVisualizer(solution_df, tasks_df)
                charts = visualizer.generate_all_charts()

                if charts:
                    print(f"\n📊 Grafici generati:")
                    for chart_type, path in charts.items():
                        if path:
                            print(f"  • {chart_type}: {path}")

                    # Crea report HTML
                    report_path = visualizer.create_summary_report(charts)
                    print(f"\n📋 Report completo: {report_path}")

            except ImportError:
                logger.warning("Modulo di visualizzazione non disponibile")
            except Exception as e:
                logger.error(f"Errore nella generazione dei grafici: {str(e)}")

            # Stampa un riassunto della pianificazione in formato dettagliato
            try:
                from src.scheduler.utils import format_schedule_output
                formatted_output = format_schedule_output(solution_df, tasks_df)
                print(formatted_output)
            except ImportError:
                logger.warning("Modulo utils non disponibile per il formato output")

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

            return True
        else:
            logger.error("Impossibile trovare una soluzione valida")
            return False

    except Exception as e:
        logger.exception(f"Errore durante l'esecuzione: {str(e)}")
        return False

    finally:
        # Chiudi le connessioni globali alla fine dell'esecuzione
        close_connection()


def main():
    """Punto di ingresso principale per l'applicazione di scheduling"""
    # Configura il logging
    logger = setup_logging()
    logger.info("Avvio dell'applicazione di scheduling in modalità interattiva")

    # Registra handler per i segnali per la chiusura controllata
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Modalità interattiva
    shell = SchedulerShell(logger)

    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\nInterruzione ricevuta, chiusura in corso...")
    except Exception as e:
        logger.exception(f"Errore imprevisto: {str(e)}")

    logger.info("Applicazione terminata")


if __name__ == "__main__":
    main()
