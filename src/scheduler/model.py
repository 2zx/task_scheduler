import logging
import pandas as pd
from datetime import datetime, timedelta, timezone
from ortools.sat.python import cp_model

from ..config import ORTOOLS_PARAMS, SCHEDULER_CONFIG
from .interval_model import IntervalSchedulingModel
from .greedy_model import GreedySchedulingModel, should_use_greedy

logger = logging.getLogger(__name__)


def get_utc_now():
    """Restituisce datetime corrente in UTC"""
    return datetime.now(timezone.utc)


def get_utc_date():
    """Restituisce data corrente in UTC"""
    return get_utc_now().date()


def get_next_business_date():
    """Restituisce il primo giorno utile per la pianificazione (domani in UTC)"""
    return get_utc_date() + timedelta(days=1)


class SchedulingModel:
    """
    Modello di ottimizzazione ibrido per la pianificazione delle attività.
    Utilizza algoritmo greedy per centinaia di task o OrTools per casi complessi.
    """

    def __init__(self, tasks_df, calendar_slots_df, leaves_df, initial_horizon_days=28, horizon_extension_factor=1.25):
        """
        Inizializza il modello con i dati necessari.

        Args:
            tasks_df: DataFrame con le attività da pianificare (include priority_score)
            calendar_slots_df: DataFrame con gli slot disponibili nel calendario
            leaves_df: DataFrame con le assenze pianificate
            initial_horizon_days: Numero di giorni dell'orizzonte temporale iniziale
            horizon_extension_factor: Fattore di estensione dell'orizzonte temporale
        """
        logger.info("Inizializzazione SchedulingModel ibrido (Greedy + OrTools)")

        # Determina quale algoritmo utilizzare
        use_greedy = should_use_greedy(tasks_df)

        if use_greedy:
            logger.info("Utilizzo algoritmo GREEDY per performance ottimizzate")
            self.model_impl = GreedySchedulingModel(
                tasks_df, calendar_slots_df, leaves_df, initial_horizon_days
            )
            self.algorithm_used = 'greedy'
        else:
            logger.info("Utilizzo algoritmo ORTOOLS per ottimizzazione avanzata")
            self.model_impl = IntervalSchedulingModel(
                tasks_df, calendar_slots_df, leaves_df,
                initial_horizon_days, horizon_extension_factor
            )
            self.algorithm_used = 'ortools'

        # Esponi interfaccia compatibile
        self.solution = None
        self.tasks_df = tasks_df

    def solve(self, max_horizon_days=SCHEDULER_CONFIG['max_horizon_days']):
        """Risolve il modello di ottimizzazione con strategia ibrida"""

        if self.algorithm_used == 'greedy':
            # Algoritmo greedy (sempre veloce)
            success = self.model_impl.solve()

            if success:
                self.solution = self.model_impl.solution

                # Verifica se ci sono task non schedulati
                scheduled_tasks = set(self.solution['tasks'].keys())
                all_tasks = set(self.tasks_df['id'].tolist())
                unscheduled_tasks = all_tasks - scheduled_tasks

                # Se ci sono pochi task non schedulati, prova OrTools per i residui
                if unscheduled_tasks and len(unscheduled_tasks) <= 20:
                    logger.info(f"Tentativo OrTools per {len(unscheduled_tasks)} task residui")
                    success = self._solve_residual_with_ortools(unscheduled_tasks, max_horizon_days)

                return success
            else:
                # Se greedy fallisce completamente, prova OrTools
                logger.warning("Greedy fallito, tentativo con OrTools")
                return self._fallback_to_ortools(max_horizon_days)

        else:
            # Algoritmo OrTools con timeout ridotto
            success = self.model_impl.solve(max_horizon_days)
            if success:
                self.solution = self.model_impl.solution
            return success

    def _solve_residual_with_ortools(self, unscheduled_task_ids, max_horizon_days):
        """Risolve task residui con OrTools"""

        try:
            # Filtra task non schedulati
            residual_tasks = self.tasks_df[self.tasks_df['id'].isin(unscheduled_task_ids)]

            # Crea modello OrTools per i residui
            ortools_model = IntervalSchedulingModel(
                residual_tasks,
                self.model_impl.calendar_slots_df,
                self.model_impl.leaves_df,
                initial_horizon_days=14,  # Orizzonte ridotto per velocità
                horizon_extension_factor=1.5
            )

            # Risolvi con timeout aggressivo
            success = ortools_model.solve(max_horizon_days=60)

            if success and ortools_model.solution:
                # Unisci risultati greedy + ortools
                self.solution['tasks'].update(ortools_model.solution['tasks'])
                logger.info(f"OrTools ha schedulato {len(ortools_model.solution['tasks'])} task residui")
                return True

            return True  # Mantieni risultato greedy anche se OrTools fallisce

        except Exception as e:
            logger.error(f"Errore in OrTools residui: {str(e)}")
            return True  # Mantieni risultato greedy

    def _fallback_to_ortools(self, max_horizon_days):
        """Fallback completo a OrTools se greedy fallisce"""

        try:
            logger.info("Fallback completo a OrTools")

            # Crea modello OrTools con parametri aggressivi
            self.model_impl = IntervalSchedulingModel(
                self.tasks_df,
                self.model_impl.calendar_slots_df,
                self.model_impl.leaves_df,
                initial_horizon_days=14,
                horizon_extension_factor=1.25
            )

            # Configura timeout molto aggressivo
            self.model_impl.solver.parameters.max_time_in_seconds = 30  # 30 secondi max

            success = self.model_impl.solve(max_horizon_days=90)

            if success:
                self.solution = self.model_impl.solution
                self.algorithm_used = 'ortools_fallback'

            return success

        except Exception as e:
            logger.error(f"Errore in fallback OrTools: {str(e)}")
            return False

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
        """Restituisce statistiche del solver con informazioni sull'algoritmo utilizzato"""

        stats = self.model_impl.get_solver_statistics()
        stats['algorithm_used'] = self.algorithm_used

        # Aggiungi statistiche specifiche per ibrido
        if hasattr(self, 'solution') and self.solution:
            stats['hybrid_success'] = True
            stats['tasks_scheduled'] = len(self.solution.get('tasks', {}))
            stats['tasks_total'] = len(self.tasks_df)
            stats['success_rate'] = stats['tasks_scheduled'] / stats['tasks_total']

        return stats


class LegacySchedulingModel:
    """
    Modello di ottimizzazione legacy (orario) per compatibilità.
    Mantiene il codice originale per fallback se necessario.
    """

    def __init__(self, tasks_df, calendar_slots_df, leaves_df, initial_horizon_days=28, horizon_extension_factor=1.25):
        """
        Inizializza il modello legacy con i dati necessari.
        """
        self.tasks_df = tasks_df
        self.calendar_slots_df = calendar_slots_df
        self.leaves_df = leaves_df
        self.initial_horizon_days = initial_horizon_days
        self.horizon_extension_factor = horizon_extension_factor
        self.current_horizon_days = initial_horizon_days
        self.model = None
        self.solver = None
        self.vars = {}
        self.solution = None

        # Prepara i dati per il modello
        self._prepare_data()

    def _prepare_data(self):
        """Prepara e trasforma i dati per il modello di ottimizzazione"""
        logger.info(f"Preparazione dei dati per il modello di ottimizzazione con orizzonte di {self.current_horizon_days} giorni")

        # Genera un orizzonte temporale di pianificazione - inizia dal primo giorno utile (domani in UTC)
        first_day = get_next_business_date()
        self.days = [first_day + timedelta(days=i) for i in range(self.current_horizon_days)]

        logger.info(f"Pianificazione legacy dal {first_day} per {self.current_horizon_days} giorni (UTC)")

        # Mappa i giorni della settimana (0-6) alle date effettive
        self.day_to_date = {d.weekday(): d for d in self.days}

        # Identifica gli slot temporali disponibili per ogni utente/attività
        self._prepare_available_slots()

        # Prepara i dati delle assenze
        self._prepare_leaves()

        logger.info("Preparazione dei dati completata")

    def _extend_planning_horizon(self):
        """Estende l'orizzonte temporale e rigenera il modello"""
        # Calcola il nuovo orizzonte (aumento del 25% di default)
        new_horizon = int(self.current_horizon_days * self.horizon_extension_factor)
        # Assicurati che ci sia almeno un incremento di 7 giorni
        if new_horizon - self.current_horizon_days < 7:
            new_horizon = self.current_horizon_days + 7

        logger.info(f"Estensione dell'orizzonte temporale da {self.current_horizon_days} a {new_horizon} giorni")

        # Estendi l'orizzonte
        self.current_horizon_days = new_horizon

        # Rigenera i dati con il nuovo orizzonte
        self._prepare_data()

        # Ricrea il modello
        self.model = None
        self.solver = None
        self.vars = {}
        self.build_model()

        return self.current_horizon_days

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
        # Limita il tempo di risoluzione per evitare blocchi
        self.solver.parameters.max_time_in_seconds = min(ORTOOLS_PARAMS['time_limit'], 300)  # Max 5 minuti per iterazione
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
        # Vincolo rigoroso: ogni task deve essere pianificato esattamente per le ore richieste
        for _, task in self.tasks_df.iterrows():
            task_id = task['id']
            remaining_hours = int(task['remaining_hours'])

            task_vars = [
                self.vars['x'][task_id, d, h]
                for d in self.days
                for h in range(24)
                if (task_id, d, h) in self.vars['x']
            ]

            if task_vars:  # Controlla che ci siano variabili disponibili
                # Vincolo di uguaglianza stretta
                self.model.Add(sum(task_vars) == remaining_hours)
                logger.debug(f"Task {task_id}: esattamente {remaining_hours} ore")

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

    def solve(self, max_horizon_days=SCHEDULER_CONFIG['max_horizon_days']):
        """
        Risolve il modello di ottimizzazione estendendo l'orizzonte se necessario.

        Args:
            max_horizon_days: Numero massimo di giorni dell'orizzonte temporale

        Returns:
            bool: True se è stata trovata una soluzione, False altrimenti
        """
        logger.info("Avvio della risoluzione del modello OrTools")

        if not self.model:
            self.build_model()

        # Configura un callback per il logging del progresso
        class SolutionCallback(cp_model.CpSolverSolutionCallback):
            def __init__(self, variables):
                cp_model.CpSolverSolutionCallback.__init__(self)
                self.__variables = variables
                self.__solution_count = 0
                self.__start_time = time.time()
                self.__last_log_time = self.__start_time
                self.__log_interval = 2  # Log ogni 2 secondi
                self.__progress_log_interval = 10  # Log di progresso ogni 10 secondi
                self.__last_progress_log_time = self.__start_time

            def on_solution_callback(self):
                self.__solution_count += 1
                current_time = time.time()
                elapsed = current_time - self.__start_time

                # Log solo ogni X secondi per non intasare il log
                if current_time - self.__last_log_time >= self.__log_interval:
                    logger.info(f"Soluzione intermedia #{self.__solution_count} trovata dopo {elapsed:.2f} secondi")
                    self.__last_log_time = current_time

            def __call__(self):
                # Chiamato periodicamente durante la ricerca
                current_time = time.time()
                elapsed = current_time - self.__start_time

                # Log di progresso periodico anche se non vengono trovate soluzioni
                if current_time - self.__last_progress_log_time >= self.__progress_log_interval:
                    logger.info(f"Ricerca in corso... {elapsed:.2f} secondi trascorsi, "
                                f"{self.__solution_count} soluzioni trovate finora")
                    self.__last_progress_log_time = current_time

                # Chiamata al metodo della classe base
                super().__call__()

        import time  # Importa il modulo time per il callback

        while self.current_horizon_days <= max_horizon_days:
            # Configura il solver con un callback
            self.solver.parameters.log_search_progress = True

            # Log prima di iniziare la risoluzione
            num_vars = len(self.vars['x'])
            logger.info(f"Inizio risoluzione con orizzonte di {self.current_horizon_days} giorni e {num_vars} variabili")
            logger.info(f"Parametri solver: time_limit={self.solver.parameters.max_time_in_seconds}s, "
                        f"workers={self.solver.parameters.num_search_workers}")

            # Risolve il modello con l'orizzonte attuale
            solution_callback = SolutionCallback(self.vars['x'])
            status = self.solver.Solve(self.model, solution_callback)
            status_name = self.solver.StatusName(status)
            logger.info(f"Stato della soluzione con orizzonte di {self.current_horizon_days} giorni: {status_name}")

            if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                self._extract_solution()
                return True
            elif status == cp_model.INFEASIBLE:
                logger.warning(f"Modello INFEASIBLE con orizzonte di {self.current_horizon_days} giorni - Estendo orizzonte")
                self._extend_planning_horizon()
            else:
                logger.warning(f"Stato non gestito: {status_name}. Estensione dell'orizzonte")
                self._extend_planning_horizon()

        logger.error(f"Nessuna soluzione trovata anche con orizzonte massimo di {max_horizon_days} giorni")
        return False

    def _extract_solution(self):
        """Estrae la soluzione dal modello risolto"""
        logger.info("Estrazione della soluzione")

        # Prepara il dizionario della soluzione
        solution = {
            'tasks': {},
            'objective_value': self.solver.ObjectiveValue(),
            'status': self.solver.StatusName(),
            'solve_time': self.solver.WallTime(),
            'horizon_days': self.current_horizon_days
        }

        # Estrai l'assegnazione delle ore per ogni attività
        for key, var in self.vars['x'].items():
            if self.solver.Value(var):  # Variabile booleana attiva
                task_id, date, hour = key

                # Converti task_id in stringa per JSON serialization
                task_id_str = str(int(task_id))
                if task_id_str not in solution['tasks']:
                    solution['tasks'][task_id_str] = []

                solution['tasks'][task_id_str].append({
                    'date': date.strftime('%Y-%m-%d'),
                    'hour': int(hour)  # Assicura che hour sia int standard
                })

        self.solution = solution
        logger.info(f"Soluzione estratta con successo (orizzonte: {self.current_horizon_days} giorni)")
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

        stats = {
            'status': self.solver.StatusName(),
            'objective_value': self.solver.ObjectiveValue() if self.solver.StatusName() in ['OPTIMAL', 'FEASIBLE'] else None,
            'wall_time': self.solver.WallTime(),
            'user_time': self.solver.UserTime(),
            'num_branches': self.solver.NumBranches(),
            'num_conflicts': self.solver.NumConflicts(),
            'num_booleans': self.solver.NumBooleans(),
            'num_constraints': self.solver.NumConstraints()
        }

        # Aggiungi informazioni sull'orizzonte temporale
        if hasattr(self, 'current_horizon_days'):
            stats['horizon_days'] = self.current_horizon_days
            stats['initial_horizon_days'] = self.initial_horizon_days

        return stats
