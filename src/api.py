import os
import json
import logging
from flask import Flask, request, jsonify
from flask_restful import Api, Resource
from flask_cors import CORS
import time
from datetime import datetime

from .config import setup_logging, ORTOOLS_PARAMS
from .fetch import get_tasks, get_calendar_slots, get_leaves
from .db import get_db_connection, close_connection
from .scheduler.model import SchedulingModel

# Configura il logging
logger = setup_logging()
logger.info("Inizializzazione API Flask")

# Inizializza l'applicazione Flask
app = Flask(__name__)
CORS(app)  # Abilita CORS per tutte le rotte
api = Api(app)

# Configurazione API
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

# Variabili globali per tenere traccia dello stato
scheduler_status = {
    "status": "idle",  # idle, running, completed, error
    "start_time": None,
    "end_time": None,
    "message": "",
    "last_result_path": None
}


class ScheduleResource(Resource):
    """Risorsa per avviare una nuova pianificazione"""

    def post(self):
        """
        Avvia una nuova pianificazione con i parametri forniti
        ---
        tags:
          - Scheduler
        parameters:
          - in: body
            name: body
            schema:
              type: object
              properties:
                task_ids:
                  type: array
                  items:
                    type: integer
                  description: Lista di ID dei task da pianificare
                initial_horizon_days:
                  type: integer
                  description: Orizzonte temporale iniziale in giorni
                horizon_extension_factor:
                  type: number
                  description: Fattore di estensione dell'orizzonte
        responses:
          202:
            description: Pianificazione avviata
          400:
            description: Parametri non validi
          500:
            description: Errore interno
        """
        global scheduler_status

        # Se c'è già una pianificazione in corso, restituisci un errore
        if scheduler_status["status"] == "running":
            return {
                "status": "error",
                "message": "Una pianificazione è già in corso"
            }, 409  # Conflict

        # Ottieni i parametri dalla richiesta
        data = request.get_json() or {}
        task_ids = data.get("task_ids", None)
        initial_horizon_days = data.get("initial_horizon_days", 28)
        horizon_extension_factor = data.get("horizon_extension_factor", 1.25)

        # Valida i parametri
        if task_ids is not None and not isinstance(task_ids, list):
            return {
                "status": "error",
                "message": "Il parametro task_ids deve essere una lista di interi"
            }, 400

        # Aggiorna lo stato
        scheduler_status["status"] = "running"
        scheduler_status["start_time"] = datetime.now().isoformat()
        scheduler_status["message"] = "Pianificazione in corso..."
        scheduler_status["end_time"] = None
        scheduler_status["last_result_path"] = None

        # Avvia la pianificazione in un thread separato
        import threading
        thread = threading.Thread(
            target=self._run_scheduler,
            args=(task_ids, initial_horizon_days, horizon_extension_factor)
        )
        thread.daemon = True
        thread.start()

        return {
            "status": "accepted",
            "message": "Pianificazione avviata",
            "task_ids": task_ids,
            "initial_horizon_days": initial_horizon_days,
            "horizon_extension_factor": horizon_extension_factor
        }, 202  # Accepted

    def _run_scheduler(self, task_ids=None, initial_horizon_days=28, horizon_extension_factor=1.25):
        """
        Esegue il processo di pianificazione in background
        """
        global scheduler_status
        logger.info(f"Avvio pianificazione API con task_ids={task_ids}, "
                   f"initial_horizon_days={initial_horizon_days}, "
                   f"horizon_extension_factor={horizon_extension_factor}")

        try:
            # Ottieni la connessione al database
            conn, ssh_server = get_db_connection()

            if conn is None:
                error_msg = "Impossibile stabilire una connessione al database"
                logger.error(error_msg)
                scheduler_status["status"] = "error"
                scheduler_status["message"] = error_msg
                scheduler_status["end_time"] = datetime.now().isoformat()
                return

            # Recupera i dati necessari
            tasks_df = get_tasks(task_ids)

            if tasks_df.empty:
                error_msg = "Nessun task trovato per la pianificazione"
                logger.error(error_msg)
                scheduler_status["status"] = "error"
                scheduler_status["message"] = error_msg
                scheduler_status["end_time"] = datetime.now().isoformat()
                return

            task_ids = tasks_df['id'].tolist()
            logger.info(f"Pianificazione delle attività con IDs: {task_ids}")

            calendar_slots_df = get_calendar_slots(task_ids)
            logger.info(f"Recuperati {len(calendar_slots_df)} slot di calendario")

            leaves_df = get_leaves(task_ids)
            logger.info(f"Recuperate {len(leaves_df)} assenze")

            # Crea e risolvi il modello di ottimizzazione
            model = SchedulingModel(
                tasks_df,
                calendar_slots_df,
                leaves_df,
                initial_horizon_days=initial_horizon_days,
                horizon_extension_factor=horizon_extension_factor
            )
            success = model.solve()

            if success:
                # Ottieni la soluzione
                solution = model.solution

                # Salva la soluzione in formato JSON
                os.makedirs(os.path.dirname(ORTOOLS_PARAMS['output_file']), exist_ok=True)
                output_file = ORTOOLS_PARAMS['output_file']
                with open(output_file, 'w') as f:
                    json.dump(solution, f, indent=2, default=str)

                logger.info(f"Soluzione salvata in {output_file}")

                # Aggiorna lo stato
                scheduler_status["status"] = "completed"
                scheduler_status["message"] = "Pianificazione completata con successo"
                scheduler_status["end_time"] = datetime.now().isoformat()
                scheduler_status["last_result_path"] = output_file
            else:
                error_msg = "Impossibile trovare una soluzione valida"
                logger.error(error_msg)
                scheduler_status["status"] = "error"
                scheduler_status["message"] = error_msg
                scheduler_status["end_time"] = datetime.now().isoformat()

        except Exception as e:
            error_msg = f"Errore durante l'esecuzione: {str(e)}"
            logger.exception(error_msg)
            scheduler_status["status"] = "error"
            scheduler_status["message"] = error_msg
            scheduler_status["end_time"] = datetime.now().isoformat()

        finally:
            # Chiudi le connessioni
            close_connection()


class ScheduleStatusResource(Resource):
    """Risorsa per verificare lo stato della pianificazione"""

    def get(self):
        """
        Ottiene lo stato attuale della pianificazione
        ---
        tags:
          - Scheduler
        responses:
          200:
            description: Stato della pianificazione
        """
        global scheduler_status

        # Calcola il tempo trascorso se la pianificazione è in corso
        elapsed = None
        if scheduler_status["status"] == "running" and scheduler_status["start_time"]:
            start = datetime.fromisoformat(scheduler_status["start_time"])
            elapsed = (datetime.now() - start).total_seconds()

        # Calcola il tempo totale se la pianificazione è completata
        total_time = None
        if scheduler_status["end_time"] and scheduler_status["start_time"]:
            start = datetime.fromisoformat(scheduler_status["start_time"])
            end = datetime.fromisoformat(scheduler_status["end_time"])
            total_time = (end - start).total_seconds()

        return {
            "status": scheduler_status["status"],
            "message": scheduler_status["message"],
            "start_time": scheduler_status["start_time"],
            "end_time": scheduler_status["end_time"],
            "elapsed_seconds": elapsed,
            "total_seconds": total_time,
            "has_result": scheduler_status["last_result_path"] is not None
        }


class ScheduleResultResource(Resource):
    """Risorsa per ottenere i risultati della pianificazione"""

    def get(self):
        """
        Ottiene i risultati dell'ultima pianificazione completata
        ---
        tags:
          - Scheduler
        responses:
          200:
            description: Risultati della pianificazione
          404:
            description: Nessun risultato disponibile
        """
        global scheduler_status

        # Verifica se è disponibile un risultato
        if (scheduler_status["status"] != "completed" or
            scheduler_status["last_result_path"] is None):
            return {
                "status": "error",
                "message": "Nessun risultato disponibile"
            }, 404

        try:
            # Leggi il file dei risultati
            with open(scheduler_status["last_result_path"], 'r') as f:
                result = json.load(f)

            return {
                "status": "success",
                "message": "Risultati recuperati con successo",
                "data": result
            }
        except Exception as e:
            logger.exception(f"Errore nel recupero dei risultati: {str(e)}")
            return {
                "status": "error",
                "message": f"Errore nel recupero dei risultati: {str(e)}"
            }, 500


# Registra le risorse
api.add_resource(ScheduleResource, f"{API_PREFIX}/schedule")
api.add_resource(ScheduleStatusResource, f"{API_PREFIX}/schedule/status")
api.add_resource(ScheduleResultResource, f"{API_PREFIX}/schedule/result")


def run_api_server(host='0.0.0.0', port=5000, debug=False):
    """
    Avvia il server API Flask
    """
    logger.info(f"Avvio server API su {host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_api_server(debug=True)
