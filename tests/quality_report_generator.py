"""
Generatore di report HTML per i test di qualità del sistema di scheduling
"""
import os
import json
import time
from datetime import datetime
from pathlib import Path

from src.scheduler.model import SchedulingModel
from src.scheduler.visualization import ScheduleVisualizer
from tests.realistic_data_generator import generate_scenario, print_scenario_stats
from tests.test_scheduling_quality import QualityMetrics


class QualityReportGenerator:
    """Generatore di report HTML per test di qualità"""

    def __init__(self, output_dir="reports"):
        """
        Inizializza il generatore di report

        Args:
            output_dir: Directory per salvare i report
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Crea sottodirectory per i grafici
        self.charts_dir = self.output_dir / "charts"
        self.charts_dir.mkdir(exist_ok=True)

    def generate_comprehensive_report(self, scenarios=None):
        """
        Genera report completo con tutti gli scenari

        Args:
            scenarios: Lista di scenari da testare, default tutti

        Returns:
            str: Percorso del report generato
        """
        if scenarios is None:
            scenarios = [
                {'name': 'Production', 'type': 'production', 'tasks': 100, 'resources': 10},
                {'name': 'High Load', 'type': 'high_load', 'tasks': 200, 'resources': 10},
                {'name': 'Stress Test', 'type': 'stress', 'tasks': 500, 'resources': 10}
            ]

        print("🚀 Generating comprehensive quality report...")

        # Esegui test per ogni scenario
        results = []
        for scenario in scenarios:
            print(f"\n📊 Testing scenario: {scenario['name']}")
            result = self._test_scenario(scenario)
            results.append(result)

        # Genera report HTML
        report_path = self._generate_html_report(results)

        print(f"\n✅ Report generated: {report_path}")
        return str(report_path)

    def _test_scenario(self, scenario):
        """Esegue test per un singolo scenario"""
        # Genera dati
        tasks_df, calendar_slots_df, leaves_df = generate_scenario(
            scenario['type'],
            num_tasks=scenario['tasks'],
            num_resources=scenario['resources']
        )

        # Statistiche scenario
        scenario_stats = {
            'total_tasks': len(tasks_df),
            'total_resources': tasks_df['user_id'].nunique(),
            'total_hours': tasks_df['remaining_hours'].sum(),
            'avg_hours_per_task': tasks_df['remaining_hours'].mean(),
            'calendar_slots': len(calendar_slots_df),
            'leaves': len(leaves_df)
        }

        # Distribuzione priorità
        high_priority = len(tasks_df[tasks_df['priority_score'] >= 80])
        med_priority = len(tasks_df[(tasks_df['priority_score'] >= 40) & (tasks_df['priority_score'] < 80)])
        low_priority = len(tasks_df[tasks_df['priority_score'] < 40])

        priority_distribution = {
            'high': {'count': high_priority, 'percentage': high_priority/len(tasks_df)*100},
            'medium': {'count': med_priority, 'percentage': med_priority/len(tasks_df)*100},
            'low': {'count': low_priority, 'percentage': low_priority/len(tasks_df)*100}
        }

        # Esegui scheduling
        start_time = time.time()
        model = SchedulingModel(tasks_df, calendar_slots_df, leaves_df)
        success = model.solve()
        execution_time = time.time() - start_time

        # Calcola metriche qualità
        quality_metrics = {'sqs': 0.0, 'completeness': 0.0, 'priority_compliance': 0.0, 'resource_efficiency': 0.0}
        solution_df = None
        charts_paths = {}

        if success:
            solution_df = model.get_solution_dataframe()
            if solution_df is not None and not solution_df.empty:
                quality_metrics = QualityMetrics.calculate_schedule_quality_score(solution_df, tasks_df)

                # Genera grafici
                try:
                    visualizer = ScheduleVisualizer(solution_df, tasks_df, str(self.charts_dir))
                    charts_paths = visualizer.generate_all_charts()
                except Exception as e:
                    print(f"⚠️  Warning: Could not generate charts: {str(e)}")

        # Statistiche solver
        solver_stats = {}
        if hasattr(model, 'get_solver_statistics'):
            try:
                solver_stats = model.get_solver_statistics()
            except:
                pass

        return {
            'scenario': scenario,
            'scenario_stats': scenario_stats,
            'priority_distribution': priority_distribution,
            'execution_time': execution_time,
            'success': success,
            'quality_metrics': quality_metrics,
            'solver_stats': solver_stats,
            'charts_paths': charts_paths,
            'solution_df': solution_df
        }

    def _generate_html_report(self, results):
        """Genera report HTML completo"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Calcola statistiche generali
        total_scenarios = len(results)
        successful_scenarios = sum(1 for r in results if r['success'])
        avg_sqs = sum(r['quality_metrics']['sqs'] for r in results if r['success']) / max(successful_scenarios, 1)

        html_content = f"""
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Scheduler - Quality Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .summary-card .value {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}
        .summary-card .unit {{
            font-size: 0.8em;
            color: #666;
        }}
        .scenarios {{
            padding: 30px;
        }}
        .scenario {{
            margin-bottom: 40px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            overflow: hidden;
        }}
        .scenario-header {{
            background: #f8f9fa;
            padding: 20px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .scenario-title {{
            margin: 0;
            color: #333;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .status-badge {{
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        .status-success {{
            background: #d4edda;
            color: #155724;
        }}
        .status-failure {{
            background: #f8d7da;
            color: #721c24;
        }}
        .scenario-content {{
            padding: 20px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .metric {{
            text-align: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 6px;
        }}
        .metric-value {{
            font-size: 1.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .metric-label {{
            font-size: 0.8em;
            color: #666;
            text-transform: uppercase;
        }}
        .sqs-excellent {{ color: #28a745; }}
        .sqs-good {{ color: #ffc107; }}
        .sqs-poor {{ color: #dc3545; }}
        .charts-section {{
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        }}
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}
        .chart-container {{
            text-align: center;
        }}
        .chart-container img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .chart-title {{
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }}
        .details-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        .details-table th,
        .details-table td {{
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}
        .details-table th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Task Scheduler Quality Report</h1>
            <p>Generated on {timestamp}</p>
        </div>

        <div class="summary">
            <div class="summary-card">
                <h3>Scenarios Tested</h3>
                <div class="value">{total_scenarios}</div>
            </div>
            <div class="summary-card">
                <h3>Success Rate</h3>
                <div class="value">{successful_scenarios}/{total_scenarios}</div>
                <div class="unit">({successful_scenarios/total_scenarios*100:.1f}%)</div>
            </div>
            <div class="summary-card">
                <h3>Average SQS</h3>
                <div class="value">{avg_sqs:.1f}</div>
                <div class="unit">%</div>
            </div>
        </div>

        <div class="scenarios">
"""

        # Aggiungi sezione per ogni scenario
        for result in results:
            html_content += self._generate_scenario_section(result)

        html_content += """
        </div>

        <div class="footer">
            <p>Generated by Task Scheduler Quality Test Suite</p>
            <p>MacBook Pro M4 Performance Benchmarks</p>
        </div>
    </div>
</body>
</html>
"""

        # Salva report
        report_path = self.output_dir / f"quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return report_path

    def _generate_scenario_section(self, result):
        """Genera sezione HTML per un singolo scenario"""
        scenario = result['scenario']
        success = result['success']
        quality = result['quality_metrics']
        stats = result['scenario_stats']
        priority_dist = result['priority_distribution']

        # Determina classe CSS per SQS
        sqs_class = 'sqs-excellent' if quality['sqs'] >= 80 else 'sqs-good' if quality['sqs'] >= 60 else 'sqs-poor'

        # Status badge
        status_class = 'status-success' if success else 'status-failure'
        status_text = '✅ SUCCESS' if success else '❌ FAILED'

        html = f"""
        <div class="scenario">
            <div class="scenario-header">
                <h2 class="scenario-title">
                    {scenario['name']} Scenario ({scenario['tasks']} tasks, {scenario['resources']} resources)
                    <span class="status-badge {status_class}">{status_text}</span>
                </h2>
            </div>
            <div class="scenario-content">
"""

        if success:
            html += f"""
                <div class="metrics-grid">
                    <div class="metric">
                        <div class="metric-value {sqs_class}">{quality['sqs']:.1f}%</div>
                        <div class="metric-label">Schedule Quality Score</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{quality['completeness']:.1f}%</div>
                        <div class="metric-label">Completeness</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{quality['priority_compliance']:.1f}%</div>
                        <div class="metric-label">Priority Compliance</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{quality['resource_efficiency']:.1f}%</div>
                        <div class="metric-label">Resource Efficiency</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{result['execution_time']:.2f}s</div>
                        <div class="metric-label">Execution Time</div>
                    </div>
                </div>
"""

        # Tabella dettagli scenario
        html += f"""
                <table class="details-table">
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Tasks</td><td>{stats['total_tasks']}</td></tr>
                    <tr><td>Total Resources</td><td>{stats['total_resources']}</td></tr>
                    <tr><td>Total Hours</td><td>{stats['total_hours']:.1f}</td></tr>
                    <tr><td>Avg Hours per Task</td><td>{stats['avg_hours_per_task']:.1f}</td></tr>
                    <tr><td>Calendar Slots</td><td>{stats['calendar_slots']}</td></tr>
                    <tr><td>Leaves</td><td>{stats['leaves']}</td></tr>
                    <tr><td>High Priority Tasks</td><td>{priority_dist['high']['count']} ({priority_dist['high']['percentage']:.1f}%)</td></tr>
                    <tr><td>Medium Priority Tasks</td><td>{priority_dist['medium']['count']} ({priority_dist['medium']['percentage']:.1f}%)</td></tr>
                    <tr><td>Low Priority Tasks</td><td>{priority_dist['low']['count']} ({priority_dist['low']['percentage']:.1f}%)</td></tr>
                </table>
"""

        # Sezione grafici
        if success and result['charts_paths']:
            html += """
                <div class="charts-section">
                    <h3>📈 Visualizations</h3>
                    <div class="charts-grid">
"""

            charts = result['charts_paths']
            if 'gantt_chart' in charts and charts['gantt_chart']:
                chart_name = os.path.basename(charts['gantt_chart'])
                html += f"""
                        <div class="chart-container">
                            <div class="chart-title">📅 Gantt Chart</div>
                            <img src="charts/{chart_name}" alt="Gantt Chart">
                        </div>
"""

            if 'resource_utilization' in charts and charts['resource_utilization']:
                chart_name = os.path.basename(charts['resource_utilization'])
                html += f"""
                        <div class="chart-container">
                            <div class="chart-title">👥 Resource Utilization</div>
                            <img src="charts/{chart_name}" alt="Resource Utilization">
                        </div>
"""

            if 'task_distribution' in charts and charts['task_distribution']:
                chart_name = os.path.basename(charts['task_distribution'])
                html += f"""
                        <div class="chart-container">
                            <div class="chart-title">📊 Task Distribution</div>
                            <img src="charts/{chart_name}" alt="Task Distribution">
                        </div>
"""

            if 'timeline_chart' in charts and charts['timeline_chart']:
                chart_name = os.path.basename(charts['timeline_chart'])
                html += f"""
                        <div class="chart-container">
                            <div class="chart-title">⏱️ Interactive Timeline</div>
                            <p><a href="charts/{chart_name}" target="_blank">🔗 Open Interactive Timeline</a></p>
                        </div>
"""

            html += """
                    </div>
                </div>
"""

        html += """
            </div>
        </div>
"""

        return html


def main():
    """Funzione principale per generare report"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate quality report for Task Scheduler')
    parser.add_argument('--output', '-o', default='reports', help='Output directory')
    parser.add_argument('--scenarios', '-s', nargs='+',
                       choices=['production', 'high_load', 'stress'],
                       default=['production', 'high_load', 'stress'],
                       help='Scenarios to test')

    args = parser.parse_args()

    # Mappa scenari
    scenario_configs = {
        'production': {'name': 'Production', 'type': 'production', 'tasks': 100, 'resources': 10},
        'high_load': {'name': 'High Load', 'type': 'high_load', 'tasks': 200, 'resources': 10},
        'stress': {'name': 'Stress Test', 'type': 'stress', 'tasks': 500, 'resources': 10}
    }

    scenarios = [scenario_configs[s] for s in args.scenarios]

    # Genera report
    generator = QualityReportGenerator(args.output)
    report_path = generator.generate_comprehensive_report(scenarios)

    print(f"\n🎉 Quality report generated successfully!")
    print(f"📄 Report: {report_path}")
    print(f"🌐 Open in browser: file://{os.path.abspath(report_path)}")


if __name__ == '__main__':
    main()
