import os
import json
import logging
import pandas as pd
from flask import Flask, request, jsonify
from flask_restful import Api, Resource
from flask_cors import CORS
import time
from datetime import datetime

from .config import setup_logging, ORTOOLS_PARAMS
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
                tasks:
                  type: array
                  items:
                    type: object
                    properties:
                      id:
                        type: integer
                      name:
                        type: string
                      user_id:
                        type: integer
                      planned_hours:
                        type: number
                  description: Lista dei task da pianificare con tutti i dati necessari
                calendar_slots:
                  type: array
                  items:
                    type: object
                    properties:
                      task_id:
                        type: integer
                      dayofweek:
                        type: integer
                      hour_from:
                        type: number
                      hour_to:
                        type: number
                  description: Slot di calendario disponibili per ogni task
                leaves:
                  type: array
                  items:
                    type: object
                    properties:
                      task_id:
                        type: integer
                      date_from:
                        type: string
                        format: date
                      date_to:
                        type: string
                        format: date
                  description: Assenze pianificate
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

        # Nuovi parametri per dati completi
        tasks_data = data.get("tasks", [])
        calendar_slots_data = data.get("calendar_slots", [])
        leaves_data = data.get("leaves", [])
        initial_horizon_days = data.get("initial_horizon_days", 28)
        horizon_extension_factor = data.get("horizon_extension_factor", 1.25)

        # Supporto per backward compatibility con task_ids
        task_ids = data.get("task_ids", None)
        if task_ids is not None and not tasks_data:
            return {
                "status": "error",
                "message": "Formato deprecato: utilizzare 'tasks', 'calendar_slots' e 'leaves' invece di 'task_ids'"
            }, 400

        # Valida i parametri
        if not tasks_data:
            return {
                "status": "error",
                "message": "Il parametro 'tasks' è obbligatorio e non può essere vuoto"
            }, 400

        if not isinstance(tasks_data, list):
            return {
                "status": "error",
                "message": "Il parametro 'tasks' deve essere una lista"
            }, 400

        # Valida la struttura dei task
        required_task_fields = ['id', 'name', 'user_id', 'planned_hours']
        for task in tasks_data:
            for field in required_task_fields:
                if field not in task:
                    return {
                        "status": "error",
                        "message": f"Campo obbligatorio '{field}' mancante nel task {task.get('id', 'sconosciuto')}"
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
            args=(tasks_data, calendar_slots_data, leaves_data, initial_horizon_days, horizon_extension_factor)
        )
        thread.daemon = True
        thread.start()

        return {
            "status": "accepted",
            "message": "Pianificazione avviata",
            "tasks_count": len(tasks_data),
            "calendar_slots_count": len(calendar_slots_data),
            "leaves_count": len(leaves_data),
            "initial_horizon_days": initial_horizon_days,
            "horizon_extension_factor": horizon_extension_factor
        }, 202  # Accepted

    def _run_scheduler(self, tasks_data, calendar_slots_data, leaves_data, initial_horizon_days=28, horizon_extension_factor=1.25):
        """
        Esegue il processo di pianificazione in background utilizzando i dati forniti direttamente
        """
        global scheduler_status
        logger.info(f"Avvio pianificazione API con {len(tasks_data)} tasks, "
                   f"{len(calendar_slots_data)} calendar slots, {len(leaves_data)} leaves, "
                   f"initial_horizon_days={initial_horizon_days}, "
                   f"horizon_extension_factor={horizon_extension_factor}")

        try:
            # Converti i dati JSON in DataFrame pandas
            tasks_df = self._convert_tasks_to_dataframe(tasks_data)
            calendar_slots_df = self._convert_calendar_slots_to_dataframe(calendar_slots_data)
            leaves_df = self._convert_leaves_to_dataframe(leaves_data)

            if tasks_df.empty:
                error_msg = "Nessun task valido fornito per la pianificazione"
                logger.error(error_msg)
                scheduler_status["status"] = "error"
                scheduler_status["message"] = error_msg
                scheduler_status["end_time"] = datetime.now().isoformat()
                return

            task_ids = tasks_df['id'].tolist()
            logger.info(f"Pianificazione delle attività con IDs: {task_ids}")
            logger.info(f"Utilizzando {len(calendar_slots_df)} slot di calendario")
            logger.info(f"Utilizzando {len(leaves_df)} assenze")

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

    def _convert_tasks_to_dataframe(self, tasks_data):
        """
        Converte i dati dei task da JSON a DataFrame pandas
        """
        if not tasks_data:
            return pd.DataFrame()

        try:
            df = pd.DataFrame(tasks_data)
            # Assicurati che le colonne necessarie siano presenti
            required_columns = ['id', 'name', 'user_id', 'planned_hours']
            for col in required_columns:
                if col not in df.columns:
                    logger.error(f"Colonna obbligatoria '{col}' mancante nei dati dei task")
                    return pd.DataFrame()

            # Converti i tipi di dati
            df['id'] = df['id'].astype(int)
            df['user_id'] = df['user_id'].astype(int)
            df['planned_hours'] = df['planned_hours'].astype(float)

            logger.info(f"Convertiti {len(df)} task in DataFrame")
            return df

        except Exception as e:
            logger.error(f"Errore nella conversione dei task in DataFrame: {str(e)}")
            return pd.DataFrame()

    def _convert_calendar_slots_to_dataframe(self, calendar_slots_data):
        """
        Converte i dati degli slot di calendario da JSON a DataFrame pandas
        """
        if not calendar_slots_data:
            return pd.DataFrame()

        try:
            df = pd.DataFrame(calendar_slots_data)
            # Assicurati che le colonne necessarie siano presenti
            required_columns = ['task_id', 'dayofweek', 'hour_from', 'hour_to']
            for col in required_columns:
                if col not in df.columns:
                    logger.warning(f"Colonna '{col}' mancante negli slot di calendario")
                    return pd.DataFrame()

            # Converti i tipi di dati
            df['task_id'] = df['task_id'].astype(int)
            df['dayofweek'] = df['dayofweek'].astype(int)
            df['hour_from'] = df['hour_from'].astype(float)
            df['hour_to'] = df['hour_to'].astype(float)

            logger.info(f"Convertiti {len(df)} slot di calendario in DataFrame")
            return df

        except Exception as e:
            logger.error(f"Errore nella conversione degli slot di calendario in DataFrame: {str(e)}")
            return pd.DataFrame()

    def _convert_leaves_to_dataframe(self, leaves_data):
        """
        Converte i dati delle assenze da JSON a DataFrame pandas
        """
        if not leaves_data:
            return pd.DataFrame()

        try:
            df = pd.DataFrame(leaves_data)
            # Assicurati che le colonne necessarie siano presenti
            required_columns = ['task_id', 'date_from', 'date_to']
            for col in required_columns:
                if col not in df.columns:
                    logger.warning(f"Colonna '{col}' mancante nelle assenze")
                    return pd.DataFrame()

            # Converti i tipi di dati
            df['task_id'] = df['task_id'].astype(int)
            df['date_from'] = pd.to_datetime(df['date_from'])
            df['date_to'] = pd.to_datetime(df['date_to'])

            logger.info(f"Convertite {len(df)} assenze in DataFrame")
            return df

        except Exception as e:
            logger.error(f"Errore nella conversione delle assenze in DataFrame: {str(e)}")
            return pd.DataFrame()


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
