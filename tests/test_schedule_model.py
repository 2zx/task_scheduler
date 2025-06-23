import unittest
import pandas as pd
from datetime import datetime, timedelta

from src.scheduler.model import SchedulingModel


class TestSchedulingModel(unittest.TestCase):
    """Test unitari per il modello di scheduling OrTools"""

    def setUp(self):
        """Crea dati di test per il modello"""
        # Crea tasks di test
        self.tasks_df = pd.DataFrame({
            'id': [1, 2],
            'name': ['Task 1', 'Task 2'],
            'user_id': [101, 102],
            'planned_hours': [8, 4]
        })

        # Crea slot di calendario di test
        calendar_data = []
        for task_id in [1, 2]:
            for day in range(5):  # Lunedì a Venerdì
                calendar_data.append({
                    'task_id': task_id,
                    'dayofweek': day,
                    'hour_from': 9,
                    'hour_to': 17
                })

        self.calendar_slots_df = pd.DataFrame(calendar_data)

        # Crea assenze di test
        today = datetime.now().date()
        self.leaves_df = pd.DataFrame({
            'task_id': [1, 2],
            'date_from': [today + timedelta(days=10), today + timedelta(days=15)],
            'date_to': [today + timedelta(days=10), today + timedelta(days=15)]
        })

    def test_model_initialization(self):
        """Testa la corretta inizializzazione del modello"""
        model = SchedulingModel(self.tasks_df, self.calendar_slots_df, self.leaves_df)
        self.assertIsNotNone(model)

        # Verifica che i dati siano stati preparati correttamente
        self.assertIsNotNone(model.available_slots)
        self.assertIsNotNone(model.unavailable_days)

        # Verifica che ci siano slot disponibili per i task
        self.assertIn(1, model.available_slots)
        self.assertIn(2, model.available_slots)

        # Verifica che ci siano giorni non disponibili per i task
        self.assertIn(1, model.unavailable_days)
        self.assertIn(2, model.unavailable_days)

    def test_model_build(self):
        """Testa la costruzione del modello OrTools CP-SAT"""
        model = SchedulingModel(self.tasks_df, self.calendar_slots_df, self.leaves_df)
        cp_model = model.build_model()

        # Verifica che il modello OrTools sia stato creato
        self.assertIsNotNone(cp_model)
        self.assertIsNotNone(model.model)
        self.assertIsNotNone(model.solver)
        self.assertIsNotNone(model.vars)

        # Verifica che ci siano variabili nel modello
        self.assertIn('x', model.vars)
        self.assertTrue(len(model.vars['x']) > 0)

    def test_solver_configuration(self):
        """Testa la configurazione del solver OrTools"""
        model = SchedulingModel(self.tasks_df, self.calendar_slots_df, self.leaves_df)
        model.build_model()

        # Verifica che i parametri del solver siano configurati
        self.assertIsNotNone(model.solver.parameters.max_time_in_seconds)
        self.assertIsNotNone(model.solver.parameters.num_search_workers)

    def test_solution_extraction(self):
        """Testa l'estrazione della soluzione"""
        model = SchedulingModel(self.tasks_df, self.calendar_slots_df, self.leaves_df)

        # Costruisci e risolvi il modello
        success = model.solve()

        if success:
            # Verifica che la soluzione sia stata estratta
            self.assertIsNotNone(model.solution)
            self.assertIn('tasks', model.solution)
            self.assertIn('status', model.solution)
            self.assertIn('solve_time', model.solution)

            # Verifica il DataFrame della soluzione
            solution_df = model.get_solution_dataframe()
            if solution_df is not None and not solution_df.empty:
                self.assertIn('task_id', solution_df.columns)
                self.assertIn('date', solution_df.columns)
                self.assertIn('hour', solution_df.columns)

    def test_solver_statistics(self):
        """Testa le statistiche del solver"""
        model = SchedulingModel(self.tasks_df, self.calendar_slots_df, self.leaves_df)
        model.build_model()

        # Ottieni le statistiche (anche senza risolvere)
        stats = model.get_solver_statistics()
        self.assertIsInstance(stats, dict)

        # Se risolviamo il modello, dovremmo avere più statistiche
        success = model.solve()
        if success:
            stats = model.get_solver_statistics()
            self.assertIn('status', stats)
            self.assertIn('wall_time', stats)
            self.assertIn('num_booleans', stats)
            self.assertIn('num_constraints', stats)

    def test_empty_solution_handling(self):
        """Testa la gestione di soluzioni vuote"""
        # Crea un modello con vincoli impossibili
        impossible_tasks_df = pd.DataFrame({
            'id': [1],
            'name': ['Impossible Task'],
            'user_id': [101],
            'planned_hours': [1000]  # Troppe ore per essere pianificate
        })

        model = SchedulingModel(impossible_tasks_df, self.calendar_slots_df, self.leaves_df)
        success = model.solve()

        # Il modello potrebbe non trovare una soluzione
        if not success:
            solution_df = model.get_solution_dataframe()
            # Dovrebbe restituire None o DataFrame vuoto
            self.assertTrue(solution_df is None or solution_df.empty)


if __name__ == '__main__':
    unittest.main()
