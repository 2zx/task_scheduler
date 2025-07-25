import logging
import pandas as pd
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from dataclasses import dataclass

from ..config import SCHEDULER_CONFIG

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

        # Logging diagnostico dettagliato
        total_blocks = sum(len(blocks) for blocks in self.available_blocks.values())
        logger.info(f"Preparazione completata: {total_blocks} blocchi disponibili")

        # Log dettagliato per ogni utente
        for user_id in self.available_blocks:
            user_blocks = len(self.available_blocks[user_id])
            user_tasks = len(self.tasks_df[self.tasks_df['user_id'] == user_id])
            user_hours = self.tasks_df[self.tasks_df['user_id'] == user_id]['remaining_hours'].sum()
            logger.debug(f"User {user_id}: {user_blocks} blocchi, {user_tasks} task, {user_hours:.1f}h totali")

    def _sort_tasks_optimally(self):
        """Ordina i task per massimizzare l'efficacia dell'algoritmo greedy"""

        # Gestione sicura dei nuovi parametri di gerarchia (backward compatibility)
        if 'hierarchy_level' not in self.tasks_df.columns:
            self.tasks_df['hierarchy_level'] = 0
        if 'is_leaf_task' not in self.tasks_df.columns:
            self.tasks_df['is_leaf_task'] = True
        if 'parent_id' not in self.tasks_df.columns:
            self.tasks_df['parent_id'] = None

        # Ordinamento multi-criterio per ottimizzare greedy con gerarchia
        # 1. priority_score (DESC) - priorità principale
        # 2. hierarchy_level (ASC) - figli prima dei padri (0=foglia, 1=padre di foglia, etc.)
        # 3. is_leaf_task (DESC) - task foglia prima di quelli con figli
        # 4. remaining_hours (DESC) - task lunghi prima per ottimizzare allocazione
        # 5. user_id (ASC) - raggruppa per utente per efficienza
        # 6. id (ASC) - determinismo

        sort_criteria = ['priority_score', 'hierarchy_level', 'is_leaf_task', 'remaining_hours', 'user_id', 'id']
        sort_ascending = [False, True, False, False, True, True]

        self.tasks_df = self.tasks_df.sort_values(sort_criteria, ascending=sort_ascending)

        # Logging diagnostico
        priority_range = f"{self.tasks_df['priority_score'].min():.1f}-{self.tasks_df['priority_score'].max():.1f}"
        hierarchy_range = f"{self.tasks_df['hierarchy_level'].min()}-{self.tasks_df['hierarchy_level'].max()}"
        leaf_count = self.tasks_df['is_leaf_task'].sum()

        logger.info(f"Task ordinati per greedy con gerarchia:")
        logger.info(f"  - Priorità: {priority_range}")
        logger.info(f"  - Livelli gerarchia: {hierarchy_range}")
        logger.info(f"  - Task foglia: {leaf_count}/{len(self.tasks_df)}")

    def _calculate_optimal_horizon(self):
        """Calcola orizzonte ottimale basato sul carico di lavoro per risorsa"""

        max_horizon_needed = self.horizon_days

        # Calcola orizzonte per ogni risorsa
        for user_id in self.tasks_df['user_id'].unique():
            user_tasks = self.tasks_df[self.tasks_df['user_id'] == user_id]
            total_hours = user_tasks['remaining_hours'].sum()

            # Stima giorni necessari (8 ore lavorative/giorno, 5 giorni/settimana)
            working_hours_per_week = 40
            weeks_needed = math.ceil(total_hours / working_hours_per_week)
            days_needed = weeks_needed * 7  # Include weekend

            # Aggiungi buffer del 50% per task lunghi
            days_with_buffer = int(days_needed * 1.5)
            max_horizon_needed = max(max_horizon_needed, days_with_buffer)

        # Rimuovi limite fisso - permetti estensione fino a 5 anni se necessario
        max_allowed_days = SCHEDULER_CONFIG['max_horizon_days']
        self.horizon_days = min(max_horizon_needed, max_allowed_days)

        logger.info(f"Orizzonte ottimizzato: {self.horizon_days} giorni (max consentito: {max_allowed_days})")

    def _generate_available_blocks(self):
        """Genera blocchi di tempo disponibili per ogni risorsa con logica migliorata"""

        self.available_blocks = {}
        self.occupied_slots = {}

        # Genera orizzonte temporale - inizia dal primo giorno utile (domani in UTC)
        first_day = get_next_business_date()
        days = [first_day + timedelta(days=i) for i in range(self.horizon_days)]

        logger.info(f"Pianificazione dal {first_day} per {self.horizon_days} giorni (UTC)")

        # Per ogni risorsa
        for user_id in self.tasks_df['user_id'].unique():
            self.available_blocks[user_id] = []
            self.occupied_slots[user_id] = {}

            # CORREZIONE: Trova TUTTI gli slot di calendario per questa risorsa
            # Non filtrare per task_id specifici, ma per tutti i task dell'utente
            user_task_ids = self.tasks_df[self.tasks_df['user_id'] == user_id]['id'].tolist()

            # Prendi tutti gli slot unici per questo utente (senza duplicati)
            user_calendar = self.calendar_slots_df[
                self.calendar_slots_df['task_id'].isin(user_task_ids)
            ].groupby(['dayofweek', 'hour_from', 'hour_to']).first().reset_index()

            if user_calendar.empty:
                logger.warning(f"Nessun calendario trovato per user {user_id} con {len(user_task_ids)} task")
                continue

            logger.debug(f"User {user_id}: {len(user_calendar)} slot di calendario unici (da {len(user_task_ids)} task)")

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

                # Inizializza slot occupati per questo giorno (usa set per evitare duplicati)
                self.occupied_slots[user_id][day.strftime('%Y-%m-%d')] = set()

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

        max_allowed_days = SCHEDULER_CONFIG['max_horizon_days']
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

                # Reset completo slot occupati per nuovo tentativo (include nuove date)
                # Nota: _generate_available_blocks() già reinizializza self.occupied_slots
                logger.debug("Reset completo slot occupati per estensione orizzonte")

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
            hours_needed = task['remaining_hours']

            logger.debug(f"Schedulando task {task_id}: {hours_needed}h remaining_hours per user {user_id}")

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
        """Trova slot ottimali per un task con algoritmo migliorato per evitare sovrapposizioni"""

        if user_id not in self.available_blocks:
            logger.warning(f"Task {task_id}: User {user_id} non ha blocchi disponibili")
            return []

        hours_needed_int = int(math.ceil(hours_needed))

        # Strategia migliorata con priorità alla sequenzialità:
        # 1. Algoritmo consecutivo rigoroso (single-day)
        # 2. Algoritmo consecutivo multi-giorno
        # 3. Algoritmo flessibile LIMITATO (solo se necessario)
        # 4. Distribuzione multi-settimana (ultima risorsa)

        # Livello 1: Algoritmo consecutivo rigoroso per singolo giorno
        slots = self._find_single_day_slots(user_id, hours_needed_int, task_id)
        if slots:
            logger.debug(f"Task {task_id}: Trovato con algoritmo consecutivo single-day")
            return slots

        # Livello 2: Algoritmo consecutivo multi-giorno
        slots = self._find_multi_day_slots(user_id, hours_needed_int, task_id)
        if slots:
            logger.debug(f"Task {task_id}: Trovato con algoritmo consecutivo multi-day")
            return slots

        # Livello 3: Algoritmo flessibile LIMITATO (solo per task > 8 ore)
        if hours_needed_int > 8:
            slots = self._find_flexible_slots_improved(user_id, hours_needed_int, task_id)
            if slots:
                logger.debug(f"Task {task_id}: Trovato con algoritmo flessibile migliorato")
                return slots

        # Livello 4: Distribuzione multi-settimana (ultima risorsa per task molto lunghi)
        if hours_needed_int > 16:
            slots = self._find_distributed_slots(user_id, hours_needed_int, task_id)
            if slots:
                logger.debug(f"Task {task_id}: Trovato con algoritmo distribuito")
                return slots

        # Debug: Perché il task è fallito?
        self._debug_failed_task(user_id, hours_needed_int, task_id)
        return []

    def _find_flexible_slots_improved(self, user_id: int, hours_needed_int: int, task_id: int) -> List[ScheduledSlot]:
        """Algoritmo flessibile migliorato che prioritizza la consecutività e evita sovrapposizioni"""

        logger.debug(f"Ricerca flessibile migliorata per task {task_id}: {hours_needed_int} ore")

        # Strategia migliorata:
        # 1. Cerca prima blocchi consecutivi per giorno
        # 2. Se non trova, cerca blocchi con gap minimi
        # 3. Limita la frammentazione massima

        # Raggruppa blocchi per giorno
        blocks_by_date = {}
        for block in self.available_blocks[user_id]:
            date_str = block.start_datetime.strftime('%Y-%m-%d')
            if date_str not in blocks_by_date:
                blocks_by_date[date_str] = []
            blocks_by_date[date_str].append(block)

        # Ordina le date cronologicamente
        sorted_dates = sorted(blocks_by_date.keys())

        # Prova prima con blocchi consecutivi per giorno
        for date_str in sorted_dates:
            day_slots = self._find_best_day_slots(user_id, date_str, hours_needed_int, task_id)
            if len(day_slots) >= hours_needed_int:
                logger.debug(f"Task {task_id}: trovati {len(day_slots)} slot consecutivi in {date_str}")
                return day_slots[:hours_needed_int]

        # Se non trova slot consecutivi in un singolo giorno, prova multi-giorno con gap limitati
        selected_slots = []
        max_gap_hours = 2  # Massimo 2 ore di gap permesse per giorno

        for date_str in sorted_dates:
            if len(selected_slots) >= hours_needed_int:
                break

            day_slots = self._find_flexible_day_slots(user_id, date_str, max_gap_hours, task_id)

            # Prendi solo quello che serve
            remaining_needed = hours_needed_int - len(selected_slots)
            selected_slots.extend(day_slots[:remaining_needed])

        if len(selected_slots) >= hours_needed_int:
            logger.debug(f"Task {task_id}: trovati {len(selected_slots)} slot flessibili su {len(set(s.date for s in selected_slots))} giorni")
            return selected_slots[:hours_needed_int]

        return []

    def _find_best_day_slots(self, user_id: int, date_str: str, hours_needed: int, task_id: int) -> List[ScheduledSlot]:
        """Trova i migliori slot consecutivi in un singolo giorno"""

        occupied_hours = self.occupied_slots[user_id].get(date_str, set())
        day_blocks = [b for b in self.available_blocks[user_id]
                     if b.start_datetime.strftime('%Y-%m-%d') == date_str]

        if not day_blocks:
            return []

        # Ordina blocchi per ora di inizio
        day_blocks = sorted(day_blocks, key=lambda b: b.start_datetime.hour)

        best_consecutive = []

        for block in day_blocks:
            start_hour = block.start_datetime.hour
            end_hour = block.end_datetime.hour

            consecutive_slots = []

            for hour in range(start_hour, end_hour):
                if hour not in occupied_hours:
                    slot = ScheduledSlot(
                        task_id=task_id,
                        user_id=user_id,
                        date=date_str,
                        hour=hour
                    )
                    consecutive_slots.append(slot)
                else:
                    # Se abbiamo trovato un blocco consecutivo migliore, salvalo
                    if len(consecutive_slots) > len(best_consecutive):
                        best_consecutive = consecutive_slots.copy()
                    consecutive_slots = []

            # Controlla l'ultimo blocco consecutivo
            if len(consecutive_slots) > len(best_consecutive):
                best_consecutive = consecutive_slots

        return best_consecutive

    def _find_flexible_day_slots(self, user_id: int, date_str: str, max_gap_hours: int, task_id: int) -> List[ScheduledSlot]:
        """Trova slot in un giorno permettendo gap limitati"""

        occupied_hours = self.occupied_slots[user_id].get(date_str, set())
        day_blocks = [b for b in self.available_blocks[user_id]
                     if b.start_datetime.strftime('%Y-%m-%d') == date_str]

        if not day_blocks:
            return []

        # Raccogli tutti gli slot liberi del giorno
        free_slots = []
        for block in day_blocks:
            start_hour = block.start_datetime.hour
            end_hour = block.end_datetime.hour

            for hour in range(start_hour, end_hour):
                if hour not in occupied_hours:
                    slot = ScheduledSlot(
                        task_id=task_id,
                        user_id=user_id,
                        date=date_str,
                        hour=hour
                    )
                    free_slots.append(slot)

        # Ordina per ora
        free_slots = sorted(free_slots, key=lambda s: s.hour)

        # Verifica che i gap non siano troppo grandi
        if len(free_slots) <= 1:
            return free_slots

        # Controlla gap tra slot consecutivi
        valid_slots = [free_slots[0]]  # Il primo slot è sempre valido

        for i in range(1, len(free_slots)):
            current_hour = free_slots[i].hour
            prev_hour = free_slots[i-1].hour
            gap = current_hour - prev_hour - 1

            if gap <= max_gap_hours:
                valid_slots.append(free_slots[i])
            else:
                # Gap troppo grande, interrompi la sequenza
                break

        return valid_slots

    def _find_flexible_slots(self, user_id: int, hours_needed_int: int, task_id: int) -> List[ScheduledSlot]:
        """Algoritmo flessibile legacy (mantenuto per compatibilità)"""

        logger.debug(f"Ricerca flessibile legacy per task {task_id}: {hours_needed_int} ore")

        # Raccogli tutti gli slot liberi disponibili
        all_free_slots = []

        # Ordina blocchi per data
        blocks = sorted(self.available_blocks[user_id], key=lambda b: b.start_datetime)

        for block in blocks:
            date_str = block.start_datetime.strftime('%Y-%m-%d')
            occupied_hours = self.occupied_slots[user_id].get(date_str, set())

            start_hour = block.start_datetime.hour
            end_hour = block.end_datetime.hour

            # Aggiungi tutti gli slot liberi di questo blocco
            for hour in range(start_hour, end_hour):
                if hour not in occupied_hours:
                    slot = ScheduledSlot(
                        task_id=task_id,
                        user_id=user_id,
                        date=date_str,
                        hour=hour
                    )
                    all_free_slots.append(slot)

        # Se abbiamo abbastanza slot liberi, prendili
        if len(all_free_slots) >= hours_needed_int:
            # Raggruppa per giorno per ottimizzare la distribuzione
            slots_by_date = {}
            for slot in all_free_slots:
                if slot.date not in slots_by_date:
                    slots_by_date[slot.date] = []
                slots_by_date[slot.date].append(slot)

            # Prova a concentrare il task in pochi giorni
            selected_slots = []
            for date in sorted(slots_by_date.keys()):
                day_slots = sorted(slots_by_date[date], key=lambda s: s.hour)

                # Prendi tutti gli slot del giorno fino al limite necessario
                for slot in day_slots:
                    if len(selected_slots) >= hours_needed_int:
                        break
                    selected_slots.append(slot)

                if len(selected_slots) >= hours_needed_int:
                    break

            if len(selected_slots) >= hours_needed_int:
                logger.debug(f"Task {task_id}: trovati {len(selected_slots)} slot flessibili legacy")
                return selected_slots[:hours_needed_int]

        return []

    def _find_distributed_slots(self, user_id: int, hours_needed_int: int, task_id: int) -> List[ScheduledSlot]:
        """Algoritmo distribuito per task lunghi - distribuisce su più settimane"""

        logger.debug(f"Ricerca distribuita per task {task_id}: {hours_needed_int} ore")

        # Raccogli slot liberi raggruppati per settimana
        slots_by_week = {}

        blocks = sorted(self.available_blocks[user_id], key=lambda b: b.start_datetime)

        for block in blocks:
            date_str = block.start_datetime.strftime('%Y-%m-%d')
            date_obj = block.start_datetime.date()

            # Calcola numero settimana
            week_number = date_obj.isocalendar()[1]
            year = date_obj.year
            week_key = f"{year}-W{week_number:02d}"

            if week_key not in slots_by_week:
                slots_by_week[week_key] = []

            occupied_hours = self.occupied_slots[user_id].get(date_str, set())

            start_hour = block.start_datetime.hour
            end_hour = block.end_datetime.hour

            # Aggiungi slot liberi di questo blocco
            for hour in range(start_hour, end_hour):
                if hour not in occupied_hours:
                    slot = ScheduledSlot(
                        task_id=task_id,
                        user_id=user_id,
                        date=date_str,
                        hour=hour
                    )
                    slots_by_week[week_key].append(slot)

        # Distribuisci il task su più settimane (max 8 ore per settimana)
        selected_slots = []
        max_hours_per_week = 8

        for week_key in sorted(slots_by_week.keys()):
            if len(selected_slots) >= hours_needed_int:
                break

            week_slots = sorted(slots_by_week[week_key], key=lambda s: (s.date, s.hour))
            hours_to_take = min(max_hours_per_week, hours_needed_int - len(selected_slots))

            selected_slots.extend(week_slots[:hours_to_take])

        if len(selected_slots) >= hours_needed_int:
            logger.debug(f"Task {task_id}: trovati {len(selected_slots)} slot distribuiti su {len(set(s.date for s in selected_slots))} giorni")
            return selected_slots[:hours_needed_int]

        return []

    def _debug_failed_task(self, user_id: int, hours_needed_int: int, task_id: int):
        """Debug dettagliato per task falliti"""

        if user_id not in self.available_blocks:
            logger.warning(f"Task {task_id} FALLITO: User {user_id} non ha blocchi disponibili")
            return

        # Calcola statistiche disponibilità
        total_blocks = len(self.available_blocks[user_id])
        total_hours_available = sum(block.duration_hours for block in self.available_blocks[user_id])

        # Calcola ore occupate
        total_occupied_hours = sum(len(hours) for hours in self.occupied_slots[user_id].values())

        # Calcola ore libere teoriche
        free_hours_theoretical = total_hours_available - total_occupied_hours

        logger.warning(f"Task {task_id} ({hours_needed_int}h) FALLITO per user {user_id}:")
        logger.warning(f"  - Blocchi disponibili: {total_blocks}")
        logger.warning(f"  - Ore totali disponibili: {total_hours_available:.1f}")
        logger.warning(f"  - Ore occupate: {total_occupied_hours}")
        logger.warning(f"  - Ore libere teoriche: {free_hours_theoretical:.1f}")

        if free_hours_theoretical >= hours_needed_int:
            logger.warning(f"  - PROBLEMA: Ore sufficienti ma algoritmo non trova slot consecutivi!")
            logger.warning(f"  - SUGGERIMENTO: Problema di frammentazione o gap nei calendar_slots")

    def _find_single_day_slots(self, user_id: int, hours_needed_int: int, task_id: int) -> List[ScheduledSlot]:
        """Trova slot consecutivi all'interno di singoli giorni con algoritmo migliorato"""

        # Ordina blocchi per data (priorità ai primi disponibili)
        blocks = sorted(self.available_blocks[user_id], key=lambda b: b.start_datetime)

        for block in blocks:
            if not block.can_fit(hours_needed_int):
                continue

            # Verifica disponibilità nel blocco
            date_str = block.start_datetime.strftime('%Y-%m-%d')
            occupied_hours = self.occupied_slots[user_id].get(date_str, set())

            # Trova slot consecutivi liberi nel blocco
            start_hour = block.start_datetime.hour
            end_hour = block.end_datetime.hour

            consecutive_slots = []
            current_hour = start_hour
            best_consecutive = []

            while current_hour < end_hour:
                if current_hour not in occupied_hours:
                    slot = ScheduledSlot(
                        task_id=task_id,
                        user_id=user_id,
                        date=date_str,
                        hour=current_hour
                    )
                    consecutive_slots.append(slot)
                else:
                    # Salva il miglior blocco consecutivo trovato finora
                    if len(consecutive_slots) > len(best_consecutive):
                        best_consecutive = consecutive_slots.copy()
                    consecutive_slots = []

                current_hour += 1

            # Controlla l'ultimo blocco consecutivo
            if len(consecutive_slots) > len(best_consecutive):
                best_consecutive = consecutive_slots

            # Se abbiamo trovato abbastanza slot consecutivi
            if len(best_consecutive) >= hours_needed_int:
                return best_consecutive[:hours_needed_int]

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

            occupied_hours = self.occupied_slots[user_id].get(date_str, set())
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
        """Marca gli slot come occupati usando set per evitare duplicati"""

        for slot in slots:
            if slot.date not in self.occupied_slots[user_id]:
                self.occupied_slots[user_id][slot.date] = set()
            self.occupied_slots[user_id][slot.date].add(slot.hour)

        # Log dettagliato per debugging
        if slots:
            date_str = slots[0].date
            occupied_count = len(self.occupied_slots[user_id][date_str])
            logger.debug(f"Task {slots[0].task_id}: marcati {len(slots)} slot, totale occupati in {date_str}: {occupied_count}")

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

        # Validazione finale: verifica che non ci siano sovrapposizioni
        overlaps_found = self._validate_no_overlaps(schedule)
        if overlaps_found:
            logger.error(f"ATTENZIONE: Trovate {overlaps_found} sovrapposizioni nella soluzione!")
            self.stats['overlaps_detected'] = overlaps_found
        else:
            logger.info("Validazione completata: nessuna sovrapposizione rilevata")
            self.stats['overlaps_detected'] = 0

        self.solution = solution
        logger.info(f"Soluzione greedy creata: {len(solution['tasks'])} task pianificati")

    def _validate_no_overlaps(self, schedule: Dict[int, List[ScheduledSlot]]) -> int:
        """Valida che non ci siano sovrapposizioni nella soluzione finale"""

        # Raggruppa tutti gli slot per utente e slot temporale
        user_slots = {}
        overlaps_count = 0

        for task_id, slots in schedule.items():
            for slot in slots:
                user_id = slot.user_id
                time_key = f"{slot.date}_{slot.hour}"

                if user_id not in user_slots:
                    user_slots[user_id] = {}

                if time_key in user_slots[user_id]:
                    # Sovrapposizione trovata!
                    existing_task = user_slots[user_id][time_key]
                    logger.error(
                        f"SOVRAPPOSIZIONE: User {user_id}, {slot.date} ore {slot.hour} - "
                        f"Task {existing_task} vs Task {task_id}"
                    )
                    overlaps_count += 1
                else:
                    user_slots[user_id][time_key] = task_id

        return overlaps_count

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
    total_hours = tasks_df['remaining_hours'].sum()
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

    logger.info(f"Decisione algoritmo: tasks={num_tasks}, remaining_hours={total_hours:.1f}, "
                f"users={num_users}, avg_hours={avg_hours:.1f} → "
                f"{'GREEDY' if use_greedy else 'ORTOOLS'}")

    return use_greedy
