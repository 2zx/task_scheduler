import unittest
import pandas as pd
from datetime import datetime, timedelta

from src.scheduler.model import SchedulingModel


class TestSchedulingModel(unittest.TestCase):
    """Test unitari per il modello di scheduling"""

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
        """Testa la costruzione del modello SCIP"""
        model = SchedulingModel(self.tasks_df, self.calendar_slots_df, self.leaves_df)
        scip_model = model.build_model()

        # Verifica che il modello SCIP sia stato creato
        self.assertIsNotNone(scip_model)
        self.assertIsNotNone(model.vars)

        # Verifica che ci siano variabili nel modello
        self.assertIn('x', model.vars)
        self.assertTrue(len(model.vars['x']) > 0)

if __name__ == '__main__':
    unittest.main()