"""
Sistema centralizzato di profilazione per il Task Scheduler
Fornisce analisi dettagliate di qualità, priorità, risorse e performance
"""
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import json
import csv
from pathlib import Path

# Import soglie centralizzate
from ..config_thresholds import (
    PRIORITY_CLASSIFICATION,
    SQS_WEIGHTS,
    RECOMMENDATION_THRESHOLDS,
    SEVERE_PRIORITY_VIOLATION_THRESHOLD,
    TEMPORAL_ANOMALY_THRESHOLDS,
    ALGORITHM_EFFICIENCY_THRESHOLDS,
    evaluate_sqs_quality,
    evaluate_priority_compliance_quality,
    should_generate_recommendation
)

logger = logging.getLogger(__name__)


class SchedulingProfiler:
    """Profiler centralizzato per tutte le metriche di scheduling"""

    def __init__(self, output_dir: str = "reports"):
        """
        Inizializza il profiler

        Args:
            output_dir: Directory per salvare i report
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Cache per evitare ricalcoli
        self._cache = {}

        # Configurazione soglie
        self.priority_thresholds = {
            'high': 80,
            'medium': 50,
            'low': 0
        }

    def profile_solution(self, solution_df: pd.DataFrame, tasks_df: pd.DataFrame,
                        algorithm_stats: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Profila una soluzione completa di scheduling

        Args:
            solution_df: DataFrame con la soluzione (task_id, date, hour)
            tasks_df: DataFrame con i task originali
            algorithm_stats: Statistiche dell'algoritmo utilizzato

        Returns:
            Dict completo con tutte le analisi
        """
        logger.info("🔍 Avvio profilazione completa della soluzione")

        if solution_df is None or solution_df.empty:
            return self._empty_profile()

        # Prepara i dati
        self._prepare_data(solution_df, tasks_df, algorithm_stats)

        # Esegui tutte le analisi
        profile = {
            'metadata': self._get_metadata(),
            'quality_metrics': self._calculate_quality_metrics(),
            'priority_analysis': self._analyze_priority_compliance(),
            'resource_analysis': self._analyze_resource_utilization(),
            'temporal_analysis': self._analyze_temporal_distribution(),
            'algorithm_performance': self._analyze_algorithm_performance(),
            'violations': self._detect_violations(),
            'recommendations': self._generate_recommendations()
        }

        logger.info("✅ Profilazione completata")
        return profile

    def _prepare_data(self, solution_df: pd.DataFrame, tasks_df: pd.DataFrame,
                     algorithm_stats: Optional[Dict]):
        """Prepara e valida i dati per l'analisi"""

        # Salva i dati principali
        self.solution_df = solution_df.copy()
        self.tasks_df = tasks_df.copy()
        self.algorithm_stats = algorithm_stats or {}

        # Merge per ottenere informazioni complete
        task_info = self.tasks_df[['id', 'priority_score', 'user_id', 'remaining_hours']].copy()
        task_info = task_info.rename(columns={'id': 'task_id'})

        self.merged_df = self.solution_df.merge(
            task_info,
            on='task_id',
            how='left',
            suffixes=('', '_task')
        )

        # Se il merge ha creato user_id_x e user_id_y, usa user_id_x (dal solution_df)
        if 'user_id_x' in self.merged_df.columns:
            self.merged_df['user_id'] = self.merged_df['user_id_x']
            self.merged_df = self.merged_df.drop(['user_id_x', 'user_id_y'], axis=1)

        # Debug: verifica colonne presenti
        logger.info(f"DEBUG - Colonne solution_df: {list(self.solution_df.columns)}")
        logger.info(f"DEBUG - Colonne tasks_df: {list(self.tasks_df.columns)}")
        logger.info(f"DEBUG - Colonne merged_df: {list(self.merged_df.columns)}")
        logger.info(f"DEBUG - Shape solution_df: {self.solution_df.shape}")
        logger.info(f"DEBUG - Shape merged_df: {self.merged_df.shape}")

        # Verifica se il merge è andato a buon fine
        if 'user_id' not in self.merged_df.columns:
            logger.error("ERRORE: user_id non presente nel merged_df!")
            logger.info(f"Sample solution_df:\n{self.solution_df.head()}")
            logger.info(f"Sample tasks_df:\n{self.tasks_df.head()}")
            logger.info(f"Sample merged_df:\n{self.merged_df.head()}")

        # Converti date se necessario
        if 'date' in self.merged_df.columns:
            self.merged_df['date'] = pd.to_datetime(self.merged_df['date'])

        # Classifica task per priorità
        self.merged_df['priority_class'] = self.merged_df['priority_score'].apply(self._classify_priority)

        # Calcola statistiche base
        self.scheduled_tasks = set(self.solution_df['task_id'].unique())
        self.total_tasks = set(self.tasks_df['id'].unique())

        logger.debug(f"Dati preparati: {len(self.scheduled_tasks)} task schedulati su {len(self.total_tasks)} totali")

    def _classify_priority(self, priority_score: float) -> str:
        """Classifica un task per priorità"""
        if priority_score >= self.priority_thresholds['high']:
            return 'high'
        elif priority_score >= self.priority_thresholds['medium']:
            return 'medium'
        else:
            return 'low'

    def _get_metadata(self) -> Dict[str, Any]:
        """Metadati della profilazione"""
        return {
            'timestamp': datetime.now().isoformat(),
            'total_tasks': len(self.total_tasks),
            'scheduled_tasks': len(self.scheduled_tasks),
            'algorithm': self.algorithm_stats.get('algorithm', 'unknown'),
            'priority_thresholds': self.priority_thresholds
        }

    def _calculate_quality_metrics(self) -> Dict[str, float]:
        """Calcola metriche di qualità principali"""

        # 1. Completeness Score (% task schedulati)
        completeness = len(self.scheduled_tasks) / len(self.total_tasks) * 100 if self.total_tasks else 0

        # 2. Priority Compliance Index
        priority_compliance = self._calculate_priority_compliance_detailed()

        # 3. Resource Efficiency
        resource_efficiency = self._calculate_resource_efficiency()

        # 4. Schedule Quality Score (weighted average)
        sqs = (
            completeness * 0.4 +
            priority_compliance['overall'] * 0.4 +
            resource_efficiency * 0.2
        )

        return {
            'sqs': round(sqs, 2),
            'completeness': round(completeness, 2),
            'priority_compliance': round(priority_compliance['overall'], 2),
            'resource_efficiency': round(resource_efficiency, 2)
        }

    def _calculate_priority_compliance_detailed(self) -> Dict[str, float]:
        """Calcola priority compliance con dettagli per fascia"""

        if self.merged_df.empty:
            return {'overall': 0.0, 'by_class': {}, 'violations': []}

        # Calcola data/ora di inizio per ogni task
        task_start_times = self.merged_df.groupby('task_id').agg({
            'date': 'min',
            'hour': 'min',
            'priority_score': 'first',
            'priority_class': 'first'
        }).reset_index()

        # Crea datetime per ordinamento
        task_start_times['start_datetime'] = pd.to_datetime(
            task_start_times['date'].astype(str) + ' ' +
            task_start_times['hour'].astype(str) + ':00'
        )

        # Ordina per tempo di inizio
        task_start_times = task_start_times.sort_values('start_datetime')

        # Calcola violazioni di priorità
        violations = []
        total_comparisons = 0
        violations_count = 0

        for i in range(len(task_start_times)):
            for j in range(i + 1, len(task_start_times)):
                task_early = task_start_times.iloc[i]
                task_late = task_start_times.iloc[j]

                # Se task con priorità più bassa inizia prima di uno con priorità più alta
                if task_early['priority_score'] < task_late['priority_score']:
                    violations.append({
                        'early_task': int(task_early['task_id']),
                        'early_priority': float(task_early['priority_score']),
                        'late_task': int(task_late['task_id']),
                        'late_priority': float(task_late['priority_score']),
                        'time_gap_hours': (task_late['start_datetime'] - task_early['start_datetime']).total_seconds() / 3600
                    })
                    violations_count += 1

                total_comparisons += 1

        # Calcola compliance overall
        overall_compliance = (1 - violations_count / total_comparisons) * 100 if total_comparisons > 0 else 100.0

        # Calcola compliance per classe di priorità
        by_class = {}
        for priority_class in ['high', 'medium', 'low']:
            class_tasks = task_start_times[task_start_times['priority_class'] == priority_class]
            if len(class_tasks) > 0:
                # Per ogni classe, calcola quanti task sono schedulati nell'ordine corretto
                class_violations = sum(1 for v in violations
                                     if self._classify_priority(v['early_priority']) == priority_class)
                class_comparisons = len(class_tasks) * (len(task_start_times) - len(class_tasks))

                if class_comparisons > 0:
                    class_compliance = (1 - class_violations / class_comparisons) * 100
                else:
                    class_compliance = 100.0

                by_class[priority_class] = round(class_compliance, 2)
            else:
                by_class[priority_class] = 0.0

        return {
            'overall': max(0.0, overall_compliance),
            'by_class': by_class,
            'violations': violations,
            'total_violations': violations_count,
            'total_comparisons': total_comparisons
        }

    def _calculate_resource_efficiency(self) -> float:
        """Calcola efficienza utilizzo risorse"""

        if self.merged_df.empty:
            return 0.0

        # Calcola ore per risorsa per giorno
        resource_daily_hours = self.merged_df.groupby(['user_id', 'date']).size().reset_index(name='hours')

        if resource_daily_hours.empty:
            return 0.0

        # Calcola statistiche utilizzo
        mean_hours = resource_daily_hours['hours'].mean()
        std_hours = resource_daily_hours['hours'].std()

        if mean_hours == 0:
            return 0.0

        # Efficienza = 1 - (coefficiente di variazione)
        cv = std_hours / mean_hours if std_hours > 0 else 0
        efficiency = max(0, (1 - cv)) * 100

        return min(100.0, efficiency)

    def _analyze_priority_compliance(self) -> Dict[str, Any]:
        """Analisi dettagliata del rispetto delle priorità"""

        priority_details = self._calculate_priority_compliance_detailed()

        # Statistiche per fascia di priorità
        priority_stats = {}
        for priority_class in ['high', 'medium', 'low']:
            class_tasks = self.tasks_df[
                self.tasks_df['priority_score'].apply(self._classify_priority) == priority_class
            ]
            scheduled_class_tasks = class_tasks[class_tasks['id'].isin(self.scheduled_tasks)]

            priority_stats[priority_class] = {
                'total_tasks': len(class_tasks),
                'scheduled_tasks': len(scheduled_class_tasks),
                'completion_rate': len(scheduled_class_tasks) / len(class_tasks) * 100 if len(class_tasks) > 0 else 0,
                'avg_priority_score': float(class_tasks['priority_score'].mean()) if len(class_tasks) > 0 else 0,
                'compliance_rate': priority_details['by_class'].get(priority_class, 0)
            }

        # Analisi violazioni più gravi
        violations = priority_details['violations']
        severe_violations = [v for v in violations if v['late_priority'] - v['early_priority'] > 30]

        return {
            'overall_compliance': priority_details['overall'],
            'by_priority_class': priority_stats,
            'violations': {
                'total': len(violations),
                'severe': len(severe_violations),
                'details': violations[:10]  # Prime 10 violazioni per il report
            },
            'recommendations': self._get_priority_recommendations(priority_stats, violations)
        }

    def _analyze_resource_utilization(self) -> Dict[str, Any]:
        """Analisi utilizzo delle risorse"""

        if self.merged_df.empty:
            return {'error': 'No data available'}

        # Statistiche per risorsa
        resource_stats = self.merged_df.groupby('user_id').agg({
            'task_id': 'nunique',
            'hour': 'count',
            'priority_score': ['mean', 'std']
        }).round(2)

        resource_stats.columns = ['tasks_count', 'total_hours', 'avg_priority', 'priority_std']
        resource_stats = resource_stats.reset_index()

        # Bilanciamento del carico
        load_balance = {
            'mean_hours': float(resource_stats['total_hours'].mean()),
            'std_hours': float(resource_stats['total_hours'].std()),
            'min_hours': int(resource_stats['total_hours'].min()),
            'max_hours': int(resource_stats['total_hours'].max()),
            'coefficient_variation': float(resource_stats['total_hours'].std() / resource_stats['total_hours'].mean()) if resource_stats['total_hours'].mean() > 0 else 0
        }

        # Utilizzo per giorno
        daily_utilization = self.merged_df.groupby(['date', 'user_id']).size().unstack(fill_value=0)

        return {
            'resource_stats': resource_stats.to_dict('records'),
            'load_balance': load_balance,
            'daily_utilization_summary': {
                'avg_daily_hours': float(daily_utilization.values.mean()),
                'peak_daily_hours': int(daily_utilization.values.max()),
                'total_resource_days': int(daily_utilization.shape[0] * daily_utilization.shape[1])
            },
            'efficiency_score': self._calculate_resource_efficiency()
        }

    def _analyze_temporal_distribution(self) -> Dict[str, Any]:
        """Analisi distribuzione temporale"""

        if self.merged_df.empty:
            return {'error': 'No data available'}

        # Distribuzione per giorno
        daily_distribution = self.merged_df.groupby('date').agg({
            'task_id': 'nunique',
            'hour': 'count',
            'priority_score': 'mean'
        }).round(2)

        # Distribuzione per ora del giorno
        hourly_distribution = self.merged_df.groupby('hour').agg({
            'task_id': 'nunique',
            'priority_score': 'mean'
        }).round(2)

        # Timeline delle priorità
        priority_timeline = self.merged_df.groupby(['date', 'priority_class']).size().unstack(fill_value=0)

        # Concentrazione temporale
        date_range = (self.merged_df['date'].max() - self.merged_df['date'].min()).days + 1

        return {
            'date_range_days': int(date_range),
            'daily_stats': {
                'avg_tasks_per_day': float(daily_distribution['task_id'].mean()),
                'avg_hours_per_day': float(daily_distribution['hour'].mean()),
                'peak_day_tasks': int(daily_distribution['task_id'].max()),
                'peak_day_hours': int(daily_distribution['hour'].max())
            },
            'hourly_stats': {
                'peak_hour': int(hourly_distribution['task_id'].idxmax()),
                'avg_tasks_per_hour': float(hourly_distribution['task_id'].mean())
            },
            'priority_timeline': priority_timeline.to_dict() if not priority_timeline.empty else {},
            'concentration_index': self._calculate_temporal_concentration()
        }

    def _calculate_temporal_concentration(self) -> float:
        """Calcola indice di concentrazione temporale (0-100)"""

        daily_hours = self.merged_df.groupby('date').size()
        if len(daily_hours) <= 1:
            return 100.0

        # Calcola coefficiente di variazione
        cv = daily_hours.std() / daily_hours.mean() if daily_hours.mean() > 0 else 0

        # Converte in indice di concentrazione (più alto = più concentrato)
        concentration = min(100.0, cv * 50)
        return round(concentration, 2)

    def _analyze_algorithm_performance(self) -> Dict[str, Any]:
        """Analisi performance dell'algoritmo"""

        base_stats = {
            'algorithm': self.algorithm_stats.get('algorithm', 'unknown'),
            'execution_time': self.algorithm_stats.get('execution_time', 0),
            'success_rate': self.algorithm_stats.get('success_rate', 0),
            'tasks_scheduled': len(self.scheduled_tasks),
            'tasks_total': len(self.total_tasks)
        }

        # Calcola metriche di efficienza
        if base_stats['execution_time'] > 0:
            tasks_per_second = len(self.scheduled_tasks) / base_stats['execution_time']
            efficiency_rating = self._rate_algorithm_efficiency(base_stats['execution_time'], len(self.total_tasks))
        else:
            tasks_per_second = 0
            efficiency_rating = 'unknown'

        return {
            **base_stats,
            'tasks_per_second': round(tasks_per_second, 2),
            'efficiency_rating': efficiency_rating,
            'memory_usage': self.algorithm_stats.get('memory_usage', 'unknown'),
            'horizon_extensions': self.algorithm_stats.get('horizon_extensions', 0)
        }

    def _rate_algorithm_efficiency(self, execution_time: float, num_tasks: int) -> str:
        """Valuta l'efficienza dell'algoritmo"""

        if num_tasks == 0:
            return 'unknown'

        time_per_task = execution_time / num_tasks

        if time_per_task < 0.01:
            return 'excellent'
        elif time_per_task < 0.05:
            return 'good'
        elif time_per_task < 0.1:
            return 'fair'
        else:
            return 'poor'

    def _detect_violations(self) -> Dict[str, List]:
        """Rileva violazioni e anomalie"""

        violations = {
            'priority_violations': [],
            'resource_conflicts': [],
            'temporal_anomalies': []
        }

        # Priority violations (già calcolate)
        priority_details = self._calculate_priority_compliance_detailed()
        violations['priority_violations'] = priority_details['violations']

        # Resource conflicts (sovrapposizioni)
        resource_conflicts = self._detect_resource_conflicts()
        violations['resource_conflicts'] = resource_conflicts

        # Temporal anomalies (gap troppo grandi, concentrazioni anomale)
        temporal_anomalies = self._detect_temporal_anomalies()
        violations['temporal_anomalies'] = temporal_anomalies

        return violations

    def _detect_resource_conflicts(self) -> List[Dict]:
        """Rileva conflitti di risorse (sovrapposizioni)"""

        conflicts = []

        # Raggruppa per risorsa, data e ora
        resource_slots = self.merged_df.groupby(['user_id', 'date', 'hour'])['task_id'].apply(list).reset_index()

        # Trova slot con più di un task
        for _, slot in resource_slots.iterrows():
            if len(slot['task_id']) > 1:
                conflicts.append({
                    'user_id': int(slot['user_id']),
                    'date': slot['date'].strftime('%Y-%m-%d'),
                    'hour': int(slot['hour']),
                    'conflicting_tasks': [int(tid) for tid in slot['task_id']]
                })

        return conflicts

    def _detect_temporal_anomalies(self) -> List[Dict]:
        """Rileva anomalie temporali"""

        anomalies = []

        # Gap troppo grandi tra task dello stesso utente
        for user_id in self.merged_df['user_id'].unique():
            user_tasks = self.merged_df[self.merged_df['user_id'] == user_id].copy()
            user_tasks = user_tasks.sort_values(['date', 'hour'])

            # Calcola gap tra task consecutivi
            user_tasks['datetime'] = pd.to_datetime(user_tasks['date'].astype(str) + ' ' + user_tasks['hour'].astype(str) + ':00')

            for i in range(1, len(user_tasks)):
                current = user_tasks.iloc[i]
                previous = user_tasks.iloc[i-1]

                gap_hours = (current['datetime'] - previous['datetime']).total_seconds() / 3600

                # Se gap > 48 ore, potrebbe essere anomalo
                if gap_hours > 48:
                    anomalies.append({
                        'type': 'large_gap',
                        'user_id': int(user_id),
                        'task1': int(previous['task_id']),
                        'task2': int(current['task_id']),
                        'gap_hours': round(gap_hours, 2)
                    })

        return anomalies

    def _generate_recommendations(self) -> List[str]:
        """Genera raccomandazioni per migliorare la schedulazione"""

        recommendations = []

        # Analizza metriche principali
        quality_metrics = self._calculate_quality_metrics()
        priority_analysis = self._analyze_priority_compliance()
        resource_analysis = self._analyze_resource_utilization()

        # Raccomandazioni basate su priority compliance
        if quality_metrics['priority_compliance'] < 80:
            recommendations.append(
                f"Priority Compliance basso ({quality_metrics['priority_compliance']:.1f}%). "
                "Considera di utilizzare algoritmo Priority-First Greedy o aumentare peso priorità."
            )

        # Raccomandazioni basate su resource efficiency
        if quality_metrics['resource_efficiency'] < 60:
            recommendations.append(
                f"Resource Efficiency basso ({quality_metrics['resource_efficiency']:.1f}%). "
                "Riequilibra il carico di lavoro tra le risorse."
            )

        # Raccomandazioni basate su completeness
        if quality_metrics['completeness'] < 90:
            recommendations.append(
                f"Completeness basso ({quality_metrics['completeness']:.1f}%). "
                "Estendi orizzonte temporale o riduci carico di lavoro."
            )

        # Raccomandazioni basate su violazioni
        violations = self._detect_violations()
        if len(violations['resource_conflicts']) > 0:
            recommendations.append(
                f"Rilevati {len(violations['resource_conflicts'])} conflitti di risorse. "
                "Verifica algoritmo di non-sovrapposizione."
            )

        return recommendations

    def _get_priority_recommendations(self, priority_stats: Dict, violations: List) -> List[str]:
        """Raccomandazioni specifiche per le priorità"""

        recommendations = []

        # Analizza completion rate per priorità
        high_completion = priority_stats['high']['completion_rate']
        if high_completion < 95:
            recommendations.append(
                f"Task ad alta priorità completati solo al {high_completion:.1f}%. "
                "Aumenta pre-allocazione per task critici."
            )

        # Analizza violazioni severe
        severe_violations = [v for v in violations if v['late_priority'] - v['early_priority'] > 30]
        if len(severe_violations) > 0:
            recommendations.append(
                f"Rilevate {len(severe_violations)} violazioni severe di priorità. "
                "Rivedi soglie di classificazione priorità."
            )

        return recommendations

    def _empty_profile(self) -> Dict[str, Any]:
        """Profilo vuoto per soluzioni non valide"""
        return {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'error': 'No solution data available'
            },
            'quality_metrics': {
                'sqs': 0.0,
                'completeness': 0.0,
                'priority_compliance': 0.0,
                'resource_efficiency': 0.0
            }
        }

    # Export Methods

    def export_json(self, profile: Dict[str, Any], filename: str = None) -> str:
        """Esporta profilo in formato JSON"""

        if filename is None:
            filename = f"profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = self.output_dir / filename

        # Converte numpy types per JSON serialization
        profile_json = self._convert_numpy_types(profile)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(profile_json, f, indent=2, ensure_ascii=False)

        logger.info(f"📄 Profilo JSON salvato: {filepath}")
        return str(filepath)

    def export_csv(self, profile: Dict[str, Any], filename: str = None) -> str:
        """Esporta metriche principali in formato CSV"""

        if filename is None:
            filename = f"profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        filepath = self.output_dir / filename

        # Estrae metriche principali per CSV
        csv_data = []

        # Quality metrics
        quality = profile.get('quality_metrics', {})
        csv_data.append(['Quality Metric', 'SQS', quality.get('sqs', 0)])
        csv_data.append(['Quality Metric', 'Completeness', quality.get('completeness', 0)])
        csv_data.append(['Quality Metric', 'Priority Compliance', quality.get('priority_compliance', 0)])
        csv_data.append(['Quality Metric', 'Resource Efficiency', quality.get('resource_efficiency', 0)])

        # Priority analysis
        priority = profile.get('priority_analysis', {})
        for priority_class, stats in priority.get('by_priority_class', {}).items():
            csv_data.append(['Priority Class', f'{priority_class}_completion_rate', stats.get('completion_rate', 0)])
            csv_data.append(['Priority Class', f'{priority_class}_compliance_rate', stats.get('compliance_rate', 0)])

        # Algorithm performance
        algorithm = profile.get('algorithm_performance', {})
        csv_data.append(['Algorithm', 'Execution Time', algorithm.get('execution_time', 0)])
        csv_data.append(['Algorithm', 'Tasks Per Second', algorithm.get('tasks_per_second', 0)])
        csv_data.append(['Algorithm', 'Success Rate', algorithm.get('success_rate', 0)])

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Category', 'Metric', 'Value'])
            writer.writerows(csv_data)

        logger.info(f"📊 Profilo CSV salvato: {filepath}")
        return str(filepath)

    def export_html_dashboard(self, profile: Dict[str, Any], filename: str = None) -> str:
        """Esporta dashboard HTML interattivo"""

        if filename is None:
            filename = f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        filepath = self.output_dir / filename

        html_content = self._generate_html_dashboard(profile)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"🌐 Dashboard HTML salvato: {filepath}")
        return str(filepath)

    def _generate_html_dashboard(self, profile: Dict[str, Any]) -> str:
        """Genera HTML dashboard"""

        quality = profile.get('quality_metrics', {})
        priority = profile.get('priority_analysis', {})
        algorithm = profile.get('algorithm_performance', {})

        html = f"""
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Scheduler - Dashboard Profiling</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }}
        .metric-card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #667eea; }}
        .metric-label {{ color: #666; margin-top: 5px; }}
        .section {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .priority-bar {{ height: 20px; background: #e0e0e0; border-radius: 10px; margin: 10px 0; }}
        .priority-fill {{ height: 100%; border-radius: 10px; }}
        .high {{ background: #4CAF50; }}
        .medium {{ background: #FF9800; }}
        .low {{ background: #f44336; }}
        .recommendations {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; }}
        .violation {{ background: #f8d7da; border: 1px solid #f5c6cb; padding: 10px; margin: 5px 0; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Task Scheduler - Dashboard Profiling</h1>
            <p>Generato il {profile.get('metadata', {}).get('timestamp', 'N/A')}</p>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{quality.get('sqs', 0):.1f}%</div>
                <div class="metric-label">Schedule Quality Score</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{quality.get('completeness', 0):.1f}%</div>
                <div class="metric-label">Completeness</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{quality.get('priority_compliance', 0):.1f}%</div>
                <div class="metric-label">Priority Compliance</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{quality.get('resource_efficiency', 0):.1f}%</div>
                <div class="metric-label">Resource Efficiency</div>
            </div>
        </div>

        <div class="section">
            <h2>📊 Analisi Priorità</h2>
            <p>Algoritmo: {algorithm.get('algorithm', 'N/A')}</p>
            <p>Tempo esecuzione: {algorithm.get('execution_time', 0):.2f}s</p>
            <p>Task/secondo: {algorithm.get('tasks_per_second', 0):.1f}</p>
        </div>

        <div class="section">
            <h2>💡 Raccomandazioni</h2>
            <div class="recommendations">
                <p>Dashboard HTML generato con successo!</p>
                <p>Consulta il file JSON per dettagli completi.</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

        return html

    def _convert_numpy_types(self, obj):
        """Converte tipi numpy e pandas per JSON serialization"""
        if isinstance(obj, dict):
            return {str(key): self._convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif hasattr(obj, 'item'):  # numpy types
            return obj.item()
        elif hasattr(obj, 'tolist'):  # numpy arrays
            return obj.tolist()
        elif hasattr(obj, 'isoformat'):  # datetime/timestamp
            return obj.isoformat()
        elif str(type(obj)).startswith('<class \'pandas'):  # pandas types
            return str(obj)
        else:
            return obj
