#!/usr/bin/env python3
"""
Esempio di utilizzo del Task Scheduler con OrTools

Questo script dimostra come utilizzare il sistema di scheduling
per pianificare task con dati di esempio.
"""

import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Aggiungi il path del progetto
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import dopo la modifica del path
from src.scheduler.model import SchedulingModel  # noqa: E402


def create_sample_data():
    """Crea dati di esempio per la dimostrazione"""

    # Task di esempio
    tasks_df = pd.DataFrame({
        'id': [1, 2, 3, 4],
        'name': [
            'Manutenzione Lavatrice A',
            'Controllo Qualità Lotto 001',
            'Pulizia Impianto B',
            'Calibrazione Sensori'
        ],
        'user_id': [101, 102, 101, 103],
        'planned_hours': [6, 4, 8, 3]
    })

    # Calendari di lavoro (Lunedì-Venerdì, 8-17)
    calendar_data = []
    for task_id in tasks_df['id']:
        for day in range(5):  # 0=Lunedì, 4=Venerdì
            calendar_data.append({
                'task_id': task_id,
                'dayofweek': day,
                'hour_from': 8,
                'hour_to': 17
            })

    calendar_slots_df = pd.DataFrame(calendar_data)

    # Assenze (alcuni giorni di ferie)
    today = datetime.now().date()
    leaves_df = pd.DataFrame({
        'task_id': [101, 102],
        'date_from': [
            today + timedelta(days=5),
            today + timedelta(days=10)
        ],
        'date_to': [
            today + timedelta(days=5),
            today + timedelta(days=11)
        ]
    })

    return tasks_df, calendar_slots_df, leaves_df


def main():
    """Funzione principale di esempio"""
    print("🚀 Task Scheduler con OrTools - Esempio di Utilizzo")
    print("=" * 60)

    # Crea dati di esempio
    print("\n📊 Creazione dati di esempio...")
    tasks_df, calendar_slots_df, leaves_df = create_sample_data()

    print(f"✅ Creati {len(tasks_df)} task da pianificare")
    print(f"✅ Creati {len(calendar_slots_df)} slot di calendario")
    print(f"✅ Create {len(leaves_df)} assenze")

    # Mostra i task
    print("\n📋 Task da pianificare:")
    for _, task in tasks_df.iterrows():
        print(f"  • {task['name']} (ID: {task['id']}) - {task['planned_hours']} ore - Utente: {task['user_id']}")

    # Crea e configura il modello
    print("\n🔧 Creazione modello OrTools...")
    model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)

    # Risolvi il modello
    print("\n⚡ Risoluzione del modello di ottimizzazione...")
    success = model.solve()

    if success:
        print("✅ Soluzione trovata!")

        # Ottieni statistiche del solver
        stats = model.get_solver_statistics()
        print(f"\n📈 Statistiche del solver:")
        print(f"  • Status: {stats.get('status', 'N/A')}")
        print(f"  • Tempo di risoluzione: {stats.get('wall_time', 0):.2f} secondi")
        print(f"  • Valore obiettivo: {stats.get('objective_value', 'N/A')}")
        print(f"  • Variabili booleane: {stats.get('num_booleans', 'N/A')}")
        print(f"  • Vincoli: {stats.get('num_constraints', 'N/A')}")

        # Mostra la pianificazione
        solution_df = model.get_solution_dataframe()
        if solution_df is not None and not solution_df.empty:
            print(f"\n📅 Pianificazione generata ({len(solution_df)} slot):")
            print("-" * 80)

            # Raggruppa per task
            for task_id in solution_df['task_id'].unique():
                task_slots = solution_df[solution_df['task_id'] == task_id]
                task_name = task_slots.iloc[0]['task_name']
                user_id = task_slots.iloc[0]['user_id']

                print(f"\n🔧 {task_name} (Utente: {user_id})")

                # Raggruppa per data
                for date in sorted(task_slots['date'].unique()):
                    date_slots = task_slots[task_slots['date'] == date]
                    hours = sorted(date_slots['hour'].tolist())
                    hours_str = ', '.join([f"{h}:00" for h in hours])
                    print(f"  📆 {date}: {hours_str} ({len(hours)} ore)")

            print("\n" + "=" * 60)
            print("✅ Pianificazione completata con successo!")

            # Genera visualizzazioni grafiche
            try:
                from src.scheduler.visualization import ScheduleVisualizer
                print("\n🎨 Generazione grafici di visualizzazione...")

                visualizer = ScheduleVisualizer(solution_df, tasks_df, output_dir="../data")
                charts = visualizer.generate_all_charts()

                if charts:
                    print("📊 Grafici generati:")
                    for chart_type, path in charts.items():
                        if path:
                            print(f"  • {chart_type}: {path}")

                    # Crea report HTML
                    report_path = visualizer.create_summary_report(charts)
                    print(f"\n📋 Report HTML completo: {report_path}")
                    print("💡 Apri il file HTML nel browser per visualizzare tutti i grafici!")

            except ImportError as e:
                print(f"⚠️  Modulo di visualizzazione non disponibile: {e}")
            except Exception as e:
                print(f"❌ Errore nella generazione dei grafici: {e}")

        else:
            print("⚠️  Nessuna pianificazione generata")

    else:
        print("❌ Impossibile trovare una soluzione valida")
        print("💡 Suggerimenti:")
        print("  • Verifica che ci siano abbastanza slot disponibili")
        print("  • Controlla i vincoli di calendario e assenze")
        print("  • Riduci le ore pianificate per i task")


if __name__ == "__main__":
    main()
