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

        # Assertions per qualità
        self.assertGreaterEqual(quality_metrics['sqs'], 75.0,
                               f"SQS should be >= 75% for production scenario, got {quality_metrics['sqs']:.2f}%")
        self.assertGreaterEqual(quality_metrics['completeness'], 80.0,
                               f"Completeness should be >= 80%, got {quality_metrics['completeness']:.2f}%")
        self.assertLess(execution_time, 10.0,
                       f"Execution should be < 10s on M4, got {execution_time:.2f}s")

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

        # Assertions per carico elevato
        self.assertGreaterEqual(quality_metrics['sqs'], 65.0,
                               f"SQS should be >= 65% for high load, got {quality_metrics['sqs']:.2f}%")
        self.assertGreaterEqual(quality_metrics['completeness'], 70.0,
                               f"Completeness should be >= 70%, got {quality_metrics['completeness']:.2f}%")
        self.assertGreaterEqual(quality_metrics['priority_compliance'], 80.0,
                               f"Priority compliance should be >= 80%, got {quality_metrics['priority_compliance']:.2f}%")
        self.assertLess(execution_time, 20.0,
                       f"Execution should be < 20s on M4, got {execution_time:.2f}s")

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

            # Assertions più permissive per stress test
            self.assertGreaterEqual(quality_metrics['sqs'], 50.0,
                                   f"SQS should be >= 50% for stress test, got {quality_metrics['sqs']:.2f}%")
            self.assertGreaterEqual(quality_metrics['completeness'], 60.0,
                                   f"Completeness should be >= 60%, got {quality_metrics['completeness']:.2f}%")
        else:
            logger.warning("⚠️  Stress test failed to find solution - this may be acceptable")

        # Performance assertion per M4
        self.assertLess(execution_time, 60.0,
                       f"Execution should be < 60s on M4, got {execution_time:.2f}s")

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

        # Verifica che le priorità siano rispettate
        self.assertGreaterEqual(quality_metrics['priority_compliance'], 85.0,
                               f"Priority compliance should be >= 85%, got {quality_metrics['priority_compliance']:.2f}%")
        self.assertGreaterEqual(quality_metrics['completeness'], 95.0,
                               f"Completeness should be >= 95% for simple scenario, got {quality_metrics['completeness']:.2f}%")

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

        # Verifica bilanciamento
        self.assertGreaterEqual(quality_metrics['resource_efficiency'], 60.0,
                               f"Resource efficiency should be >= 60%, got {quality_metrics['resource_efficiency']:.2f}%")


class TestPerformanceBenchmarks(unittest.TestCase):
    """Test di performance calibrati per MacBook Pro M4"""

    def test_performance_benchmarks_m4(self):
        """Benchmark di performance per MacBook Pro M4"""
        logger.info("🚀 Running performance benchmarks for MacBook Pro M4")

        benchmarks = [
            {'tasks': 50, 'expected_time': 3.0, 'expected_sqs': 85.0},
            {'tasks': 100, 'expected_time': 8.0, 'expected_sqs': 80.0},
            {'tasks': 200, 'expected_time': 20.0, 'expected_sqs': 70.0},
        ]

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


if __name__ == '__main__':
    # Configura logging più dettagliato per esecuzione diretta
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    unittest.main(verbosity=2)
