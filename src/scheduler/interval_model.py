import logging
import pandas as pd
from datetime import datetime, timedelta
from ortools.sat.python import cp_model
from dataclasses import dataclass
from typing import List, Dict, Tuple

from ..config import ORTOOLS_PARAMS

logger = logging.getLogger(__name__)


@dataclass
class ContiguousSlot:
    """Rappresenta uno slot di tempo contiguo disponibile per un task"""
    task_id: int
    user_id: int
    start_datetime: datetime
    end_datetime: datetime
    duration_hours: float
    weekday: int

    def __post_init__(self):
        if self.duration_hours <= 0:
            self.duration_hours = (self.end_datetime - self.start_datetime).total_seconds() / 3600


class IntervalSchedulingModel:
    """
    Modello di ottimizzazione interval-based per la pianificazione delle attività.
    Utilizza slot contigui invece di variabili orarie per migliorare drasticamente le performance.
    """

    def __init__(self, tasks_df, calendar_slots_df, leaves_df, initial_horizon_days=28, horizon_extension_factor=1.25):
        """
        Inizializza il modello interval-based.

        Args:
            tasks_df: DataFrame con le attività da pianificare (include priority_score)
            calendar_slots_df: DataFrame con gli slot disponibili nel calendario
            leaves_df: DataFrame con le assenze pianificate
            initial_horizon_days: Numero di giorni dell'orizzonte temporale iniziale
            horizon_extension_factor: Fattore di estensione dell'orizzonte temporale
        """
        self.tasks_df = tasks_df.copy()
        self.calendar_slots_df = calendar_slots_df
        self.leaves_df = leaves_df
        self.initial_horizon_days = initial_horizon_days
        self.horizon_extension_factor = horizon_extension_factor
        self.current_horizon_days = initial_horizon_days

        # Ordina i task per priorità (score più basso = priorità più alta)
        if 'priority_score' in self.tasks_df.columns:
            self.tasks_df = self.tasks_df.sort_values('priority_score', ascending=True)
            logger.info(f"Task ordinati per priorità: {self.tasks_df[['id', 'priority_score']].to_dict('records')}")

        self.model = None
        self.solver = None
        self.vars = {}
        self.solution = None
        self.contiguous_slots = []

        # Prepara i dati per il modello
        self._prepare_data()

    def _prepare_data(self):
        """Prepara e trasforma i dati per il modello interval-based"""
        logger.info(f"Preparazione dati interval-based con orizzonte di {self.current_horizon_days} giorni")

        # Genera orizzonte temporale
        today = datetime.now().date()
        self.days = [today + timedelta(days=i) for i in range(self.current_horizon_days)]

        # Calcola slot contigui
        self._calculate_contiguous_slots()

        # Applica assenze
        self._apply_leaves_to_slots()

        logger.info(f"Preparazione completata: {len(self.contiguous_slots)} slot contigui generati")

    def _calculate_contiguous_slots(self):
        """Calcola slot di disponibilità oraria contigua per ogni task/risorsa"""
        self.contiguous_slots = []

        if self.calendar_slots_df.empty:
            logger.warning("Nessun slot di calendario disponibile!")
            return

        # Raggruppa per task_id e dayofweek per trovare slot contigui
        grouped = self.calendar_slots_df.groupby(['task_id', 'dayofweek'])

        for (task_id, dayofweek), group in grouped:
            # Trova user_id per questo task
            task_info = self.tasks_df[self.tasks_df['id'] == task_id]
            if task_info.empty:
                continue
            user_id = task_info.iloc[0]['user_id']

            # Ordina per hour_from per trovare slot contigui
            group_sorted = group.sort_values('hour_from')

            # Trova slot contigui per questo giorno della settimana
            current_start = None
            current_end = None

            for _, row in group_sorted.iterrows():
                hour_from = int(row['hour_from'])
                hour_to = int(row['hour_to'])

                if current_start is None:
                    # Primo slot
                    current_start = hour_from
                    current_end = hour_to
                elif hour_from == current_end:
                    # Slot contiguo, estendi
                    current_end = hour_to
                else:
                    # Gap trovato, salva slot precedente e inizia nuovo
                    self._add_slots_for_weekday(task_id, user_id, dayofweek, current_start, current_end)
                    current_start = hour_from
                    current_end = hour_to

            # Salva ultimo slot
            if current_start is not None:
                self._add_slots_for_weekday(task_id, user_id, dayofweek, current_start, current_end)

        logger.info(f"Generati {len(self.contiguous_slots)} slot contigui")

    def _add_slots_for_weekday(self, task_id, user_id, weekday, hour_from, hour_to):
        """Aggiunge slot contigui per un giorno della settimana specifico"""
        duration_hours = hour_to - hour_from

        # Crea slot per ogni occorrenza di questo weekday nell'orizzonte
        for day in self.days:
            if day.weekday() == weekday:
                start_datetime = datetime.combine(day, datetime.min.time()) + timedelta(hours=hour_from)
                end_datetime = datetime.combine(day, datetime.min.time()) + timedelta(hours=hour_to)

                slot = ContiguousSlot(
                    task_id=task_id,
                    user_id=user_id,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    duration_hours=duration_hours,
                    weekday=weekday
                )
                self.contiguous_slots.append(slot)

    def _apply_leaves_to_slots(self):
        """Rimuove o spezza slot che si sovrappongono con assenze"""
        if self.leaves_df.empty:
            return

        original_count = len(self.contiguous_slots)
        filtered_slots = []

        for slot in self.contiguous_slots:
            # Trova assenze per questo task
            task_leaves = self.leaves_df[self.leaves_df['task_id'] == slot.task_id]

            slot_conflicts = False
            for _, leave in task_leaves.iterrows():
                leave_start = leave['date_from'].date()
                leave_end = leave['date_to'].date()
                slot_date = slot.start_datetime.date()

                # Controlla sovrapposizione
                if leave_start <= slot_date <= leave_end:
                    slot_conflicts = True
                    break

            if not slot_conflicts:
                filtered_slots.append(slot)

        self.contiguous_slots = filtered_slots
        removed_count = original_count - len(filtered_slots)

        if removed_count > 0:
            logger.info(f"Rimossi {removed_count} slot a causa di assenze")

    def _extend_planning_horizon(self):
        """Estende l'orizzonte temporale e rigenera il modello"""
        new_horizon = int(self.current_horizon_days * self.horizon_extension_factor)
        if new_horizon - self.current_horizon_days < 7:
            new_horizon = self.current_horizon_days + 7

        logger.info(f"Estensione orizzonte da {self.current_horizon_days} a {new_horizon} giorni")

        self.current_horizon_days = new_horizon
        self._prepare_data()

        # Ricrea il modello
        self.model = None
        self.solver = None
        self.vars = {}
        self.build_model()

        return self.current_horizon_days

    def build_model(self):
        """Costruisce il modello di ottimizzazione interval-based"""
        logger.info("Costruzione modello interval-based OrTools")

        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        # Configura parametri solver
        self.solver.parameters.max_time_in_seconds = min(ORTOOLS_PARAMS['time_limit'], 300)
        self.solver.parameters.num_search_workers = ORTOOLS_PARAMS['num_search_workers']
        self.solver.parameters.log_search_progress = ORTOOLS_PARAMS['log_search_progress']

        # Crea variabili e vincoli
        self._create_interval_variables()
        self._create_interval_constraints()
        self._create_priority_objective()

        logger.info("Modello interval-based costruito")
        return self.model

    def _create_interval_variables(self):
        """Crea variabili di decisione per il modello interval-based"""
        self.vars = {
            'assign': {},      # assign[task_id, slot_idx] = bool (task usa questo slot?)
            'duration': {},    # duration[task_id, slot_idx] = int (ore utilizzate del slot)
            'start_time': {},  # start_time[task_id, slot_idx] = int (ora di inizio nel slot)
        }

        variables_created = 0

        # Raggruppa slot per task
        slots_by_task = {}
        for i, slot in enumerate(self.contiguous_slots):
            if slot.task_id not in slots_by_task:
                slots_by_task[slot.task_id] = []
            slots_by_task[slot.task_id].append((i, slot))

        for task_id, task_slots in slots_by_task.items():
            logger.debug(f"Creazione variabili per task {task_id}: {len(task_slots)} slot disponibili")

            for slot_idx, slot in task_slots:
                # Variabile: questo task usa questo slot?
                assign_var = self.model.NewBoolVar(f'assign_{task_id}_{slot_idx}')
                self.vars['assign'][task_id, slot_idx] = assign_var

                # Variabile: quante ore del slot vengono utilizzate?
                max_duration = int(slot.duration_hours)
                duration_var = self.model.NewIntVar(0, max_duration, f'duration_{task_id}_{slot_idx}')
                self.vars['duration'][task_id, slot_idx] = duration_var

                # Vincolo: se non assegnato, durata = 0
                self.model.Add(duration_var <= max_duration * assign_var)

                variables_created += 2

        logger.info(f"Variabili create: {variables_created} (vs ~{len(self.contiguous_slots) * 24 * self.current_horizon_days} nel modello orario)")

    def _create_interval_constraints(self):
        """Crea vincoli per il modello interval-based"""

        # 1. Vincolo durata: ogni task deve avere esattamente planned_hours
        for _, task in self.tasks_df.iterrows():
            task_id = task['id']
            planned_hours = int(task['planned_hours'])

            # Somma durate di tutti gli slot assegnati a questo task
            duration_vars = [
                self.vars['duration'][task_id, slot_idx]
                for slot_idx, slot in enumerate(self.contiguous_slots)
                if slot.task_id == task_id and (task_id, slot_idx) in self.vars['duration']
            ]

            if duration_vars:
                self.model.Add(sum(duration_vars) == planned_hours)
                logger.debug(f"Task {task_id}: vincolo durata {planned_hours} ore")

        # 2. Vincolo non sovrapposizione: stessa risorsa non può fare 2 task contemporaneamente
        self._create_non_overlap_constraints()

    def _create_non_overlap_constraints(self):
        """Crea vincoli di non sovrapposizione per stessa risorsa"""
        # Raggruppa slot per user_id e datetime
        slots_by_user_time = {}

        for slot_idx, slot in enumerate(self.contiguous_slots):
            key = (slot.user_id, slot.start_datetime, slot.end_datetime)
            if key not in slots_by_user_time:
                slots_by_user_time[key] = []
            slots_by_user_time[key].append((slot.task_id, slot_idx))

        # Per ogni combinazione user+time, massimo un task può essere assegnato
        for (user_id, start_time, end_time), task_slots in slots_by_user_time.items():
            if len(task_slots) > 1:
                assign_vars = [
                    self.vars['assign'][task_id, slot_idx]
                    for task_id, slot_idx in task_slots
                    if (task_id, slot_idx) in self.vars['assign']
                ]

                if len(assign_vars) > 1:
                    self.model.Add(sum(assign_vars) <= 1)

    def _create_priority_objective(self):
        """Crea funzione obiettivo che considera priorità e contiguità"""
        objective_terms = []

        # Termine 1: Priorità - penalizza ritardi per task ad alta priorità
        for _, task in self.tasks_df.iterrows():
            task_id = task['id']
            priority_score = task.get('priority_score', 50.0)

            # Peso priorità: più basso il score, più alta la penalità per ritardi
            priority_weight = 100.0 / (priority_score + 1.0)

            # Penalizza assegnazione a slot tardivi per task prioritari
            for slot_idx, slot in enumerate(self.contiguous_slots):
                if slot.task_id == task_id and (task_id, slot_idx) in self.vars['assign']:
                    # Calcola "lateness" del slot (giorni dall'inizio orizzonte)
                    days_from_start = (slot.start_datetime.date() - self.days[0]).days
                    lateness_penalty = days_from_start * priority_weight

                    objective_terms.append(
                        lateness_penalty * self.vars['assign'][task_id, slot_idx]
                    )

        # Termine 2: Contiguità - preferisce meno slot per task
        for _, task in self.tasks_df.iterrows():
            task_id = task['id']

            # Conta numero di slot utilizzati per questo task
            assign_vars = [
                self.vars['assign'][task_id, slot_idx]
                for slot_idx, slot in enumerate(self.contiguous_slots)
                if slot.task_id == task_id and (task_id, slot_idx) in self.vars['assign']
            ]

            # Penalizza uso di molti slot (preferisce contiguità)
            for assign_var in assign_vars:
                objective_terms.append(0.1 * assign_var)  # Peso minore rispetto a priorità

        if objective_terms:
            self.model.Minimize(sum(objective_terms))
            logger.info(f"Obiettivo creato con {len(objective_terms)} termini")
        else:
            logger.warning("Nessun termine nell'obiettivo!")

    def solve(self, max_horizon_days=365 * 5):
        """Risolve il modello interval-based"""
        logger.info("Avvio risoluzione modello interval-based")

        if not self.model:
            self.build_model()

        while self.current_horizon_days <= max_horizon_days:
            num_vars = len(self.vars['assign']) + len(self.vars['duration'])
            logger.info(f"Risoluzione con orizzonte {self.current_horizon_days} giorni, {num_vars} variabili")

            status = self.solver.Solve(self.model)
            status_name = self.solver.StatusName(status)
            logger.info(f"Stato soluzione: {status_name}")

            if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                self._extract_interval_solution()
                return True
            elif status == cp_model.INFEASIBLE:
                logger.warning(f"Modello INFEASIBLE - Estendo orizzonte")
                self._extend_planning_horizon()
            else:
                logger.warning(f"Stato non gestito: {status_name}")
                self._extend_planning_horizon()

        logger.error(f"Nessuna soluzione trovata con orizzonte massimo {max_horizon_days} giorni")
        return False

    def _extract_interval_solution(self):
        """Estrae la soluzione dal modello interval-based"""
        logger.info("Estrazione soluzione interval-based")

        solution = {
            'tasks': {},
            'objective_value': self.solver.ObjectiveValue(),
            'status': self.solver.StatusName(),
            'solve_time': self.solver.WallTime(),
            'horizon_days': self.current_horizon_days
        }

        # Estrai assegnazioni
        for (task_id, slot_idx), assign_var in self.vars['assign'].items():
            if self.solver.Value(assign_var):  # Slot assegnato
                slot = self.contiguous_slots[slot_idx]
                duration = self.solver.Value(self.vars['duration'][task_id, slot_idx])

                if task_id not in solution['tasks']:
                    solution['tasks'][task_id] = []

                # Converti in formato compatibile (slot orari)
                start_hour = slot.start_datetime.hour
                for h in range(duration):
                    solution['tasks'][task_id].append({
                        'date': slot.start_datetime.date().strftime('%Y-%m-%d'),
                        'hour': start_hour + h
                    })

        self.solution = solution
        logger.info(f"Soluzione estratta: {len(solution['tasks'])} task pianificati")
        return solution

    def get_solver_statistics(self):
        """Restituisce statistiche del solver"""
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
            'num_constraints': self.solver.NumConstraints(),
            'horizon_days': self.current_horizon_days,
            'initial_horizon_days': self.initial_horizon_days,
            'contiguous_slots_count': len(self.contiguous_slots)
        }
