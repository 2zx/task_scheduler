import logging
import pandas as pd
import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AvailableBlock:
    """Rappresenta un blocco di tempo disponibile per una risorsa"""
    user_id: int
    start_datetime: datetime
    end_datetime: datetime
    duration_hours: float
    weekday: int

    def can_fit(self, hours_needed: float) -> bool:
        """Verifica se il blocco può contenere le ore richieste"""
        return self.duration_hours >= hours_needed


@dataclass
class ScheduledSlot:
    """Rappresenta uno slot schedulato per un task"""
    task_id: int
    user_id: int
    date: str
    hour: int


class GreedySchedulingModel:
    """
    Algoritmo greedy ottimizzato per la pianificazione di centinaia di task.
    Complessità O(n log n) invece di esponenziale.
    """

    def __init__(self, tasks_df, calendar_slots_df, leaves_df, initial_horizon_days=28):
        """
        Inizializza il modello greedy.

        Args:
            tasks_df: DataFrame con le attività da pianificare (include priority_score)
            calendar_slots_df: DataFrame con gli slot disponibili nel calendario
            leaves_df: DataFrame con le assenze pianificate
            initial_horizon_days: Numero di giorni dell'orizzonte temporale
        """
        self.tasks_df = tasks_df.copy()
        self.calendar_slots_df = calendar_slots_df
        self.leaves_df = leaves_df
        self.horizon_days = initial_horizon_days

        # Statistiche per monitoring
        self.stats = {
            'algorithm': 'greedy',
            'tasks_total': len(tasks_df),
            'tasks_scheduled': 0,
            'execution_time': 0,
            'success_rate': 0
        }

        self.solution = None
        self.occupied_slots = {}  # {user_id: {date: [hours]}}
        self.available_blocks = {}  # {user_id: [AvailableBlock]}

        # Prepara i dati
        self._prepare_data()

    def _prepare_data(self):
        """Prepara e ottimizza i dati per l'algoritmo greedy"""
        logger.info(f"Preparazione dati greedy per {len(self.tasks_df)} task")

        # Ordina task per priorità e criteri secondari
        self._sort_tasks_optimally()

        # Calcola orizzonte ottimale per ogni risorsa
        self._calculate_optimal_horizon()

        # Genera blocchi disponibili per ogni risorsa
        self._generate_available_blocks()

        # Applica assenze
        self._apply_leaves_to_blocks()

        logger.info(f"Preparazione completata: {sum(len(blocks) for blocks in self.available_blocks.values())} blocchi disponibili")

    def _sort_tasks_optimally(self):
        """Ordina i task per massimizzare l'efficacia dell'algoritmo greedy"""

        # Ordinamento multi-criterio per ottimizzare greedy
        sort_criteria = ['priority_score', 'planned_hours', 'user_id', 'id']
        sort_ascending = [True, False, True, True]  # Priorità alta, ore alte, user raggruppati

        self.tasks_df = self.tasks_df.sort_values(sort_criteria, ascending=sort_ascending)

        logger.info(f"Task ordinati per greedy: priorità {self.tasks_df['priority_score'].min():.1f}-{self.tasks_df['priority_score'].max():.1f}")

    def _calculate_optimal_horizon(self):
        """Calcola orizzonte ottimale basato sul carico di lavoro per risorsa"""

        max_horizon_needed = self.horizon_days

        # Calcola orizzonte per ogni risorsa
        for user_id in self.tasks_df['user_id'].unique():
            user_tasks = self.tasks_df[self.tasks_df['user_id'] == user_id]
            total_hours = user_tasks['planned_hours'].sum()

            # Stima giorni necessari (8 ore lavorative/giorno, 5 giorni/settimana)
            working_hours_per_week = 40
            weeks_needed = math.ceil(total_hours / working_hours_per_week)
            days_needed = weeks_needed * 7  # Include weekend

            # Aggiungi buffer del 50% per task lunghi
            days_with_buffer = int(days_needed * 1.5)
            max_horizon_needed = max(max_horizon_needed, days_with_buffer)

        # Rimuovi limite fisso - permetti estensione fino a 5 anni se necessario
        max_allowed_days = 1825  # 5 anni
        self.horizon_days = min(max_horizon_needed, max_allowed_days)

        logger.info(f"Orizzonte ottimizzato: {self.horizon_days} giorni (max consentito: {max_allowed_days})")

    def _generate_available_blocks(self):
        """Genera blocchi di tempo disponibili per ogni risorsa"""

        self.available_blocks = {}
        self.occupied_slots = {}

        # Genera orizzonte temporale
        today = datetime.now().date()
        days = [today + timedelta(days=i) for i in range(self.horizon_days)]

        # Per ogni risorsa
        for user_id in self.tasks_df['user_id'].unique():
            self.available_blocks[user_id] = []
            self.occupied_slots[user_id] = {}

            # Trova slot di calendario per questa risorsa
            user_calendar = self.calendar_slots_df[
                self.calendar_slots_df['task_id'].isin(
                    self.tasks_df[self.tasks_df['user_id'] == user_id]['id']
                )
            ].drop_duplicates(['dayofweek', 'hour_from', 'hour_to'])

            if user_calendar.empty:
                logger.warning(f"Nessun calendario trovato per user {user_id}")
                continue

            # Genera blocchi per ogni giorno
            for day in days:
                weekday = day.weekday()

                # Trova slot per questo giorno della settimana
                day_slots = user_calendar[user_calendar['dayofweek'] == weekday]

                for _, slot in day_slots.iterrows():
                    start_hour = int(slot['hour_from'])
                    end_hour = int(slot['hour_to'])
                    duration = end_hour - start_hour

                    if duration > 0:
                        start_datetime = datetime.combine(day, datetime.min.time()) + timedelta(hours=start_hour)
                        end_datetime = datetime.combine(day, datetime.min.time()) + timedelta(hours=end_hour)

                        block = AvailableBlock(
                            user_id=user_id,
                            start_datetime=start_datetime,
                            end_datetime=end_datetime,
                            duration_hours=duration,
                            weekday=weekday
                        )
                        self.available_blocks[user_id].append(block)

                # Inizializza slot occupati per questo giorno
                self.occupied_slots[user_id][day.strftime('%Y-%m-%d')] = []

    def _apply_leaves_to_blocks(self):
        """Rimuove blocchi che si sovrappongono con assenze"""

        if self.leaves_df.empty:
            return

        original_count = sum(len(blocks) for blocks in self.available_blocks.values())

        for user_id in self.available_blocks.keys():
            # Trova assenze per task di questa risorsa
            user_task_ids = self.tasks_df[self.tasks_df['user_id'] == user_id]['id'].tolist()
            user_leaves = self.leaves_df[self.leaves_df['task_id'].isin(user_task_ids)]

            if user_leaves.empty:
                continue

            # Filtra blocchi che non si sovrappongono con assenze
            filtered_blocks = []
            for block in self.available_blocks[user_id]:
                block_date = block.start_datetime.date()

                # Controlla sovrapposizione con assenze
                conflicts = False
                for _, leave in user_leaves.iterrows():
                    leave_start = leave['date_from'].date()
                    leave_end = leave['date_to'].date()

                    if leave_start <= block_date <= leave_end:
                        conflicts = True
                        break

                if not conflicts:
                    filtered_blocks.append(block)

            self.available_blocks[user_id] = filtered_blocks

        final_count = sum(len(blocks) for blocks in self.available_blocks.values())
        removed_count = original_count - final_count

        if removed_count > 0:
            logger.info(f"Rimossi {removed_count} blocchi a causa di assenze")

    def solve(self) -> bool:
        """Risolve la pianificazione usando l'algoritmo greedy con estensione dinamica dell'orizzonte"""

        start_time = datetime.now()
        logger.info("Avvio risoluzione greedy")

        max_allowed_days = 1825  # 5 anni massimo
        extension_attempts = 0
        max_attempts = 5

        try:
            while extension_attempts < max_attempts:
                # Esegui algoritmo greedy
                schedule = self._greedy_algorithm()

                # Calcola tasso di successo
                success_rate = len(schedule) / len(self.tasks_df) if len(self.tasks_df) > 0 else 0

                # Se abbiamo schedulato tutti i task o almeno l'80%, siamo soddisfatti
                if success_rate >= 0.8:
                    logger.info(f"Greedy riuscito con {success_rate:.1%} di task schedulati")
                    break

                # Se non abbiamo schedulato abbastanza task, estendi l'orizzonte
                if self.horizon_days >= max_allowed_days:
                    logger.warning(f"Raggiunto orizzonte massimo di {max_allowed_days} giorni")
                    break

                # Estendi orizzonte
                old_horizon = self.horizon_days
                self.horizon_days = min(int(self.horizon_days * 2), max_allowed_days)
                extension_attempts += 1

                logger.info(f"Estensione orizzonte #{extension_attempts}: {old_horizon} → {self.horizon_days} giorni (schedulati {len(schedule)}/{len(self.tasks_df)} task)")

                # Rigenera blocchi con nuovo orizzonte
                self._generate_available_blocks()
                self._apply_leaves_to_blocks()

                # Reset slot occupati per nuovo tentativo
                for user_id in self.occupied_slots:
                    for date in self.occupied_slots[user_id]:
                        self.occupied_slots[user_id][date] = []

            # Converti in formato compatibile
            self._convert_to_solution_format(schedule)

            # Calcola statistiche finali
            end_time = datetime.now()
            self.stats['execution_time'] = (end_time - start_time).total_seconds()
            self.stats['tasks_scheduled'] = len(schedule)
            self.stats['success_rate'] = len(schedule) / len(self.tasks_df)
            self.stats['horizon_extensions'] = extension_attempts

            logger.info(f"Greedy completato: {len(schedule)}/{len(self.tasks_df)} task schedulati in {self.stats['execution_time']:.2f}s (estensioni: {extension_attempts})")

            return len(schedule) > 0

        except Exception as e:
            logger.error(f"Errore in algoritmo greedy: {str(e)}")
            return False

    def _greedy_algorithm(self) -> Dict[int, List[ScheduledSlot]]:
        """Algoritmo greedy principale per la pianificazione"""

        schedule = {}

        # Per ogni task in ordine di priorità
        for _, task in self.tasks_df.iterrows():
            task_id = task['id']
            user_id = task['user_id']
            hours_needed = task['planned_hours']

            logger.debug(f"Schedulando task {task_id}: {hours_needed}h per user {user_id}")

            # Trova slot consecutivi per questo task
            assigned_slots = self._find_consecutive_slots(user_id, hours_needed, task_id)

            if assigned_slots:
                schedule[task_id] = assigned_slots
                self._mark_slots_occupied(user_id, assigned_slots)
                logger.debug(f"Task {task_id} schedulato: {len(assigned_slots)} slot")
            else:
                logger.warning(f"Impossibile schedulare task {task_id} ({hours_needed}h)")

        return schedule

    def _find_consecutive_slots(self, user_id: int, hours_needed: float, task_id: int) -> List[ScheduledSlot]:
        """Trova slot consecutivi ottimali per un task, anche attraverso più giorni"""

        if user_id not in self.available_blocks:
            return []

        hours_needed_int = int(math.ceil(hours_needed))

        # Per task molto lunghi, usa algoritmo multi-giorno
        if hours_needed_int > 40:  # Più di una settimana lavorativa
            return self._find_multi_day_slots(user_id, hours_needed_int, task_id)
        else:
            # Per task normali, usa algoritmo originale ottimizzato
            return self._find_single_day_slots(user_id, hours_needed_int, task_id)

    def _find_single_day_slots(self, user_id: int, hours_needed_int: int, task_id: int) -> List[ScheduledSlot]:
        """Trova slot consecutivi all'interno di singoli giorni"""

        # Ordina blocchi per data (priorità ai primi disponibili)
        blocks = sorted(self.available_blocks[user_id], key=lambda b: b.start_datetime)

        for block in blocks:
            if not block.can_fit(hours_needed_int):
                continue

            # Verifica disponibilità nel blocco
            date_str = block.start_datetime.strftime('%Y-%m-%d')
            occupied_hours = self.occupied_slots[user_id].get(date_str, [])

            # Trova slot consecutivi liberi nel blocco
            start_hour = block.start_datetime.hour
            end_hour = block.end_datetime.hour

            consecutive_slots = []
            current_hour = start_hour

            while current_hour < end_hour and len(consecutive_slots) < hours_needed_int:
                if current_hour not in occupied_hours:
                    slot = ScheduledSlot(
                        task_id=task_id,
                        user_id=user_id,
                        date=date_str,
                        hour=current_hour
                    )
                    consecutive_slots.append(slot)
                else:
                    # Reset se troviamo un'ora occupata
                    consecutive_slots = []

                current_hour += 1

            # Se abbiamo trovato abbastanza slot consecutivi
            if len(consecutive_slots) >= hours_needed_int:
                return consecutive_slots[:hours_needed_int]

        return []

    def _find_multi_day_slots(self, user_id: int, hours_needed_int: int, task_id: int) -> List[ScheduledSlot]:
        """Trova slot consecutivi attraverso più giorni per task molto lunghi"""

        logger.debug(f"Ricerca multi-giorno per task {task_id}: {hours_needed_int} ore")

        # Raggruppa blocchi per giorno e ordina cronologicamente
        blocks_by_date = {}
        for block in self.available_blocks[user_id]:
            date_str = block.start_datetime.strftime('%Y-%m-%d')
            if date_str not in blocks_by_date:
                blocks_by_date[date_str] = []
            blocks_by_date[date_str].append(block)

        # Ordina le date
        sorted_dates = sorted(blocks_by_date.keys())

        consecutive_slots = []

        # Scorri i giorni in ordine cronologico
        for date_str in sorted_dates:
            if len(consecutive_slots) >= hours_needed_int:
                break

            occupied_hours = self.occupied_slots[user_id].get(date_str, [])
            day_blocks = sorted(blocks_by_date[date_str], key=lambda b: b.start_datetime.hour)

            # Per ogni blocco del giorno
            for block in day_blocks:
                if len(consecutive_slots) >= hours_needed_int:
                    break

                start_hour = block.start_datetime.hour
                end_hour = block.end_datetime.hour

                # Aggiungi tutte le ore disponibili del blocco
                for hour in range(start_hour, end_hour):
                    if len(consecutive_slots) >= hours_needed_int:
                        break

                    if hour not in occupied_hours:
                        slot = ScheduledSlot(
                            task_id=task_id,
                            user_id=user_id,
                            date=date_str,
                            hour=hour
                        )
                        consecutive_slots.append(slot)

        # Verifica se abbiamo trovato abbastanza slot
        if len(consecutive_slots) >= hours_needed_int:
            logger.debug(f"Task {task_id}: trovati {len(consecutive_slots)} slot multi-giorno")
            return consecutive_slots[:hours_needed_int]
        else:
            logger.debug(f"Task {task_id}: trovati solo {len(consecutive_slots)}/{hours_needed_int} slot")
            return []

    def _mark_slots_occupied(self, user_id: int, slots: List[ScheduledSlot]):
        """Marca gli slot come occupati"""

        for slot in slots:
            if slot.date not in self.occupied_slots[user_id]:
                self.occupied_slots[user_id][slot.date] = []
            self.occupied_slots[user_id][slot.date].append(slot.hour)

    def _convert_to_solution_format(self, schedule: Dict[int, List[ScheduledSlot]]):
        """Converte il risultato greedy nel formato compatibile"""

        solution = {
            'tasks': {},
            'algorithm': 'greedy',
            'stats': self.stats,
            'horizon_days': self.horizon_days
        }

        for task_id, slots in schedule.items():
            # Converti task_id in int standard Python per JSON serialization
            task_id_str = str(int(task_id))
            solution['tasks'][task_id_str] = []

            for slot in slots:
                solution['tasks'][task_id_str].append({
                    'date': slot.date,
                    'hour': int(slot.hour)  # Assicura che anche hour sia int standard
                })

        self.solution = solution
        logger.info(f"Soluzione greedy creata: {len(solution['tasks'])} task pianificati")

    def get_solver_statistics(self):
        """Restituisce statistiche dell'algoritmo greedy"""

        return {
            'algorithm': 'greedy',
            'status': 'OPTIMAL' if self.stats['success_rate'] > 0.8 else 'FEASIBLE',
            'execution_time': self.stats['execution_time'],
            'tasks_scheduled': self.stats['tasks_scheduled'],
            'tasks_total': self.stats['tasks_total'],
            'success_rate': self.stats['success_rate'],
            'horizon_days': self.horizon_days,
            'horizon_extensions': self.stats.get('horizon_extensions', 0),
            'available_blocks_count': sum(len(blocks) for blocks in self.available_blocks.values())
        }


def should_use_greedy(tasks_df: pd.DataFrame) -> bool:
    """
    Determina se utilizzare l'algoritmo greedy basato sulla complessità del problema
    """

    num_tasks = len(tasks_df)
    total_hours = tasks_df['planned_hours'].sum()
    num_users = tasks_df['user_id'].nunique()

    # Usa greedy se:
    # - Molti task (>50)
    # - Molte ore totali (>1000)
    # - Molte risorse (>10)
    # - Task molto lunghi (media >100h)

    avg_hours = total_hours / num_tasks if num_tasks > 0 else 0

    use_greedy = (
        num_tasks > 50 or
        total_hours > 1000 or
        num_users > 10 or
        avg_hours > 100
    )

    logger.info(f"Decisione algoritmo: tasks={num_tasks}, hours={total_hours:.1f}, users={num_users}, avg_hours={avg_hours:.1f} → {'GREEDY' if use_greedy else 'ORTOOLS'}")

    return use_greedy
