#!/usr/bin/env python3
"""
Debug con dati reali dal database per capire il problema
"""

import pandas as pd
import sys
import os

# Aggiungi il path del progetto
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.fetch import get_tasks, get_calendar_slots, get_leaves  # noqa: E402
from src.scheduler.model import SchedulingModel  # noqa: E402
from src.config import setup_logging  # noqa: E402


def debug_real_data():
    """Debug con dati reali dal database"""
    print("🔍 Debug con dati reali dal database...")

    # Configura logging
    setup_logging()

    # Prendi solo i primi 2 task per semplificare il debug
    print("\n📊 Recupero dati dal database...")
    tasks_df = get_tasks()

    if tasks_df.empty:
        print("❌ Nessun task trovato!")
        return False

    # Prendi solo i primi 2 task
    tasks_df = tasks_df.head(2)
    task_ids = tasks_df['id'].tolist()

    print(f"✅ Task recuperati: {task_ids}")
    print(tasks_df[['id', 'name', 'user_id', 'planned_hours']])

    # Recupera calendari
    calendar_slots_df = get_calendar_slots(task_ids)
    print(f"\n📅 Slot calendario recuperati: {len(calendar_slots_df)}")

    if calendar_slots_df.empty:
        print("❌ PROBLEMA: Nessun slot di calendario trovato!")
        print("Questo spiega perché non vengono create variabili.")
        return False

    print("Prime 10 righe del calendario:")
    print(calendar_slots_df.head(10))

    # Verifica corrispondenza task_id
    calendar_task_ids = set(calendar_slots_df['task_id'].unique())
    tasks_task_ids = set(task_ids)

    print(f"\n🔍 Analisi corrispondenza task_id:")
    print(f"Task IDs nei task: {tasks_task_ids}")
    print(f"Task IDs nel calendario: {calendar_task_ids}")
    print(f"Intersezione: {tasks_task_ids.intersection(calendar_task_ids)}")
    print(f"Task senza calendario: {tasks_task_ids - calendar_task_ids}")
    print(f"Calendario senza task: {calendar_task_ids - tasks_task_ids}")

    # Recupera assenze
    leaves_df = get_leaves(task_ids)
    print(f"\n🏖️ Assenze recuperate: {len(leaves_df)}")

    # Crea il modello
    print(f"\n🔧 Creazione modello...")
    model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)

    # Analizza gli slot disponibili
    print(f"\n📋 Analisi slot disponibili:")
    print(f"Task con slot disponibili: {len(model.available_slots)}")

    for task_id, slots in model.available_slots.items():
        print(f"  Task {task_id}:")
        for day, hours in slots.items():
            print(f"    Giorno {day}: {len(hours)} ore ({min(hours)}-{max(hours)})")

    # Analisi giorni non disponibili
    print(f"\n🚫 Analisi giorni non disponibili:")
    for task_id, days in model.unavailable_days.items():
        print(f"  Task {task_id}: {len(days)} giorni non disponibili")
        if len(days) > 0:
            print(f"    Primi 5: {days[:5]}")

    # Costruisci il modello
    print(f"\n🏗️ Costruzione modello...")
    model.build_model()

    # Risolvi
    print(f"\n⚡ Risoluzione...")
    success = model.solve()

    if success:
        solution_df = model.get_solution_dataframe()
        print(f"✅ Soluzione trovata: {len(solution_df) if solution_df is not None else 0} slot")
    else:
        print("❌ Nessuna soluzione trovata")

    return success


if __name__ == "__main__":
    debug_real_data()
