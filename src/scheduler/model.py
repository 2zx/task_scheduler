import logging
import pandas as pd
from datetime import datetime, timedelta
from ortools.sat.python import cp_model

from ..config import ORTOOLS_PARAMS

logger = logging.getLogger(__name__)


class SchedulingModel:
    """
    Modello di ottimizzazione per la pianificazione delle attività
    utilizzando Google OrTools CP-SAT come solutore.
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
        self.solver = None
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

        # Debug: stampa i dati del calendario
        logger.debug(f"Calendar slots DataFrame shape: {self.calendar_slots_df.shape}")
        logger.debug(f"Calendar slots columns: {list(self.calendar_slots_df.columns)}")

        if self.calendar_slots_df.empty:
            logger.warning("Nessun slot di calendario disponibile!")
            return

        for _, row in self.calendar_slots_df.iterrows():
            task_id = row['task_id']
            day = int(row['dayofweek'])  # Converti a intero
            hour_from = row['hour_from']
            hour_to = row['hour_to']

            logger.debug(f"Processing calendar slot: task_id={task_id}, day={day}, hours={hour_from}-{hour_to}")

            # Calcola gli slot orari (es. 9-10, 10-11, etc.)
            hours = list(range(int(hour_from), int(hour_to)))

            if task_id not in self.available_slots:
                self.available_slots[task_id] = {}

            if day not in self.available_slots[task_id]:
                self.available_slots[task_id][day] = []

            self.available_slots[task_id][day].extend(hours)

        logger.info(f"Prepared available slots for {len(self.available_slots)} tasks")
        for task_id, slots in self.available_slots.items():
            total_hours = sum(len(hours) for hours in slots.values())
            logger.debug(f"Task {task_id}: {len(slots)} days, {total_hours} total hours")

    def _prepare_leaves(self):
        """Prepara i dati sulle assenze, convertendoli in giorni non disponibili"""
        self.unavailable_days = {}

        # Definisci il periodo di pianificazione
        planning_start = self.days[0]
        planning_end = self.days[-1]

        logger.debug(f"Planning period: {planning_start} to {planning_end}")

        leaves_in_period = 0
        total_leaves_processed = 0

        for _, row in self.leaves_df.iterrows():
            task_id = row['task_id']
            date_from = row['date_from'].date() if isinstance(row['date_from'], datetime) else row['date_from']
            date_to = row['date_to'].date() if isinstance(row['date_to'], datetime) else row['date_to']

            total_leaves_processed += 1

            # Filtra solo le assenze che si sovrappongono al periodo di pianificazione
            if date_to < planning_start or date_from > planning_end:
                continue  # Assenza fuori dal periodo di pianificazione

            # Limita le date al periodo di pianificazione
            effective_start = max(date_from, planning_start)
            effective_end = min(date_to, planning_end)

            # Calcola tutti i giorni di assenza nel periodo
            current_date = effective_start
            while current_date <= effective_end:
                if task_id not in self.unavailable_days:
                    self.unavailable_days[task_id] = []

                self.unavailable_days[task_id].append(current_date)
                current_date += timedelta(days=1)
                leaves_in_period += 1

        logger.info(f"Processed {total_leaves_processed} total leaves, {leaves_in_period} days in planning period")

        # Log statistiche per task
        for task_id, days in self.unavailable_days.items():
            logger.debug(f"Task {task_id}: {len(days)} unavailable days in planning period")

    def build_model(self):
        """Costruisce il modello di ottimizzazione OrTools CP-SAT"""
        logger.info("Costruzione del modello di ottimizzazione OrTools")

        # Inizializza il modello CP-SAT
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        # Configura i parametri del solutore
        self.solver.parameters.max_time_in_seconds = ORTOOLS_PARAMS['time_limit']
        self.solver.parameters.num_search_workers = ORTOOLS_PARAMS['num_search_workers']
        self.solver.parameters.log_search_progress = ORTOOLS_PARAMS['log_search_progress']

        # Definisci le variabili di decisione e i vincoli
        self._create_variables()
        self._create_constraints()
        self._create_objective()

        logger.info("Modello di ottimizzazione OrTools costruito")
        return self.model

    def _create_variables(self):
        """Crea le variabili di decisione per il modello"""
        # Variabile booleana x[t,d,h] = True se il task t è schedulato nel giorno d all'ora h
        self.vars['x'] = {}

        logger.debug("Creating variables...")
        variables_created = 0

        for _, task in self.tasks_df.iterrows():
            task_id = task['id']
            logger.debug(f"Creating variables for task {task_id}")

            task_variables = 0
            for d in self.days:
                weekday = d.weekday()

                # Salta i giorni in cui il task non può essere eseguito
                if task_id in self.unavailable_days and d in self.unavailable_days[task_id]:
                    logger.debug(f"  Skipping {d} (unavailable day)")
                    continue

                # Salta i giorni della settimana non disponibili nel calendario
                if task_id not in self.available_slots:
                    logger.debug(f"  Task {task_id} not in available_slots")
                    continue

                if weekday not in self.available_slots[task_id]:
                    logger.debug(f"  Weekday {weekday} not available for task {task_id}")
                    continue

                for h in self.available_slots[task_id][weekday]:
                    var_name = f"x_{task_id}_{d.strftime('%Y%m%d')}_{h}"
                    self.vars['x'][task_id, d, h] = self.model.NewBoolVar(var_name)
                    variables_created += 1
                    task_variables += 1

            logger.debug(f"  Created {task_variables} variables for task {task_id}")

        logger.info(f"Total variables created: {variables_created}")

        if variables_created == 0:
            logger.error("NO VARIABLES CREATED! This will cause the model to have no solution.")
            logger.error("Available slots summary:")
            for task_id, slots in self.available_slots.items():
                logger.error(f"  Task {task_id}: {list(slots.keys())} weekdays")

    def _create_constraints(self):
        """Crea i vincoli per il modello"""
        # Vincolo rilassato: ogni task deve essere pianificato per almeno il 50% delle ore richieste
        # ma non più del 100%
        for _, task in self.tasks_df.iterrows():
            task_id = task['id']
            planned_hours = int(task['planned_hours'])
            min_hours = max(1, planned_hours // 2)  # Almeno 50% delle ore, minimo 1
            max_hours = planned_hours

            task_vars = [
                self.vars['x'][task_id, d, h]
                for d in self.days
                for h in range(24)
                if (task_id, d, h) in self.vars['x']
            ]

            if task_vars:  # Controlla che ci siano variabili disponibili
                # Vincolo minimo e massimo invece di uguaglianza stretta
                self.model.Add(sum(task_vars) >= min_hours)
                self.model.Add(sum(task_vars) <= max_hours)
                logger.debug(f"Task {task_id}: {min_hours}-{max_hours} ore (richieste: {planned_hours})")

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
                        self.model.Add(sum(slot_vars) <= 1)

    def _create_objective(self):
        """Crea la funzione obiettivo del modello"""
        # Obiettivo: minimizzare la dispersione delle attività (preferire slot contigui)

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
                    task_day_vars[task_id, d] = self.model.NewBoolVar(var_name)

                    # Constraint: day_var = True se almeno un'ora del giorno è pianificata
                    self.model.Add(sum(day_vars) <= 24 * task_day_vars[task_id, d])
                    self.model.Add(sum(day_vars) >= task_day_vars[task_id, d])

        # Obiettivo: minimizzare il numero di giorni utilizzati per ogni task
        all_day_vars = list(task_day_vars.values())
        if all_day_vars:
            self.model.Minimize(sum(all_day_vars))

    def solve(self):
        """Risolve il modello di ottimizzazione"""
        logger.info("Avvio della risoluzione del modello OrTools")

        if not self.model:
            self.build_model()

        # Risolve il modello
        status = self.solver.Solve(self.model)

        # Controlla lo stato della soluzione
        status_name = self.solver.StatusName(status)
        logger.info(f"Stato della soluzione: {status_name}")

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            self._extract_solution()
            return True
        elif status == cp_model.INFEASIBLE:
            logger.warning("Modello INFEASIBLE - Tentativo con vincoli ancora più rilassati")
            return self._solve_with_relaxed_constraints()
        else:
            logger.warning(f"Nessuna soluzione trovata. Stato: {status_name}")
            return False

    def _solve_with_relaxed_constraints(self):
        """Risolve il modello con vincoli molto rilassati"""
        logger.info("Tentativo di risoluzione con vincoli rilassati")

        # Ricrea il modello con vincoli più rilassati
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        # Configura i parametri del solutore
        self.solver.parameters.max_time_in_seconds = ORTOOLS_PARAMS['time_limit']
        self.solver.parameters.num_search_workers = ORTOOLS_PARAMS['num_search_workers']
        self.solver.parameters.log_search_progress = ORTOOLS_PARAMS['log_search_progress']

        # Ricrea le variabili (sono già create)
        # Crea vincoli molto rilassati
        self._create_relaxed_constraints()
        self._create_objective()

        # Risolve il modello rilassato
        status = self.solver.Solve(self.model)
        status_name = self.solver.StatusName(status)
        logger.info(f"Stato della soluzione rilassata: {status_name}")

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            self._extract_solution()
            return True
        else:
            logger.error(f"Anche il modello rilassato non ha soluzione: {status_name}")
            return False

    def _create_relaxed_constraints(self):
        """Crea vincoli molto rilassati per trovare almeno una soluzione"""
        # Vincolo molto rilassato: ogni task deve essere pianificato per almeno 1 ora
        for _, task in self.tasks_df.iterrows():
            task_id = task['id']
            planned_hours = int(task['planned_hours'])
            min_hours = 1  # Almeno 1 ora
            max_hours = min(planned_hours, 8)  # Massimo 8 ore per task

            task_vars = [
                self.vars['x'][task_id, d, h]
                for d in self.days
                for h in range(24)
                if (task_id, d, h) in self.vars['x']
            ]

            if task_vars:  # Controlla che ci siano variabili disponibili
                self.model.Add(sum(task_vars) >= min_hours)
                self.model.Add(sum(task_vars) <= max_hours)
                logger.debug(f"Relaxed Task {task_id}: {min_hours}-{max_hours} ore (richieste: {planned_hours})")

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
                        self.model.Add(sum(slot_vars) <= 1)

    def _extract_solution(self):
        """Estrae la soluzione dal modello risolto"""
        logger.info("Estrazione della soluzione")

        # Prepara il dizionario della soluzione
        solution = {
            'tasks': {},
            'objective_value': self.solver.ObjectiveValue(),
            'status': self.solver.StatusName(),
            'solve_time': self.solver.WallTime()
        }

        # Estrai l'assegnazione delle ore per ogni attività
        for key, var in self.vars['x'].items():
            if self.solver.Value(var):  # Variabile booleana attiva
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
            # Converti task_id a int se è una stringa
            task_id_int = int(task_id) if isinstance(task_id, str) else task_id

            # Trova le informazioni del task
            task_info = self.tasks_df[self.tasks_df['id'] == task_id_int]
            if task_info.empty:
                logger.warning(f"Task {task_id_int} non trovato nel DataFrame dei task")
                continue

            task_name = task_info['name'].iloc[0]
            user_id = task_info['user_id'].iloc[0]

            for slot in slots:
                rows.append({
                    'task_id': task_id_int,
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
            return pd.DataFrame(columns=['task_id', 'task_name', 'user_id', 'date', 'hour'])

    def get_solver_statistics(self):
        """
        Restituisce le statistiche del solver per analisi delle performance.

        Returns:
            dict: Dizionario con le statistiche del solver
        """
        if not self.solver:
            return {}

        return {
            'status': self.solver.StatusName(),
            'objective_value': self.solver.ObjectiveValue() if self.solver.StatusName() in ['OPTIMAL', 'FEASIBLE'] else None,
            'wall_time': self.solver.WallTime(),
            'user_time': self.solver.UserTime(),
            'num_branches': self.solver.NumBranches(),
            'num_conflicts': self.solver.NumConflicts(),
            'num_booleans': self.solver.NumBooleans(),
            'num_constraints': self.solver.NumConstraints()
        }
