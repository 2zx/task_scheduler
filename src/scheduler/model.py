import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pyscipopt import Model, quicksum

from ..config import SCIP_PARAMS

logger = logging.getLogger(__name__)


class SchedulingModel:
    """
    Modello di ottimizzazione per la pianificazione delle attività
    utilizzando SCIP come solutore.
    """

    def __init__(self, tasks_df, calendar_slots_df, leaves_df):
        """
        Inizializza il modello con i dati necessari.

        Args:
            tasks_df: DataFrame con le attività da pianificare
            calendar_slots_df: DataFrame con gli slot disponibili nel calendario
            leaves_df: DataFrame con le assenze pianificate
        """
        self.tasks_df = tasks_df
        self.calendar_slots_df = calendar_slots_df
        self.leaves_df = leaves_df
        self.model = None
        self.vars = {}
        self.solution = None

        # Prepara i dati per il modello
        self._prepare_data()

    def _prepare_data(self):
        """Prepara e trasforma i dati per il modello di ottimizzazione"""
        logger.info("Preparazione dei dati per il modello di ottimizzazione")

        # Genera un orizzonte temporale di pianificazione (es. 4 settimane)
        today = datetime.now().date()
        self.days = [today + timedelta(days=i) for i in range(28)]  # 4 settimane

        # Mappa i giorni della settimana (0-6) alle date effettive
        self.day_to_date = {d.weekday(): d for d in self.days}

        # Identifica gli slot temporali disponibili per ogni utente/attività
        self._prepare_available_slots()

        # Prepara i dati delle assenze
        self._prepare_leaves()

        logger.info("Preparazione dei dati completata")

    def _prepare_available_slots(self):
        """Prepara gli slot disponibili per ogni task basandosi sul calendario"""
        # Mappa gli slot disponibili per ogni task
        self.available_slots = {}

        for _, row in self.calendar_slots_df.iterrows():
            task_id = row['task_id']
            day = row['dayofweek']
            hour_from = row['hour_from']
            hour_to = row['hour_to']

            # Calcola gli slot orari (es. 9-10, 10-11, etc.)
            hours = list(range(int(hour_from), int(hour_to)))

            if task_id not in self.available_slots:
                self.available_slots[task_id] = {}

            if day not in self.available_slots[task_id]:
                self.available_slots[task_id][day] = []

            self.available_slots[task_id][day].extend(hours)

        # In alternativa, possiamo usare la funzione generate_user_working_slots
        # per un approccio più dettagliato, decommentando il codice seguente:
        """
        from .utils import generate_user_working_slots

        # Definisci l'intervallo di date per la pianificazione
        today = datetime.now().date()
        start_date = datetime.combine(today, datetime.min.time())
        end_date = datetime.combine(today + timedelta(days=28), datetime.min.time())

        # Genera gli slot di lavoro disponibili
        self.working_slots = generate_user_working_slots(
            self.calendar_slots_df,
            self.leaves_df,
            start_date,
            end_date
        )
        """

    def _prepare_leaves(self):
        """Prepara i dati sulle assenze, convertendoli in giorni non disponibili"""
        self.unavailable_days = {}

        for _, row in self.leaves_df.iterrows():
            task_id = row['task_id']
            date_from = row['date_from'].date() if isinstance(row['date_from'], datetime) else row['date_from']
            date_to = row['date_to'].date() if isinstance(row['date_to'], datetime) else row['date_to']

            # Calcola tutti i giorni di assenza
            current_date = date_from
            while current_date <= date_to:
                if task_id not in self.unavailable_days:
                    self.unavailable_days[task_id] = []

                self.unavailable_days[task_id].append(current_date)
                current_date += timedelta(days=1)

    def build_model(self):
        """Costruisce il modello di ottimizzazione SCIP"""
        logger.info("Costruzione del modello di ottimizzazione")

        # Inizializza il modello SCIP
        self.model = Model("TaskScheduling")

        # Configura i parametri del solutore
        self.model.setParam('limits/time', SCIP_PARAMS['time_limit'])
        self.model.setParam('limits/gap', SCIP_PARAMS['gap_limit'])
        self.model.setParam('parallel/maxnthreads', SCIP_PARAMS['threads'])

        # Definisci le variabili di decisione e i vincoli
        self._create_variables()
        self._create_constraints()
        self._create_objective()

        logger.info("Modello di ottimizzazione costruito")
        return self.model

    def _create_variables(self):
        """Crea le variabili di decisione per il modello"""
        # Variabile binaria x[t,d,h] = 1 se il task t è schedulato nel giorno d all'ora h
        self.vars['x'] = {}

        for _, task in self.tasks_df.iterrows():
            task_id = task['id']
            for d in self.days:
                weekday = d.weekday()

                # Salta i giorni in cui il task non può essere eseguito
                if task_id in self.unavailable_days and d in self.unavailable_days[task_id]:
                    continue

                # Salta i giorni della settimana non disponibili nel calendario
                if task_id not in self.available_slots or weekday not in self.available_slots[task_id]:
                    continue

                for h in self.available_slots[task_id][weekday]:
                    var_name = f"x_{task_id}_{d.strftime('%Y%m%d')}_{h}"
                    self.vars['x'][task_id, d, h] = self.model.addVar(
                        vtype="B", name=var_name
                    )

    def _create_constraints(self):
        """Crea i vincoli per il modello"""
        # Vincolo: ogni task deve essere pianificato per il numero di ore richiesto
        for _, task in self.tasks_df.iterrows():
            task_id = task['id']
            planned_hours = task['planned_hours']

            task_vars = [
                self.vars['x'][task_id, d, h]
                for d in self.days
                for h in range(24)
                if (task_id, d, h) in self.vars['x']
            ]

            if task_vars:  # Controlla che ci siano variabili disponibili
                self.model.addCons(
                    quicksum(task_vars) == planned_hours,
                    name=f"planned_hours_{task_id}"
                )

        # Vincolo: una risorsa può svolgere al massimo un'attività per ogni slot orario
        for d in self.days:
            for h in range(24):
                for user_id in self.tasks_df['user_id'].unique():
                    # Filtra i task per user_id
                    user_tasks = self.tasks_df[self.tasks_df['user_id'] == user_id]['id'].tolist()

                    slot_vars = [
                        self.vars['x'][task_id, d, h]
                        for task_id in user_tasks
                        if (task_id, d, h) in self.vars['x']
                    ]

                    if len(slot_vars) > 1:  # Se c'è più di una variabile, aggiungi il vincolo
                        self.model.addCons(
                            quicksum(slot_vars) <= 1,
                            name=f"one_task_per_slot_{user_id}_{d.strftime('%Y%m%d')}_{h}"
                        )

    def _create_objective(self):
        """Crea la funzione obiettivo del modello"""
        # Obiettivo: minimizzare la dispersione delle attività (preferire slot contigui)
        # Questo è solo un esempio, puoi modificarlo in base alle tue esigenze

        # Variabili ausiliarie per rilevare se un task è schedulato in un giorno
        task_day_vars = {}
        for _, task in self.tasks_df.iterrows():
            task_id = task['id']
            for d in self.days:
                day_vars = [
                    self.vars['x'][task_id, d, h]
                    for h in range(24)
                    if (task_id, d, h) in self.vars['x']
                ]

                if day_vars:
                    var_name = f"day_{task_id}_{d.strftime('%Y%m%d')}"
                    task_day_vars[task_id, d] = self.model.addVar(
                        vtype="B", name=var_name
                    )

                    # Constraint: day_var = 1 se almeno un'ora del giorno è pianificata
                    self.model.addCons(
                        quicksum(day_vars) <= 24 * task_day_vars[task_id, d],
                        name=f"link_day_{task_id}_{d.strftime('%Y%m%d')}"
                    )

                    self.model.addCons(
                        quicksum(day_vars) >= task_day_vars[task_id, d],
                        name=f"link_day_min_{task_id}_{d.strftime('%Y%m%d')}"
                    )

        # Obiettivo: minimizzare il numero di giorni utilizzati per ogni task
        all_day_vars = [var for var in task_day_vars.values()]
        self.model.setObjective(quicksum(all_day_vars), "minimize")

    def solve(self):
        """Risolve il modello di ottimizzazione"""
        logger.info("Avvio della risoluzione del modello")

        if not self.model:
            self.build_model()

        # Risolve il modello
        self.model.optimize()

        # Controlla lo stato della soluzione
        status = self.model.getStatus()
        logger.info(f"Stato della soluzione: {status}")

        if status == "optimal" or status == "feasible":
            self._extract_solution()
            return True
        else:
            logger.warning(f"Nessuna soluzione trovata. Stato: {status}")
            return False

    def _extract_solution(self):
        """Estrae la soluzione dal modello risolto"""
        logger.info("Estrazione della soluzione")

        # Prepara il dizionario della soluzione
        solution = {
            'tasks': {},
            'objective_value': self.model.getObjVal(),
            'status': self.model.getStatus(),
            'solve_time': self.model.getSolvingTime()
        }

        # Estrai l'assegnazione delle ore per ogni attività
        for key, var in self.vars['x'].items():
            if self.model.getVal(var) > 0.5:  # Variabile binaria attiva
                task_id, date, hour = key

                if task_id not in solution['tasks']:
                    solution['tasks'][task_id] = []

                solution['tasks'][task_id].append({
                    'date': date.strftime('%Y-%m-%d'),
                    'hour': hour
                })

        self.solution = solution
        logger.info("Soluzione estratta con successo")
        return solution

    def get_solution_dataframe(self):
        """
        Converte la soluzione in un DataFrame pandas per una facile manipolazione.

        Returns:
            DataFrame: La soluzione in formato DataFrame
        """
        if not self.solution:
            logger.warning("Nessuna soluzione disponibile")
            return None

        # Prepara i dati per il DataFrame
        rows = []
        for task_id, slots in self.solution['tasks'].items():
            task_name = self.tasks_df[self.tasks_df['id'] == task_id]['name'].iloc[0]
            user_id = self.tasks_df[self.tasks_df['id'] == task_id]['user_id'].iloc[0]

            for slot in slots:
                rows.append({
                    'task_id': task_id,
                    'task_name': task_name,
                    'user_id': user_id,
                    'date': slot['date'],
                    'hour': slot['hour']
                })

        # Crea il DataFrame
        if rows:
            df = pd.DataFrame(rows)
            # Ordina per data, ora e task
            df = df.sort_values(['date', 'hour', 'task_id'])
            return df
        else:
            return pd.DataFrame()