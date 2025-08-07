#!/usr/bin/env python3
"""
Script di esempio per testare il sistema di profilazione
"""
import sys
import os
import logging

# Aggiungi il path del progetto
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.scheduler.profiler import SchedulingProfiler
from src.scheduler.model import SchedulingModel
from tests.realistic_data_generator import generate_scenario

# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Esempio di utilizzo del profiler"""

    print("🔍 Test del Sistema di Profilazione Centralizzato")
    print("=" * 60)

    # Genera scenario di test
    print("📊 Generazione scenario di test...")
    tasks_df, calendar_slots_df, leaves_df = generate_scenario(
        'production', num_tasks=50, num_resources=5
    )

    # Esegui scheduling
    print("⚙️ Esecuzione scheduling...")
    model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)
    success = model.solve()

    if not success:
        print("❌ Scheduling fallito!")
        return

    # Ottieni soluzione e statistiche
    solution_df = model.get_solution_dataframe()
    algorithm_stats = model.get_solver_statistics()

    print(f"✅ Scheduling completato: {len(solution_df)} slot schedulati")

    # Inizializza profiler
    print("🔍 Avvio profilazione...")
    profiler = SchedulingProfiler(output_dir="reports")

    # Esegui profilazione completa
    profile = profiler.profile_solution(solution_df, tasks_df, algorithm_stats)

    # Mostra risultati principali
    print("\n📈 RISULTATI PROFILAZIONE")
    print("=" * 40)

    quality = profile['quality_metrics']
    print(f"🎯 Schedule Quality Score: {quality['sqs']:.1f}%")
    print(f"📊 Completeness: {quality['completeness']:.1f}%")
    print(f"🔥 Priority Compliance: {quality['priority_compliance']:.1f}%")
    print(f"⚖️ Resource Efficiency: {quality['resource_efficiency']:.1f}%")

    # Analisi priorità
    priority_analysis = profile['priority_analysis']
    print(f"\n🎯 ANALISI PRIORITÀ")
    print("=" * 30)
    for priority_class, stats in priority_analysis['by_priority_class'].items():
        print(f"{priority_class.upper()}: {stats['scheduled_tasks']}/{stats['total_tasks']} task "
              f"({stats['completion_rate']:.1f}% completati, {stats['compliance_rate']:.1f}% compliance)")

    # Performance algoritmo
    algorithm = profile['algorithm_performance']
    print(f"\n⚡ PERFORMANCE ALGORITMO")
    print("=" * 35)
    print(f"Algoritmo: {algorithm['algorithm']}")
    print(f"Tempo esecuzione: {algorithm['execution_time']:.3f}s")
    print(f"Task/secondo: {algorithm['tasks_per_second']:.1f}")
    print(f"Efficienza: {algorithm['efficiency_rating']}")

    # Violazioni
    violations = profile['violations']
    print(f"\n⚠️ VIOLAZIONI RILEVATE")
    print("=" * 30)
    print(f"Violazioni priorità: {len(violations['priority_violations'])}")
    print(f"Conflitti risorse: {len(violations['resource_conflicts'])}")
    print(f"Anomalie temporali: {len(violations['temporal_anomalies'])}")

    # Raccomandazioni
    recommendations = profile['recommendations']
    if recommendations:
        print(f"\n💡 RACCOMANDAZIONI")
        print("=" * 25)
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")

    # Export dei risultati
    print(f"\n💾 EXPORT RISULTATI")
    print("=" * 25)

    # JSON
    json_file = profiler.export_json(profile)
    print(f"📄 JSON: {json_file}")

    # CSV
    csv_file = profiler.export_csv(profile)
    print(f"📊 CSV: {csv_file}")

    # HTML Dashboard
    html_file = profiler.export_html_dashboard(profile)
    print(f"🌐 HTML: {html_file}")

    print(f"\n🎉 Profilazione completata con successo!")
    print(f"📁 Tutti i file salvati in: reports/")


if __name__ == "__main__":
    main()
