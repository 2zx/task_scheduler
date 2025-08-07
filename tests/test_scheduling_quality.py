"""
Test di qualità per il sistema di scheduling ibrido
Focus sulla qualità del prodotto finale indipendentemente dall'algoritmo utilizzato
"""
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging

from src.scheduler.model import SchedulingModel
from tests.realistic_data_generator import generate_scenario, print_scenario_stats

# Import soglie centralizzate
from src.config_thresholds import (
    SQS_WEIGHTS,
    PRODUCTION_SCENARIO_THRESHOLDS,
    HIGH_LOAD_SCENARIO_THRESHOLDS,
    STRESS_SCENARIO_THRESHOLDS,
    PRIORITY_RESPECT_THRESHOLDS,
    RESOURCE_BALANCE_THRESHOLDS,
    BENCHMARK_M4_THRESHOLDS,
    CALENDAR_DISTRIBUTION_THRESHOLDS,
    get_scenario_thresholds
)

# Configura logging per i test
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QualityMetrics:
    """Classe per calcolare metriche di qualità della pianificazione"""

    @staticmethod
    def calculate_schedule_quality_score(solution_df, tasks_df):
        """
        Calcola Schedule Quality Score (SQS)

        Args:
            solution_df: DataFrame con la soluzione
            tasks_df: DataFrame con i task originali

        Returns:
            dict: Metriche di qualità
        """
        if solution_df is None or solution_df.empty:
            return {
                'sqs': 0.0,
                'completeness': 0.0,
                'priority_compliance': 0.0,
                'resource_efficiency': 0.0
            }

        # 1. Completeness Score (% task schedulati)
        scheduled_tasks = set(solution_df['task_id'].unique())
        total_tasks = set(tasks_df['id'].unique())
        completeness = len(scheduled_tasks) / len(total_tasks) * 100

        # 2. Priority Compliance Index
        priority_compliance = QualityMetrics._calculate_priority_compliance(solution_df, tasks_df)

        # 3. Resource Efficiency
        resource_efficiency = QualityMetrics._calculate_resource_efficiency(solution_df)

        # 4. Schedule Quality Score (weighted average)
        sqs = (
            completeness * 0.4 +  # 40% peso completezza
            priority_compliance * 0.4 +  # 40% peso priorità
            resource_efficiency * 0.2  # 20% peso efficienza
        )

        return {
            'sqs': round(sqs, 2),
            'completeness': round(completeness, 2),
            'priority_compliance': round(priority_compliance, 2),
            'resource_efficiency': round(resource_efficiency, 2),
            'scheduled_tasks': len(scheduled_tasks),
            'total_tasks': len(total_tasks)
        }

    @staticmethod
    def _calculate_priority_compliance(solution_df, tasks_df):
        """Calcola compliance delle priorità"""
        if solution_df.empty:
            return 0.0

        # Merge per ottenere priorità
        merged_df = solution_df.merge(
            tasks_df[['id', 'priority_score']].rename(columns={'id': 'task_id'}),
            on='task_id',
            how='left'
        )

        if merged_df.empty:
            return 0.0

        # Calcola data/ora di inizio per ogni task
        task_start_times = merged_df.groupby('task_id').agg({
            'date': 'min',
            'hour': 'min',
            'priority_score': 'first'
        }).reset_index()

        # Crea datetime per ordinamento
        task_start_times['start_datetime'] = pd.to_datetime(
            task_start_times['date'] + ' ' + task_start_times['hour'].astype(str) + ':00'
        )

        # Ordina per tempo di inizio
        task_start_times = task_start_times.sort_values('start_datetime')

        # Calcola violazioni di priorità
        violations = 0
        total_comparisons = 0

        for i in range(len(task_start_times)):
            for j in range(i + 1, len(task_start_times)):
                task_early = task_start_times.iloc[i]
                task_late = task_start_times.iloc[j]

                # Se task con priorità più bassa inizia prima di uno con priorità più alta
                if task_early['priority_score'] < task_late['priority_score']:
                    violations += 1

                total_comparisons += 1

        if total_comparisons == 0:
            return 100.0

        compliance = (1 - violations / total_comparisons) * 100
        return max(0.0, compliance)

    @staticmethod
    def _calculate_resource_efficiency(solution_df):
        """Calcola efficienza utilizzo risorse"""
        if solution_df.empty:
            return 0.0

        # Calcola ore per risorsa per giorno
        resource_daily_hours = solution_df.groupby(['user_id', 'date']).size().reset_index(name='hours')

        if resource_daily_hours.empty:
            return 0.0

        # Calcola statistiche utilizzo
        mean_hours = resource_daily_hours['hours'].mean()
        std_hours = resource_daily_hours['hours'].std()

        if mean_hours == 0:
            return 0.0

        # Efficienza = 1 - (coefficiente di variazione)
        # Più bilanciato = più efficiente
        cv = std_hours / mean_hours if std_hours > 0 else 0
        efficiency = max(0, (1 - cv)) * 100

        return min(100.0, efficiency)


class TestSchedulingQuality(unittest.TestCase):
    """Test di qualità per il sistema di scheduling"""

    def setUp(self):
        """Setup per i test"""
        self.maxDiff = None
        logger.info("=" * 60)
        logger.info(f"Starting test: {self._testMethodName}")

    def tearDown(self):
        """Cleanup dopo i test"""
        logger.info(f"Completed test: {self._testMethodName}")
        logger.info("=" * 60)

    def test_100_tasks_production_quality(self):
        """Test qualità scenario produzione con 100 task"""
        logger.info("🧪 Testing 100 tasks production scenario quality")

        # Genera scenario realistico
        tasks_df, calendar_slots_df, leaves_df = generate_scenario(
            'production', num_tasks=100, num_resources=10
        )

        print_scenario_stats(tasks_df, calendar_slots_df, leaves_df)

        # Esegui scheduling
        start_time = time.time()
        model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)
        success = model.solve()
        execution_time = time.time() - start_time

        # Verifica successo
        self.assertTrue(success, "Scheduling should succeed for production scenario")
        self.assertIsNotNone(model.solution, "Solution should be generated")

        # Ottieni DataFrame soluzione
        solution_df = model.get_solution_dataframe()
        self.assertIsNotNone(solution_df, "Solution DataFrame should be generated")

        # Calcola metriche qualità
        quality_metrics = QualityMetrics.calculate_schedule_quality_score(solution_df, tasks_df)

        # Log risultati
        logger.info(f"⏱️  Execution time: {execution_time:.2f} seconds")
        logger.info(f"📊 Quality Metrics:")
        logger.info(f"   SQS (Schedule Quality Score): {quality_metrics['sqs']:.2f}%")
        logger.info(f"   Completeness: {quality_metrics['completeness']:.2f}%")
        logger.info(f"   Priority Compliance: {quality_metrics['priority_compliance']:.2f}%")
        logger.info(f"   Resource Efficiency: {quality_metrics['resource_efficiency']:.2f}%")
        logger.info(f"   Tasks Scheduled: {quality_metrics['scheduled_tasks']}/{quality_metrics['total_tasks']}")

        # Usa soglie centralizzate per production scenario
        thresholds = PRODUCTION_SCENARIO_THRESHOLDS

        # Assertions per qualità
        self.assertGreaterEqual(quality_metrics['sqs'], thresholds['sqs_min'],
                               f"SQS should be >= {thresholds['sqs_min']}% for production scenario, got {quality_metrics['sqs']:.2f}%")
        self.assertGreaterEqual(quality_metrics['completeness'], thresholds['completeness_min'],
                               f"Completeness should be >= {thresholds['completeness_min']}%, got {quality_metrics['completeness']:.2f}%")
        self.assertLess(execution_time, thresholds['max_execution_time'],
                       f"Execution should be < {thresholds['max_execution_time']}s on M4, got {execution_time:.2f}s")

    def test_200_tasks_high_load_quality(self):
        """Test qualità scenario carico elevato con 200 task"""
        logger.info("🧪 Testing 200 tasks high load scenario quality")

        # Genera scenario carico elevato
        tasks_df, calendar_slots_df, leaves_df = generate_scenario(
            'high_load', num_tasks=200, num_resources=10
        )

        print_scenario_stats(tasks_df, calendar_slots_df, leaves_df)

        # Esegui scheduling
        start_time = time.time()
        model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)
        success = model.solve()
        execution_time = time.time() - start_time

        # Verifica successo
        self.assertTrue(success, "Scheduling should succeed for high load scenario")

        # Ottieni metriche
        solution_df = model.get_solution_dataframe()
        quality_metrics = QualityMetrics.calculate_schedule_quality_score(solution_df, tasks_df)

        # Log risultati
        logger.info(f"⏱️  Execution time: {execution_time:.2f} seconds")
        logger.info(f"📊 Quality Metrics:")
        logger.info(f"   SQS: {quality_metrics['sqs']:.2f}%")
        logger.info(f"   Completeness: {quality_metrics['completeness']:.2f}%")
        logger.info(f"   Priority Compliance: {quality_metrics['priority_compliance']:.2f}%")
        logger.info(f"   Resource Efficiency: {quality_metrics['resource_efficiency']:.2f}%")

        # Usa soglie centralizzate per high load scenario
        thresholds = HIGH_LOAD_SCENARIO_THRESHOLDS

        # Assertions per carico elevato
        self.assertGreaterEqual(quality_metrics['sqs'], thresholds['sqs_min'],
                               f"SQS should be >= {thresholds['sqs_min']}% for high load, got {quality_metrics['sqs']:.2f}%")
        self.assertGreaterEqual(quality_metrics['completeness'], thresholds['completeness_min'],
                               f"Completeness should be >= {thresholds['completeness_min']}%, got {quality_metrics['completeness']:.2f}%")
        self.assertGreaterEqual(quality_metrics['priority_compliance'], thresholds['priority_compliance_min'],
                               f"Priority compliance should be >= {thresholds['priority_compliance_min']}%, got {quality_metrics['priority_compliance']:.2f}%")
        self.assertLess(execution_time, thresholds['max_execution_time'],
                       f"Execution should be < {thresholds['max_execution_time']}s on M4, got {execution_time:.2f}s")

    def test_500_tasks_stress_quality(self):
        """Test qualità scenario stress con 500 task"""
        logger.info("🧪 Testing 500 tasks stress scenario quality")

        # Genera scenario stress
        tasks_df, calendar_slots_df, leaves_df = generate_scenario(
            'stress', num_tasks=500, num_resources=10
        )

        print_scenario_stats(tasks_df, calendar_slots_df, leaves_df)

        # Esegui scheduling
        start_time = time.time()
        model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)
        success = model.solve()
        execution_time = time.time() - start_time

        # Per stress test, anche parziale successo è accettabile
        logger.info(f"⏱️  Execution time: {execution_time:.2f} seconds")
        logger.info(f"✅ Scheduling success: {success}")

        if success:
            solution_df = model.get_solution_dataframe()
            quality_metrics = QualityMetrics.calculate_schedule_quality_score(solution_df, tasks_df)

            logger.info(f"📊 Quality Metrics:")
            logger.info(f"   SQS: {quality_metrics['sqs']:.2f}%")
            logger.info(f"   Completeness: {quality_metrics['completeness']:.2f}%")
            logger.info(f"   Priority Compliance: {quality_metrics['priority_compliance']:.2f}%")
            logger.info(f"   Resource Efficiency: {quality_metrics['resource_efficiency']:.2f}%")

            # Usa soglie centralizzate per stress scenario
            thresholds = STRESS_SCENARIO_THRESHOLDS

            # Assertions più permissive per stress test
            self.assertGreaterEqual(quality_metrics['sqs'], thresholds['sqs_min'],
                                   f"SQS should be >= {thresholds['sqs_min']}% for stress test, got {quality_metrics['sqs']:.2f}%")
            self.assertGreaterEqual(quality_metrics['completeness'], thresholds['completeness_min'],
                                   f"Completeness should be >= {thresholds['completeness_min']}%, got {quality_metrics['completeness']:.2f}%")
        else:
            logger.warning("⚠️  Stress test failed to find solution - this may be acceptable")

        # Usa soglie centralizzate per tempo di esecuzione
        thresholds = STRESS_SCENARIO_THRESHOLDS
        self.assertLess(execution_time, thresholds['max_execution_time'],
                       f"Execution should be < {thresholds['max_execution_time']}s on M4, got {execution_time:.2f}s")

    def test_priority_respect_quality(self):
        """Test specifico per rispetto delle priorità"""
        logger.info("🧪 Testing priority respect quality")

        # Crea scenario con priorità ben definite
        tasks_data = []
        for i in range(1, 51):  # 50 task
            if i <= 10:  # 10 task alta priorità
                priority = 90.0
            elif i <= 30:  # 20 task media priorità
                priority = 50.0
            else:  # 20 task bassa priorità
                priority = 20.0

            tasks_data.append({
                'id': i,
                'name': f'Priority_Task_{i:02d}',
                'user_id': (i % 5) + 1,  # 5 risorse
                'remaining_hours': 4.0,
                'priority_score': priority
            })

        tasks_df = pd.DataFrame(tasks_data)

        # Genera calendari semplici
        calendar_data = []
        for task_id in range(1, 51):
            for day in range(5):  # Lun-Ven
                calendar_data.append({
                    'task_id': task_id,
                    'dayofweek': day,
                    'hour_from': 9,
                    'hour_to': 17
                })

        calendar_slots_df = pd.DataFrame(calendar_data)
        leaves_df = pd.DataFrame()  # Nessuna assenza

        # Esegui scheduling
        model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)
        success = model.solve()

        self.assertTrue(success, "Priority test should succeed")

        solution_df = model.get_solution_dataframe()
        quality_metrics = QualityMetrics.calculate_schedule_quality_score(solution_df, tasks_df)

        logger.info(f"📊 Priority Test Results:")
        logger.info(f"   Priority Compliance: {quality_metrics['priority_compliance']:.2f}%")
        logger.info(f"   Completeness: {quality_metrics['completeness']:.2f}%")

        # Usa soglie centralizzate per priority respect
        thresholds = PRIORITY_RESPECT_THRESHOLDS

        # Verifica che le priorità siano rispettate
        self.assertGreaterEqual(quality_metrics['priority_compliance'], thresholds['priority_compliance_min'],
                               f"Priority compliance should be >= {thresholds['priority_compliance_min']}%, got {quality_metrics['priority_compliance']:.2f}%")
        self.assertGreaterEqual(quality_metrics['completeness'], thresholds['completeness_min'],
                               f"Completeness should be >= {thresholds['completeness_min']}% for simple scenario, got {quality_metrics['completeness']:.2f}%")

    def test_resource_balance_quality(self):
        """Test bilanciamento delle risorse"""
        logger.info("🧪 Testing resource balance quality")

        # Genera scenario bilanciato
        tasks_df, calendar_slots_df, leaves_df = generate_scenario(
            'production', num_tasks=80, num_resources=8
        )

        model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)
        success = model.solve()

        self.assertTrue(success, "Resource balance test should succeed")

        solution_df = model.get_solution_dataframe()
        quality_metrics = QualityMetrics.calculate_schedule_quality_score(solution_df, tasks_df)

        # Analizza distribuzione per risorsa
        resource_hours = solution_df.groupby('user_id').size()
        logger.info(f"📊 Resource Distribution:")
        for user_id, hours in resource_hours.items():
            logger.info(f"   User {user_id}: {hours} hours")

        logger.info(f"   Resource Efficiency: {quality_metrics['resource_efficiency']:.2f}%")

        # Usa soglie centralizzate per resource balance
        thresholds = RESOURCE_BALANCE_THRESHOLDS

        # Verifica bilanciamento
        self.assertGreaterEqual(quality_metrics['resource_efficiency'], thresholds['resource_efficiency_min'],
                               f"Resource efficiency should be >= {thresholds['resource_efficiency_min']}%, got {quality_metrics['resource_efficiency']:.2f}%")


class TestPerformanceBenchmarks(unittest.TestCase):
    """Test di performance calibrati per MacBook Pro M4"""

    def test_performance_benchmarks_m4(self):
        """Benchmark di performance per MacBook Pro M4"""
        logger.info("🚀 Running performance benchmarks for MacBook Pro M4")

        # Usa soglie centralizzate per benchmark
        benchmarks = BENCHMARK_M4_THRESHOLDS

        results = []

        for benchmark in benchmarks:
            logger.info(f"📊 Benchmark: {benchmark['tasks']} tasks")

            # Genera scenario
            tasks_df, calendar_slots_df, leaves_df = generate_scenario(
                'production', num_tasks=benchmark['tasks'], num_resources=10
            )

            # Esegui test
            start_time = time.time()
            model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)
            success = model.solve()
            execution_time = time.time() - start_time

            # Calcola qualità
            quality_metrics = {'sqs': 0.0}
            if success:
                solution_df = model.get_solution_dataframe()
                quality_metrics = QualityMetrics.calculate_schedule_quality_score(solution_df, tasks_df)

            result = {
                'tasks': benchmark['tasks'],
                'execution_time': execution_time,
                'success': success,
                'sqs': quality_metrics['sqs']
            }
            results.append(result)

            logger.info(f"   ⏱️  Time: {execution_time:.2f}s (expected < {benchmark['expected_time']}s)")
            logger.info(f"   📈 SQS: {quality_metrics['sqs']:.2f}% (expected >= {benchmark['expected_sqs']}%)")
            logger.info(f"   ✅ Success: {success}")

            # Assertions
            self.assertTrue(success, f"Benchmark {benchmark['tasks']} tasks should succeed")
            self.assertLess(execution_time, benchmark['expected_time'],
                           f"Execution time should be < {benchmark['expected_time']}s for {benchmark['tasks']} tasks")
            if success:
                self.assertGreaterEqual(quality_metrics['sqs'], benchmark['expected_sqs'],
                                       f"SQS should be >= {benchmark['expected_sqs']}% for {benchmark['tasks']} tasks")

        # Log summary
        logger.info("🏆 Performance Benchmark Summary:")
        for result in results:
            logger.info(f"   {result['tasks']} tasks: {result['execution_time']:.2f}s, SQS: {result['sqs']:.2f}%")


class TestCalendarDistributionVisualization(unittest.TestCase):
    """Test con rappresentazione grafica della distribuzione calendario"""

    def setUp(self):
        """Setup per i test"""
        self.maxDiff = None
        logger.info("=" * 60)
        logger.info(f"Starting test: {self._testMethodName}")

    def tearDown(self):
        """Cleanup dopo i test"""
        logger.info(f"Completed test: {self._testMethodName}")
        logger.info("=" * 60)

    def test_calendar_distribution_visualization(self):
        """Test con visualizzazioni calendario complete"""
        logger.info("📅 Testing calendar distribution with full visualization")

        # Genera scenario medio (100 task, 10 risorse, ~2 settimane)
        tasks_df, calendar_slots_df, leaves_df = generate_scenario(
            'production', num_tasks=100, num_resources=10
        )

        print_scenario_stats(tasks_df, calendar_slots_df, leaves_df)

        # Esegui scheduling
        start_time = time.time()
        model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)
        success = model.solve()
        execution_time = time.time() - start_time

        # Verifica successo
        self.assertTrue(success, "Calendar distribution test should succeed")
        self.assertIsNotNone(model.solution, "Solution should be generated")

        # Ottieni DataFrame soluzione
        solution_df = model.get_solution_dataframe()
        self.assertIsNotNone(solution_df, "Solution DataFrame should be generated")

        # Calcola metriche qualità
        quality_metrics = QualityMetrics.calculate_schedule_quality_score(solution_df, tasks_df)

        # Log risultati base
        logger.info(f"⏱️  Execution time: {execution_time:.2f} seconds")
        logger.info(f"📊 Quality Metrics:")
        logger.info(f"   SQS: {quality_metrics['sqs']:.2f}%")
        logger.info(f"   Completeness: {quality_metrics['completeness']:.2f}%")
        logger.info(f"   Priority Compliance: {quality_metrics['priority_compliance']:.2f}%")
        logger.info(f"   Resource Efficiency: {quality_metrics['resource_efficiency']:.2f}%")

        # ============================================================================
        # GENERAZIONE VISUALIZZAZIONI CALENDARIO
        # ============================================================================

        logger.info("🎨 Generazione visualizzazioni calendario...")

        # Import visualizer
        from src.scheduler.visualization import ScheduleVisualizer

        # Crea visualizer con directory reports/charts
        import os
        charts_dir = os.path.join("reports", "charts")
        os.makedirs(charts_dir, exist_ok=True)

        visualizer = ScheduleVisualizer(solution_df, tasks_df, output_dir=charts_dir)

        # Genera tutti i grafici calendario
        calendar_charts = visualizer.generate_calendar_charts()

        # Verifica che tutti i grafici siano stati generati
        expected_charts = [
            'calendar_heatmap',
            'weekly_distribution',
            'hourly_timeline',
            'resource_calendar',
            'priority_timeline'
        ]

        for chart_name in expected_charts:
            self.assertIn(chart_name, calendar_charts, f"Chart {chart_name} should be generated")
            if calendar_charts[chart_name]:
                self.assertTrue(os.path.exists(calendar_charts[chart_name]),
                               f"Chart file {chart_name} should exist")
                logger.info(f"   ✅ {chart_name}: {calendar_charts[chart_name]}")

        # Genera anche i grafici standard per confronto
        standard_charts = visualizer.generate_all_charts()

        # Combina tutti i grafici
        all_charts = {**standard_charts, **calendar_charts}

        # ============================================================================
        # ANALISI DISTRIBUZIONE CALENDARIO
        # ============================================================================

        logger.info("📈 Analisi distribuzione calendario...")

        # Calcola metriche di distribuzione calendario
        calendar_metrics = self._calculate_calendar_distribution_metrics(solution_df, tasks_df)

        # Log metriche calendario
        logger.info(f"📅 Calendar Distribution Metrics:")
        logger.info(f"   Daily Concentration Max: {calendar_metrics['daily_concentration_max']:.1f}%")
        logger.info(f"   Hourly Concentration Max: {calendar_metrics['hourly_concentration_max']:.1f}%")
        logger.info(f"   Resource Balance: {calendar_metrics['resource_balance']:.1f}%")
        logger.info(f"   Weekend Usage: {calendar_metrics['weekend_usage']:.1f}%")
        logger.info(f"   Priority Timeline Compliance: {calendar_metrics['priority_timeline_compliance']:.1f}%")

        # ============================================================================
        # VERIFICA SOGLIE DISTRIBUZIONE CALENDARIO
        # ============================================================================

        # Usa soglie centralizzate per calendar distribution
        thresholds = CALENDAR_DISTRIBUTION_THRESHOLDS

        # Assertions per qualità generale
        self.assertGreaterEqual(quality_metrics['sqs'], thresholds['sqs_min'],
                               f"SQS should be >= {thresholds['sqs_min']}% for calendar test, got {quality_metrics['sqs']:.2f}%")
        self.assertGreaterEqual(quality_metrics['completeness'], thresholds['completeness_min'],
                               f"Completeness should be >= {thresholds['completeness_min']}%, got {quality_metrics['completeness']:.2f}%")
        self.assertLess(execution_time, thresholds['max_execution_time'],
                       f"Execution should be < {thresholds['max_execution_time']}s on M4, got {execution_time:.2f}s")

        # Assertions per distribuzione calendario
        self.assertLessEqual(calendar_metrics['daily_concentration_max'], thresholds['max_daily_concentration'],
                            f"Daily concentration should be <= {thresholds['max_daily_concentration']}%, got {calendar_metrics['daily_concentration_max']:.1f}%")
        self.assertLessEqual(calendar_metrics['hourly_concentration_max'], thresholds['max_hourly_concentration'],
                            f"Hourly concentration should be <= {thresholds['max_hourly_concentration']}%, got {calendar_metrics['hourly_concentration_max']:.1f}%")
        self.assertGreaterEqual(calendar_metrics['resource_balance'], thresholds['min_resource_balance'],
                               f"Resource balance should be >= {thresholds['min_resource_balance']}%, got {calendar_metrics['resource_balance']:.1f}%")
        self.assertLessEqual(calendar_metrics['weekend_usage'], thresholds['max_weekend_usage'],
                            f"Weekend usage should be <= {thresholds['max_weekend_usage']}%, got {calendar_metrics['weekend_usage']:.1f}%")
        self.assertGreaterEqual(calendar_metrics['priority_timeline_compliance'], thresholds['priority_timeline_compliance'],
                               f"Priority timeline compliance should be >= {thresholds['priority_timeline_compliance']}%, got {calendar_metrics['priority_timeline_compliance']:.1f}%")

        # ============================================================================
        # GENERA DASHBOARD AGGIORNATA
        # ============================================================================

        logger.info("📊 Generazione dashboard aggiornata...")

        # Crea dashboard HTML con tutti i grafici (standard + calendario)
        dashboard_path = visualizer.create_enhanced_summary_report(all_charts)

        self.assertTrue(os.path.exists(dashboard_path), "Dashboard HTML should be created")
        logger.info(f"   ✅ Dashboard: {dashboard_path}")

        # ============================================================================
        # RISULTATI FINALI
        # ============================================================================

        logger.info("🎉 Test calendario completato con successo!")
        logger.info(f"📁 Grafici generati: {len(all_charts)}")
        logger.info(f"📊 Dashboard: {os.path.basename(dashboard_path)}")

        # Verifica che tutti i file esistano
        for chart_name, chart_path in all_charts.items():
            if chart_path:
                self.assertTrue(os.path.exists(chart_path), f"Chart {chart_name} file should exist")

    def _calculate_calendar_distribution_metrics(self, solution_df, tasks_df):
        """Calcola metriche specifiche per la distribuzione calendario"""

        if solution_df is None or solution_df.empty:
            return {
                'daily_concentration_max': 0.0,
                'hourly_concentration_max': 0.0,
                'resource_balance': 0.0,
                'weekend_usage': 0.0,
                'priority_timeline_compliance': 0.0
            }

        # Prepara i dati
        solution_copy = solution_df.copy()
        solution_copy['datetime'] = pd.to_datetime(solution_copy['date'])
        solution_copy['weekday'] = solution_copy['datetime'].dt.dayofweek

        total_tasks = len(solution_copy)

        # 1. Daily Concentration Max (% massima di task in un singolo giorno)
        daily_counts = solution_copy.groupby('date').size()
        daily_concentration_max = (daily_counts.max() / total_tasks) * 100 if total_tasks > 0 else 0

        # 2. Hourly Concentration Max (% massima di task in una singola ora)
        hourly_counts = solution_copy.groupby('hour').size()
        hourly_concentration_max = (hourly_counts.max() / total_tasks) * 100 if total_tasks > 0 else 0

        # 3. Resource Balance (bilanciamento tra risorse)
        resource_counts = solution_copy.groupby('user_id').size()
        if len(resource_counts) > 1:
            mean_tasks = resource_counts.mean()
            std_tasks = resource_counts.std()
            cv = std_tasks / mean_tasks if mean_tasks > 0 else 0
            resource_balance = max(0, (1 - cv)) * 100
        else:
            resource_balance = 100.0

        # 4. Weekend Usage (% task nel weekend)
        weekend_tasks = solution_copy[solution_copy['weekday'].isin([5, 6])]  # Sabato=5, Domenica=6
        weekend_usage = (len(weekend_tasks) / total_tasks) * 100 if total_tasks > 0 else 0

        # 5. Priority Timeline Compliance (task alta priorità schedulati presto)
        # Merge con tasks per ottenere priorità
        merged_df = solution_copy.merge(
            tasks_df[['id', 'priority_score']].rename(columns={'id': 'task_id'}),
            on='task_id',
            how='left'
        )

        if not merged_df.empty and 'priority_score' in merged_df.columns:
            # Task alta priorità (>=80)
            high_priority_tasks = merged_df[merged_df['priority_score'] >= 80]

            if len(high_priority_tasks) > 0:
                # Calcola giorno medio per task alta priorità
                high_priority_tasks['day_num'] = (high_priority_tasks['datetime'] - high_priority_tasks['datetime'].min()).dt.days
                avg_day_high = high_priority_tasks['day_num'].mean()

                # Calcola giorno medio per tutti i task
                merged_df['day_num'] = (merged_df['datetime'] - merged_df['datetime'].min()).dt.days
                avg_day_all = merged_df['day_num'].mean()

                # Compliance = quanto prima sono schedulati i task alta priorità
                if avg_day_all > 0:
                    priority_timeline_compliance = max(0, (1 - avg_day_high / avg_day_all)) * 100
                else:
                    priority_timeline_compliance = 100.0
            else:
                priority_timeline_compliance = 100.0  # Nessun task alta priorità
        else:
            priority_timeline_compliance = 0.0

        return {
            'daily_concentration_max': round(daily_concentration_max, 1),
            'hourly_concentration_max': round(hourly_concentration_max, 1),
            'resource_balance': round(resource_balance, 1),
            'weekend_usage': round(weekend_usage, 1),
            'priority_timeline_compliance': round(priority_timeline_compliance, 1)
        }


if __name__ == '__main__':
    # Configura logging più dettagliato per esecuzione diretta
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    unittest.main(verbosity=2)
