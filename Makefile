# Task Scheduler - Makefile per test di qualità e benchmark

.PHONY: help test-quality test-performance test-all generate-report clean setup venv

# Configurazione
VENV_DIR = venv
PYTHON = $(VENV_DIR)/bin/python
PIP = $(VENV_DIR)/bin/pip
PYTEST = PYTHONPATH=. $(VENV_DIR)/bin/pytest
REPORTS_DIR = reports
CHARTS_DIR = $(REPORTS_DIR)/charts

# Verifica se siamo su Windows (per adattare i path)
ifeq ($(OS),Windows_NT)
    PYTHON = PYTHONPATH=. $(VENV_DIR)/Scripts/python.exe
    PIP = $(VENV_DIR)/Scripts/pip.exe
    PYTEST = PYTHONPATH=. $(VENV_DIR)/Scripts/pytest.exe
else
    PYTHON = PYTHONPATH=. $(VENV_DIR)/bin/python
endif

help: ## Mostra questo messaggio di aiuto
	@echo "Task Scheduler - Test di Qualità e Performance"
	@echo ""
	@echo "Comandi disponibili:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

venv: ## Crea virtual environment
	@echo "🐍 Creating virtual environment..."
	python3 -m venv $(VENV_DIR)
	@echo "✅ Virtual environment created in $(VENV_DIR)/"
	@echo "💡 To activate manually: source $(VENV_DIR)/bin/activate"

setup: venv ## Installa dipendenze e prepara ambiente
	@echo "🔧 Setting up test environment..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	mkdir -p $(REPORTS_DIR)
	mkdir -p $(CHARTS_DIR)
	mkdir -p logs
	mkdir -p data
	@echo "✅ Setup completed!"
	@echo "💡 Virtual environment ready at $(VENV_DIR)/"

test-quality: ## Esegue test di qualità (100 task scenario)
	@echo "🧪 Running quality tests..."
	$(PYTEST) tests/test_scheduling_quality.py::TestSchedulingQuality::test_100_tasks_production_quality -v -s

test-performance: ## Esegue benchmark di performance per M4
	@echo "🚀 Running performance benchmarks..."
	$(PYTEST) tests/test_scheduling_quality.py::TestPerformanceBenchmarks::test_performance_benchmarks_m4 -v -s

test-priority: ## Test specifico per rispetto priorità
	@echo "🎯 Testing priority compliance..."
	$(PYTEST) tests/test_scheduling_quality.py::TestSchedulingQuality::test_priority_respect_quality -v -s

test-stress: ## Test di stress con 500 task
	@echo "💪 Running stress test..."
	$(PYTEST) tests/test_scheduling_quality.py::TestSchedulingQuality::test_500_tasks_stress_quality -v -s

test-calendar-viz: ## Test con visualizzazioni calendario complete
	@echo "📅 Testing calendar distribution visualization..."
	$(PYTEST) tests/test_scheduling_quality.py::TestCalendarDistributionVisualization::test_calendar_distribution_visualization -v -s

test-all: ## Esegue tutti i test di qualità
	@echo "🔬 Running all quality tests..."
	$(PYTEST) tests/test_scheduling_quality.py -v -s

test-unit: ## Esegue test unitari base
	@echo "⚙️ Running unit tests..."
	$(PYTEST) tests/test_schedule_model.py -v

generate-report: ## Genera report HTML completo
	@echo "📊 Generating comprehensive quality report..."
	$(PYTHON) tests/quality_report_generator.py --output $(REPORTS_DIR)
	@echo "🎉 Report generated in $(REPORTS_DIR)/"

generate-report-production: ## Genera report solo scenario produzione
	@echo "📊 Generating production scenario report..."
	$(PYTHON) tests/quality_report_generator.py --output $(REPORTS_DIR) --scenarios production

generate-report-stress: ## Genera report solo stress test
	@echo "📊 Generating stress test report..."
	$(PYTHON) tests/quality_report_generator.py --output $(REPORTS_DIR) --scenarios stress

test-data-generator: ## Test del generatore dati realistici
	@echo "🎲 Testing data generator..."
	$(PYTHON) tests/realistic_data_generator.py

benchmark-m4: ## Benchmark completo per MacBook Pro M4
	@echo "🏆 Running MacBook Pro M4 benchmarks..."
	@echo "This will test 50, 100, 200 tasks scenarios"
	$(PYTEST) tests/test_scheduling_quality.py::TestPerformanceBenchmarks -v -s
	@echo ""
	@echo "📈 Generating benchmark report..."
	$(PYTHON) tests/quality_report_generator.py --output $(REPORTS_DIR)

quick-test: ## Test rapido (50 task)
	@echo "⚡ Quick quality test..."
	@$(PYTHON) -c "\
from tests.realistic_data_generator import generate_scenario; \
from src.scheduler.model import SchedulingModel; \
from tests.test_scheduling_quality import QualityMetrics; \
import time; \
print('🧪 Quick Test: 50 tasks, 5 resources'); \
tasks_df, calendar_df, leaves_df = generate_scenario('production', num_tasks=50, num_resources=5); \
start = time.time(); \
model = SchedulingModel(tasks_df, calendar_df, leaves_df); \
success = model.solve(); \
exec_time = time.time() - start; \
solution_df = model.get_solution_dataframe() if success else None; \
metrics = QualityMetrics.calculate_schedule_quality_score(solution_df, tasks_df) if success else {}; \
print(f'✅ Success: {exec_time:.2f}s') if success else print('❌ Failed'); \
print(f'📊 SQS: {metrics.get(\"sqs\", 0):.1f}%') if success else None; \
print(f'📈 Completeness: {metrics.get(\"completeness\", 0):.1f}%') if success else None; \
print(f'🎯 Priority Compliance: {metrics.get(\"priority_compliance\", 0):.1f}%') if success else None"

demo: ## Demo completo con visualizzazioni
	@echo "🎬 Running complete demo..."
	@$(PYTHON) -c "\
from tests.quality_report_generator import QualityReportGenerator; \
print('🚀 Generating demo report with all scenarios...'); \
generator = QualityReportGenerator('$(REPORTS_DIR)'); \
scenarios = [ \
    {'name': 'Demo Small', 'type': 'production', 'tasks': 50, 'resources': 5}, \
    {'name': 'Demo Medium', 'type': 'production', 'tasks': 100, 'resources': 8}, \
    {'name': 'Demo Large', 'type': 'high_load', 'tasks': 150, 'resources': 10} \
]; \
report_path = generator.generate_comprehensive_report(scenarios); \
print(f'🎉 Demo report: {report_path}'); \
print(f'🌐 Open: file://{report_path}')"

clean: ## Pulisce file temporanei e report
	@echo "🧹 Cleaning up..."
	rm -rf $(REPORTS_DIR)/*
	rm -rf logs/*.log
	rm -rf data/*.json
	rm -rf data/*.png
	rm -rf data/*.html
	rm -rf __pycache__
	rm -rf tests/__pycache__
	rm -rf src/__pycache__
	rm -rf src/scheduler/__pycache__
	find . -name "*.pyc" -delete
	@echo "✅ Cleanup completed!"

clean-all: clean ## Pulisce tutto incluso virtualenv
	@echo "🧹 Deep cleaning (including virtual environment)..."
	rm -rf $(VENV_DIR)
	@echo "✅ Deep cleanup completed!"

install-dev: venv ## Installa dipendenze di sviluppo
	@echo "🔧 Installing development dependencies..."
	$(PIP) install pytest pytest-cov flake8 black isort
	@echo "✅ Development dependencies installed!"

lint: ## Esegue controlli di stile del codice
	@echo "🔍 Running code style checks..."
	flake8 src/ tests/ --max-line-length=130 --ignore=E203,W503
	@echo "✅ Code style checks completed!"

format: ## Formatta il codice
	@echo "🎨 Formatting code..."
	black src/ tests/ --line-length=130
	isort src/ tests/
	@echo "✅ Code formatting completed!"

coverage: ## Esegue test con coverage
	@echo "📊 Running tests with coverage..."
	$(PYTEST) tests/ --cov=src --cov-report=html --cov-report=term
	@echo "📄 Coverage report: htmlcov/index.html"

docker-test: ## Esegue test in container Docker
	@echo "🐳 Running tests in Docker..."
	docker-compose exec task-scheduler-api $(PYTEST) tests/test_scheduling_quality.py -v

docker-report: ## Genera report in container Docker
	@echo "🐳 Generating report in Docker..."
	docker-compose exec task-scheduler-api python tests/quality_report_generator.py --output /app/data

ci-test: setup lint test-all ## Pipeline completa per CI/CD
	@echo "🚀 CI/CD pipeline completed!"

profile-demo: ## Demo completo del sistema di profilazione
	@echo "🔍 Demo Sistema di Profilazione Centralizzato..."
	$(PYTHON) src/scheduler/profile_example.py

profile-quick: ## Profilazione rapida con quick-test
	@echo "🔍 Profilazione rapida..."
	@$(PYTHON) -c "\
from src.scheduler.profiler import SchedulingProfiler; \
from src.scheduler.model import SchedulingModel; \
from tests.realistic_data_generator import generate_scenario; \
print('🧪 Profilazione Quick Test: 30 task, 3 risorse'); \
tasks_df, calendar_df, leaves_df = generate_scenario('production', num_tasks=30, num_resources=3); \
model = SchedulingModel(tasks_df, calendar_df, leaves_df); \
success = model.solve(); \
if success: \
    solution_df = model.get_solution_dataframe(); \
    stats = model.get_solver_statistics(); \
    profiler = SchedulingProfiler('$(REPORTS_DIR)'); \
    profile = profiler.profile_solution(solution_df, tasks_df, stats); \
    quality = profile['quality_metrics']; \
    print(f'📊 SQS: {quality[\"sqs\"]:.1f}% | Completeness: {quality[\"completeness\"]:.1f}% | Priority: {quality[\"priority_compliance\"]:.1f}%'); \
    json_file = profiler.export_json(profile, 'quick_profile.json'); \
    print(f'💾 Report salvato: {json_file}'); \
else: \
    print('❌ Scheduling fallito')"

profile-priority: ## Profilazione specifica per priorità
	@echo "🎯 Profilazione Priority Compliance..."
	@$(PYTHON) -c "\
from src.scheduler.profiler import SchedulingProfiler; \
from src.scheduler.model import SchedulingModel; \
import pandas as pd; \
print('🧪 Test Priority Compliance: 20 task con priorità definite'); \
tasks_data = []; \
for i in range(1, 21): \
    priority = 90.0 if i <= 5 else (60.0 if i <= 12 else 30.0); \
    tasks_data.append({'id': i, 'name': f'Task_{i:02d}', 'user_id': (i % 3) + 1, 'remaining_hours': 4.0, 'priority_score': priority}); \
tasks_df = pd.DataFrame(tasks_data); \
calendar_data = []; \
for task_id in range(1, 21): \
    for day in range(5): \
        calendar_data.append({'task_id': task_id, 'dayofweek': day, 'hour_from': 9, 'hour_to': 17}); \
calendar_df = pd.DataFrame(calendar_data); \
leaves_df = pd.DataFrame(); \
model = SchedulingModel(tasks_df, calendar_df, leaves_df); \
success = model.solve(); \
if success: \
    solution_df = model.get_solution_dataframe(); \
    stats = model.get_solver_statistics(); \
    profiler = SchedulingProfiler('$(REPORTS_DIR)'); \
    profile = profiler.profile_solution(solution_df, tasks_df, stats); \
    priority_analysis = profile['priority_analysis']; \
    print(f'🎯 Priority Compliance: {priority_analysis[\"overall_compliance\"]:.1f}%'); \
    for pclass, pstats in priority_analysis['by_priority_class'].items(): \
        print(f'   {pclass.upper()}: {pstats[\"completion_rate\"]:.1f}% completati, {pstats[\"compliance_rate\"]:.1f}% compliance'); \
    violations = profile['violations']['priority_violations']; \
    print(f'⚠️ Violazioni priorità: {len(violations)}'); \
    csv_file = profiler.export_csv(profile, 'priority_analysis.csv'); \
    print(f'💾 Analisi salvata: {csv_file}'); \
else: \
    print('❌ Scheduling fallito')"

profile-dashboard: ## Genera dashboard HTML completo
	@echo "🌐 Generazione Dashboard HTML..."
	@$(PYTHON) -c "\
from src.scheduler.profiler import SchedulingProfiler; \
from src.scheduler.model import SchedulingModel; \
from tests.realistic_data_generator import generate_scenario; \
print('🌐 Generazione Dashboard: 100 task scenario produzione'); \
tasks_df, calendar_df, leaves_df = generate_scenario('production', num_tasks=100, num_resources=8); \
model = SchedulingModel(tasks_df, calendar_df, leaves_df); \
success = model.solve(); \
if success: \
    solution_df = model.get_solution_dataframe(); \
    stats = model.get_solver_statistics(); \
    profiler = SchedulingProfiler('$(REPORTS_DIR)'); \
    profile = profiler.profile_solution(solution_df, tasks_df, stats); \
    html_file = profiler.export_html_dashboard(profile, 'dashboard.html'); \
    json_file = profiler.export_json(profile, 'dashboard_data.json'); \
    print(f'🌐 Dashboard HTML: {html_file}'); \
    print(f'📄 Dati JSON: {json_file}'); \
    print(f'💡 Apri: file://{html_file}'); \
else: \
    print('❌ Scheduling fallito')"

profile-compare: ## Confronta Greedy vs OrTools
	@echo "⚖️ Confronto Algoritmi: Greedy vs OrTools..."
	@echo "🔄 Test in corso... (può richiedere tempo)"
	@$(PYTHON) -c "\
from src.scheduler.profiler import SchedulingProfiler; \
from src.scheduler.model import SchedulingModel; \
from tests.realistic_data_generator import generate_scenario; \
import json; \
print('⚖️ Confronto Greedy vs OrTools: 80 task'); \
tasks_df, calendar_df, leaves_df = generate_scenario('production', num_tasks=80, num_resources=6); \
profiler = SchedulingProfiler('$(REPORTS_DIR)'); \
results = {}; \
for algo_name in ['Greedy', 'OrTools']: \
    print(f'🧪 Test {algo_name}...'); \
    model = SchedulingModel(tasks_df, calendar_df, leaves_df); \
    success = model.solve(); \
    if success: \
        solution_df = model.get_solution_dataframe(); \
        stats = model.get_solver_statistics(); \
        profile = profiler.profile_solution(solution_df, tasks_df, stats); \
        results[algo_name] = profile['quality_metrics']; \
        results[algo_name]['algorithm'] = stats.get('algorithm', 'unknown'); \
        results[algo_name]['execution_time'] = stats.get('execution_time', 0); \
    else: \
        results[algo_name] = {'error': 'Scheduling failed'}; \
print('\\n📊 CONFRONTO RISULTATI:'); \
print('=' * 50); \
for algo, metrics in results.items(): \
    if 'error' not in metrics: \
        print(f'{algo:>8}: SQS={metrics[\"sqs\"]:5.1f}% | Priority={metrics[\"priority_compliance\"]:5.1f}% | Time={metrics[\"execution_time\"]:6.3f}s'); \
    else: \
        print(f'{algo:>8}: {metrics[\"error\"]}'); \
with open('$(REPORTS_DIR)/algorithm_comparison.json', 'w') as f: \
    json.dump(results, f, indent=2); \
print('💾 Confronto salvato: $(REPORTS_DIR)/algorithm_comparison.json')"

info: ## Mostra informazioni sistema
	@echo "📋 System Information:"
	@echo "Python: $(shell python3 --version)"
	@echo "Platform: $(shell python3 -c 'import platform; print(platform.platform())')"
	@echo "CPU: $(shell python3 -c 'import platform; print(platform.processor())')"
	@echo "Working Directory: $(shell pwd)"
	@echo "Reports Directory: $(REPORTS_DIR)"
	@echo "Virtual Environment: $(VENV_DIR)"

.DEFAULT_GOAL := help
