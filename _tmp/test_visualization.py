#!/usr/bin/env python3
"""
Test rapido per verificare la visualizzazione
"""

import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Aggiungi il path del progetto
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.scheduler.model import SchedulingModel  # noqa: E402


def test_visualization():
    """Test della visualizzazione con dati semplici"""
    print("🧪 Test della visualizzazione...")

    # Crea dati di test molto semplici
    tasks_df = pd.DataFrame({
        'id': [1, 2],
        'name': ['Task A', 'Task B'],
        'user_id': [101, 102],
        'planned_hours': [2, 3]
    })

    # Calendari di lavoro semplici
    calendar_data = []
    for task_id in [1, 2]:
        for day in range(2):  # Solo 2 giorni
            calendar_data.append({
                'task_id': task_id,
                'dayofweek': day,
                'hour_from': 9,
                'hour_to': 12
            })

    calendar_slots_df = pd.DataFrame(calendar_data)

    # Nessuna assenza
    leaves_df = pd.DataFrame(columns=['task_id', 'date_from', 'date_to'])

    print("✅ Dati di test creati")

    # Crea e risolvi il modello
    model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)
    success = model.solve()

    if success:
        print("✅ Modello risolto con successo")

        # Ottieni il DataFrame della soluzione
        solution_df = model.get_solution_dataframe()

        if solution_df is not None and not solution_df.empty:
            print("✅ DataFrame della soluzione creato")
            print(f"Colonne: {list(solution_df.columns)}")
            print(f"Righe: {len(solution_df)}")

            # Test della visualizzazione
            try:
                from src.scheduler.visualization import ScheduleVisualizer

                visualizer = ScheduleVisualizer(solution_df, tasks_df, output_dir="../data")
                charts = visualizer.generate_all_charts()

                print("✅ Grafici generati con successo!")
                for chart_type, path in charts.items():
                    if path:
                        print(f"  • {chart_type}: {path}")

                return True

            except Exception as e:
                print(f"❌ Errore nella visualizzazione: {e}")
                return False
        else:
            print("❌ DataFrame della soluzione vuoto")
            return False
    else:
        print("❌ Modello non risolto")
        return False


if __name__ == "__main__":
    success = test_visualization()
    if success:
        print("\n🎉 Test completato con successo!")
    else:
        print("\n💥 Test fallito!")
