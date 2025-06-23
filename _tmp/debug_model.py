#!/usr/bin/env python3
"""
Debug del modello di scheduling per capire perché non schedula task
"""

import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Aggiungi il path del progetto
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.scheduler.model import SchedulingModel  # noqa: E402


def debug_model_creation():
    """Debug dettagliato del modello"""
    print("🔍 Debug del modello di scheduling...")

    # Crea dati di test semplici
    tasks_df = pd.DataFrame({
        'id': [1, 2],
        'name': ['Task A', 'Task B'],
        'user_id': [101, 102],
        'planned_hours': [2, 3]
    })

    # Calendari di lavoro
    calendar_data = []
    for task_id in [1, 2]:
        for day in range(5):  # Lunedì-Venerdì (0-4)
            calendar_data.append({
                'task_id': task_id,
                'dayofweek': day,
                'hour_from': 9,
                'hour_to': 17
            })

    calendar_slots_df = pd.DataFrame(calendar_data)

    # Nessuna assenza
    leaves_df = pd.DataFrame(columns=['task_id', 'date_from', 'date_to'])

    print(f"📊 Task: {len(tasks_df)}")
    print(f"📅 Slot calendario: {len(calendar_slots_df)}")
    print(f"🏖️ Assenze: {len(leaves_df)}")

    # Crea il modello
    model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)

    # Debug dei dati preparati
    print(f"\n🗓️ Giorni di pianificazione: {len(model.days)}")
    print(f"Primo giorno: {model.days[0]}")
    print(f"Ultimo giorno: {model.days[-1]}")

    print(f"\n📋 Slot disponibili per task:")
    for task_id, slots in model.available_slots.items():
        print(f"  Task {task_id}: {len(slots)} giorni della settimana")
        for day, hours in slots.items():
            print(f"    Giorno {day}: ore {hours}")

    print(f"\n🚫 Giorni non disponibili:")
    for task_id, days in model.unavailable_days.items():
        print(f"  Task {task_id}: {len(days)} giorni")

    # Costruisci il modello
    model.build_model()

    print(f"\n🔧 Variabili create: {len(model.vars['x'])}")

    # Debug delle variabili create
    if len(model.vars['x']) == 0:
        print("❌ PROBLEMA: Nessuna variabile creata!")

        # Verifica perché non vengono create variabili
        print("\n🔍 Debug creazione variabili:")
        for _, task in tasks_df.iterrows():
            task_id = task['id']
            print(f"\nTask {task_id}:")

            for d in model.days[:3]:  # Solo primi 3 giorni per debug
                weekday = d.weekday()
                print(f"  Data {d} (weekday {weekday}):")

                # Controlla se il giorno è disponibile
                if task_id in model.unavailable_days and d in model.unavailable_days[task_id]:
                    print(f"    ❌ Giorno non disponibile (assenza)")
                    continue

                # Controlla se il weekday è nel calendario
                if task_id not in model.available_slots:
                    print(f"    ❌ Task non in available_slots")
                    continue

                if weekday not in model.available_slots[task_id]:
                    print(f"    ❌ Weekday {weekday} non disponibile per task {task_id}")
                    print(f"    Weekdays disponibili: {list(model.available_slots[task_id].keys())}")
                    continue

                hours = model.available_slots[task_id][weekday]
                print(f"    ✅ Ore disponibili: {hours}")

                for h in hours[:2]:  # Solo prime 2 ore per debug
                    var_name = f"x_{task_id}_{d.strftime('%Y%m%d')}_{h}"
                    print(f"      Variabile: {var_name}")
    else:
        print("✅ Variabili create correttamente")

        # Mostra alcune variabili
        for i, (key, var) in enumerate(list(model.vars['x'].items())[:5]):
            task_id, date, hour = key
            print(f"  {i+1}. Task {task_id}, {date}, ora {hour}")

    # Risolvi il modello
    success = model.solve()

    if success:
        solution_df = model.get_solution_dataframe()
        print(f"\n✅ Soluzione trovata: {len(solution_df) if solution_df is not None else 0} slot")

        if solution_df is not None and not solution_df.empty:
            print(solution_df.head())
        else:
            print("❌ PROBLEMA: Soluzione vuota!")

            # Debug della soluzione
            print(f"\nSoluzione raw: {model.solution}")

    else:
        print("❌ Nessuna soluzione trovata")

    return success


if __name__ == "__main__":
    debug_model_creation()
