# Task Scheduler Ibrido con OrTools

Un sistema di pianificazione delle attività ottimizzato che utilizza un approccio ibrido (Greedy + OrTools) per l'allocazione intelligente delle risorse e la pianificazione automatica delle attività. Progettato per integrarsi con sistemi esterni tramite API REST.

## 🚀 Caratteristiche Principali

- **Algoritmo Ibrido**: Combina algoritmo Greedy (per performance) e OrTools CP-SAT (per ottimizzazione avanzata)
- **API REST Completa** per integrazione con sistemi esterni (Odoo, ERP, etc.)
- **Pianificazione Automatica** basata su vincoli complessi e calendari di lavoro
- **Gestione Assenze** e calendari personalizzati per ogni risorsa
- **Estensione Automatica dell'Orizzonte** temporale per garantire soluzioni fattibili
- **Visualizzazioni Grafiche** con diagrammi di Gantt, timeline interattive e report HTML
- **Containerizzazione Docker** completa per deployment semplificato
- **Shell Interattiva** per controllo e monitoraggio in tempo reale

## 📋 Requisiti

- Docker e Docker Compose
- Python 3.11+ (se eseguito senza Docker)
- Accesso a database PostgreSQL (per integrazione con Odoo o altri sistemi)

## 🏗️ Architettura del Sistema

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Sistema       │    │   Task Scheduler │    │   Risultati     │
│   Esterno       │───▶│   API REST       │───▶│   JSON/HTML     │
│   (Odoo/ERP)    │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Algoritmo       │
                       │  Ibrido          │
                       │                  │
                       │ ┌──────────────┐ │
                       │ │   Greedy     │ │◀── Per molti task
                       │ │  (Performance)│ │    (>50 task)
                       │ └──────────────┘ │
                       │                  │
                       │ ┌──────────────┐ │
                       │ │   OrTools    │ │◀── Per ottimizzazione
                       │ │  (CP-SAT)    │ │    complessa
                       │ └──────────────┘ │
                       └──────────────────┘
```

## 🔧 Struttura del Progetto

```
task_scheduler/
├── src/                           # Codice sorgente principale
│   ├── __init__.py
│   ├── run.py                     # Shell interattiva e punto di ingresso
│   ├── run_api.py                 # Server API REST
│   ├── api.py                     # Endpoint e logica API
│   ├── config.py                  # Configurazioni sistema
│   ├── db.py                      # Gestione connessioni database
│   ├── fetch.py                   # Recupero dati da database esterni
│   └── scheduler/                 # Logica di scheduling
│       ├── __init__.py
│       ├── model.py               # Modello ibrido principale
│       ├── greedy_model.py        # Algoritmo Greedy
│       ├── interval_model.py      # Modello OrTools CP-SAT
│       ├── utils.py               # Funzioni di utilità
│       └── visualization.py       # Generazione grafici
├── tests/                         # Test unitari
│   └── test_schedule_model.py
├── logs/                          # Directory per i log
├── data/                          # Directory per output JSON/HTML
├── _tmp/                          # File temporanei e di lavoro
├── Dockerfile                     # Configurazione container
├── docker-compose.yml             # Orchestrazione servizi
├── requirements.txt               # Dipendenze Python
├── setup.py                       # Setup del pacchetto
├── .env.example                   # Template configurazione
├── .gitignore
└── README.md
```

## 🛠️ Installazione e Configurazione

### 1. Clone del Repository

```bash
git clone https://github.com/2zx/task_scheduler.git
cd task_scheduler
```

### 2. Configurazione Ambiente

```bash
cp .env.example .env
```

Modifica il file `.env` con le tue configurazioni:

```env
# Database Configuration (per integrazione con sistemi esterni)
DB_HOST=your-database-host
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_user
DB_PASSWORD=your_password

# SSH Tunnel (opzionale per database remoti)
SSH_ENABLED=false
SSH_HOST=
SSH_USERNAME=
SSH_KEY_PATH=/app/ssh_key

# OrTools Configuration
ORTOOLS_TIME_LIMIT=30
ORTOOLS_WORKERS=4
ORTOOLS_LOG_PROGRESS=false

# Scheduler Hybrid Configuration
GREEDY_THRESHOLD_TASKS=50          # Soglia per usare Greedy
GREEDY_THRESHOLD_HOURS=1000        # Soglia ore totali per Greedy
HYBRID_MODE=true                   # Abilita modalità ibrida
MAX_HORIZON_DAYS=1825              # Orizzonte massimo (5 anni)

# Logging
LOG_LEVEL=INFO
```

### 3. Avvio con Docker

```bash
# Avvia il servizio API
docker-compose up -d task-scheduler-api

# Verifica che il servizio sia attivo
curl http://localhost:5050/api/v1/schedule/status
```

## 🎯 Utilizzo

### API REST

Il sistema espone un'API REST completa per l'integrazione con sistemi esterni:

#### 1. Avvia una Pianificazione

```bash
POST http://localhost:5050/api/v1/schedule
Content-Type: application/json

{
  "tasks": [
    {
      "id": 1,
      "name": "Task Esempio",
      "user_id": 10,
      "remaining_hours": 8.0
    }
  ],
  "calendar_slots": [
    {
      "task_id": 1,
      "dayofweek": 0,
      "hour_from": 9.0,
      "hour_to": 17.0
    }
  ],
  "leaves": [],
  "initial_horizon_days": 28,
  "horizon_extension_factor": 1.25
}
```

#### 2. Verifica lo Stato

```bash
GET http://localhost:5050/api/v1/schedule/status
```

#### 3. Recupera i Risultati

```bash
GET http://localhost:5050/api/v1/schedule/result
```

### Shell Interattiva

Per controllo diretto e debugging:

```bash
# Accedi alla shell interattiva
docker-compose exec task-scheduler-api python -m src.run

# Comandi disponibili:
scheduler> run          # Esegue pianificazione con dati da database
scheduler> status       # Mostra stato del sistema
scheduler> list         # Elenca task pendenti
scheduler> exit         # Esce dall'applicazione
```

## 🧠 Algoritmo Ibrido

### Strategia di Selezione

Il sistema sceglie automaticamente l'algoritmo più appropriato:

```python
# Criteri per algoritmo Greedy (performance):
- Numero task > 50
- Ore totali > 1000
- Numero utenti > 10
- Media ore per task > 100

# Altrimenti usa OrTools (ottimizzazione)
```

### Algoritmo Greedy

- **Vantaggi**: Velocità estrema, scalabilità lineare
- **Uso**: Grandi volumi di task (>50), scenari di produzione
- **Strategia**: Priorità + disponibilità temporale

### Algoritmo OrTools CP-SAT

- **Vantaggi**: Ottimizzazione matematica, soluzioni ottimali
- **Uso**: Task complessi, vincoli articolati, piccoli volumi
- **Strategia**: Constraint Programming con estensione automatica dell'orizzonte

### Fallback Intelligente

```python
# Flusso ibrido:
1. Greedy per task principali
2. OrTools per task residui (se <20)
3. Fallback completo a OrTools se Greedy fallisce
```

## 📊 Formato Dati

### Input Task

```json
{
  "id": 123,
  "name": "Nome Task",
  "user_id": 10,
  "remaining_hours": 8.0,
  "priority_score": 50.0  // Opzionale, default 50.0
}
```

### Input Calendar Slots

```json
{
  "task_id": 123,
  "dayofweek": 0,        // 0=Lunedì, 6=Domenica
  "hour_from": 9.0,
  "hour_to": 17.0
}
```

### Input Leaves (Assenze)

```json
{
  "task_id": 123,
  "date_from": "2025-06-10",
  "date_to": "2025-06-12"
}
```

### Output Pianificazione

```json
{
  "tasks": {
    "123": [
      {"date": "2025-06-24", "hour": 9},
      {"date": "2025-06-24", "hour": 10}
    ]
  },
  "objective_value": 15,
  "status": "OPTIMAL",
  "solve_time": 2.34,
  "horizon_days": 28,
  "algorithm_used": "greedy"
}
```

## 📈 Visualizzazioni

Il sistema genera automaticamente:

### Grafici Disponibili

1. **📅 Diagramma di Gantt** (`gantt_chart.png`)
   - Visualizzazione temporale delle attività
   - Colori per task e utenti

2. **⏱️ Timeline Interattiva** (`timeline_chart.html`)
   - Grafico Plotly interattivo
   - Zoom, pan, hover per dettagli

3. **👥 Utilizzo Risorse** (`resource_utilization.png`)
   - Ore per utente per giorno
   - Identificazione sovraccarichi

4. **📊 Distribuzione Task** (`task_distribution.png`)
   - Statistiche ore e giorni per task
   - Confronto pianificato vs programmato

5. **📋 Report HTML Completo** (`scheduling_report.html`)
   - Tutti i grafici in un unico report
   - Statistiche e metriche dettagliate

### Output Directory

```
/app/data/
├── schedule.json              # Risultati JSON
├── gantt_chart.png           # Diagramma di Gantt
├── timeline_chart.html       # Timeline interattiva
├── resource_utilization.png  # Utilizzo risorse
├── task_distribution.png     # Distribuzione task
└── scheduling_report.html    # Report completo
```

## ⚙️ Configurazione Avanzata

### Parametri Algoritmo Ibrido

```env
# Soglie per selezione algoritmo
GREEDY_THRESHOLD_TASKS=50          # Numero task per Greedy
GREEDY_THRESHOLD_HOURS=1000        # Ore totali per Greedy
GREEDY_THRESHOLD_USERS=10          # Numero utenti per Greedy
GREEDY_THRESHOLD_AVG_HOURS=100     # Media ore/task per Greedy

# Timeout OrTools
ORTOOLS_TIMEOUT_SECONDS=30         # Timeout normale
ORTOOLS_FALLBACK_TIMEOUT=60        # Timeout fallback

# Modalità ibrida
HYBRID_MODE=true                   # Abilita/disabilita ibrido
```

### Parametri Orizzonte Temporale

```env
# Orizzonte temporale massimo
MAX_HORIZON_DAYS=1825              # 5 anni (default)

# Estensione automatica (solo OrTools)
# initial_horizon_days=28          # Configurabile via API
# horizon_extension_factor=1.25    # Configurabile via API
```

### Parametri Performance

```env
# OrTools
ORTOOLS_TIME_LIMIT=30              # Timeout per iterazione
ORTOOLS_WORKERS=4                  # Worker paralleli

# Logging
LOG_LEVEL=INFO                     # DEBUG per dettagli
ORTOOLS_LOG_PROGRESS=false         # Log progresso solver
```

## 🐳 Docker

### Servizi Disponibili

```yaml
# docker-compose.yml
services:
  task-scheduler-api:
    build: .
    ports:
      - "5050:5000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=INFO
```

### Comandi Docker

```bash
# Build e avvio
docker-compose up -d

# Log in tempo reale
docker-compose logs -f task-scheduler-api

# Shell interattiva
docker-compose exec task-scheduler-api python -m src.run

# Restart servizio
docker-compose restart task-scheduler-api

# Stop e cleanup
docker-compose down
```

## 🧪 Testing, Benchmark e Profilazione

### Sistema di Profilazione Centralizzato

Il sistema include un **profiler centralizzato** (`src/scheduler/profiler.py`) che fornisce analisi dettagliate di qualità, priorità, risorse e performance per qualsiasi soluzione di scheduling.

#### 🎯 Comandi di Profilazione

```bash
# Demo completo del sistema di profilazione
make profile-demo

# Profilazione rapida (30 task, 3 risorse)
make profile-quick

# Analisi specifica priority compliance
make profile-priority

# Dashboard HTML completo (100 task)
make profile-dashboard

# Confronto algoritmi Greedy vs OrTools
make profile-compare
```

#### 📊 Metriche Centralizzate

Il profiler analizza automaticamente:

**Quality Metrics**
- **SQS (Schedule Quality Score)**: Metrica principale combinata
- **Completeness**: Percentuale task schedulati
- **Priority Compliance**: Rispetto ordine priorità (dettagliato per fascia)
- **Resource Efficiency**: Bilanciamento utilizzo risorse

**Priority Analysis** (Focus principale)
- Analisi per fascia: Alta (≥80), Media (50-79), Bassa (<50)
- Violazioni specifiche con dettagli temporali
- Compliance rate per ogni classe di priorità
- Raccomandazioni automatiche per miglioramenti

**Resource Analysis**
- Statistiche per risorsa (task, ore, priorità media)
- Bilanciamento del carico di lavoro
- Utilizzo giornaliero e picchi

**Temporal Analysis**
- Distribuzione temporale delle attività
- Concentrazione e gap temporali
- Anomalie nella pianificazione

**Algorithm Performance**
- Tempo di esecuzione e velocità (task/secondo)
- Efficienza algoritmo (excellent/good/fair/poor)
- Statistiche memoria e estensioni orizzonte

**Violations Detection**
- Conflitti di risorse (sovrapposizioni)
- Violazioni di priorità con severity
- Anomalie temporali (gap > 48h)

#### 🚀 Utilizzo del Profiler

**API Programmatica**
```python
from src.scheduler.profiler import SchedulingProfiler

# Inizializza profiler
profiler = SchedulingProfiler(output_dir="reports")

# Profila una soluzione completa
profile = profiler.profile_solution(solution_df, tasks_df, algorithm_stats)

# Export in multipli formati
json_file = profiler.export_json(profile)           # Dati completi
csv_file = profiler.export_csv(profile)             # Metriche principali
html_file = profiler.export_html_dashboard(profile) # Dashboard visuale
```

**Esempio Output**
```
📈 RISULTATI PROFILAZIONE
🎯 Schedule Quality Score: 86.8%
📊 Completeness: 98.0%
🔥 Priority Compliance: 77.8%
⚖️ Resource Efficiency: 82.5%

🎯 ANALISI PRIORITÀ
HIGH: 10/10 task (100.0% completati, 95.1% compliance)
MEDIUM: 15/15 task (100.0% completati, 87.7% compliance)
LOW: 24/25 task (96.0% completati, 70.2% compliance)

⚡ PERFORMANCE ALGORITMO
Algoritmo: greedy
Tempo esecuzione: 0.026s
Task/secondo: 1,850.6
Efficienza: excellent

⚠️ VIOLAZIONI RILEVATE
Violazioni priorità: 261
Conflitti risorse: 0
Anomalie temporali: 26
```

#### 📁 File Generati

Il profiler genera automaticamente:
- **JSON**: `profile_YYYYMMDD_HHMMSS.json` - Dati completi per analisi programmatica
- **CSV**: `profile_YYYYMMDD_HHMMSS.csv` - Metriche principali per Excel/analisi
- **HTML**: `dashboard_YYYYMMDD_HHMMSS.html` - Dashboard interattivo con grafici

### Test di Qualità del Prodotto

Il sistema include una suite completa di test per verificare la qualità della pianificazione prodotta, indipendentemente dall'algoritmo utilizzato internamente.

#### Comandi Rapidi

```bash
# Setup ambiente di test
make setup

# Test rapido (50 task) con profilazione
make quick-test

# Test qualità completo (100 task)
make test-quality

# Benchmark performance M4
make benchmark-m4

# Genera report HTML completo
make generate-report

# Mostra tutti i comandi disponibili
make help
```

#### Test Disponibili

```bash
# Test di qualità per scenari specifici
make test-quality          # Scenario produzione (100 task)
make test-performance       # Benchmark performance M4
make test-priority         # Test rispetto priorità
make test-stress           # Stress test (500 task)
make test-all             # Tutti i test di qualità

# Test unitari base
make test-unit            # Test unitari originali

# Generazione report
make generate-report                # Report completo
make generate-report-production     # Solo scenario produzione
make generate-report-stress         # Solo stress test
make demo                          # Demo con visualizzazioni
```

#### Test Manuali con Docker

```bash
# Test completi in container
docker-compose exec task-scheduler-api pytest tests/test_scheduling_quality.py -v

# Test con coverage
docker-compose exec task-scheduler-api pytest --cov=src

# Genera report in container
docker-compose exec task-scheduler-api python tests/quality_report_generator.py
```

### Metriche di Qualità

#### Schedule Quality Score (SQS)
Metrica principale che combina:
- **Completeness (40%)**: Percentuale task schedulati
- **Priority Compliance (40%)**: Rispetto ordine priorità
- **Resource Efficiency (20%)**: Bilanciamento utilizzo risorse

#### Soglie di Qualità
- **SQS ≥ 80%**: Eccellente ✅
- **SQS 60-79%**: Buona ⚠️
- **SQS < 60%**: Da ottimizzare ❌

#### Metriche Dettagliate
```python
{
  "sqs": 85.2,                    # Schedule Quality Score
  "completeness": 95.0,           # % task schedulati
  "priority_compliance": 88.5,    # % rispetto priorità
  "resource_efficiency": 72.3,    # Bilanciamento risorse
  "scheduled_tasks": 95,          # Task schedulati
  "total_tasks": 100              # Task totali
}
```

### Scenari di Test

#### 1. Scenario Produzione (100 task, 10 risorse)
- **Obiettivo**: Simulare carico produzione reale
- **Aspettative**: SQS ≥ 75%, Tempo < 10s (M4)
- **Priorità**: 20% alta, 60% media, 20% bassa
- **Assenze**: 15% distribuite

#### 2. Scenario Carico Elevato (200 task, 10 risorse)
- **Obiettivo**: Test con carico sostenuto
- **Aspettative**: SQS ≥ 65%, Tempo < 20s (M4)
- **Priorità**: 40% alta, 40% media, 20% bassa
- **Assenze**: 25% concentrate

#### 3. Scenario Stress (500 task, 10 risorse)
- **Obiettivo**: Test limiti sistema
- **Aspettative**: SQS ≥ 50%, Tempo < 60s (M4)
- **Priorità**: Distribuzione realistica
- **Assenze**: 30% sovrapposte

### Benchmark MacBook Pro M4

#### Performance Target
| Task | Tempo Atteso | SQS Atteso | Memoria |
|------|-------------|------------|---------|
| 50   | < 3s        | ≥ 85%      | < 500MB |
| 100  | < 8s        | ≥ 80%      | < 1GB   |
| 200  | < 20s       | ≥ 70%      | < 2GB   |
| 500  | < 60s       | ≥ 60%      | < 4GB   |

#### Esecuzione Benchmark
```bash
# Benchmark completo
make benchmark-m4

# Output esempio:
# 🏆 MacBook Pro M4 Benchmarks:
#   50 tasks: 2.1s, SQS: 87.3%
#   100 tasks: 5.8s, SQS: 82.1%
#   200 tasks: 15.2s, SQS: 74.5%
```

### Report HTML

Il sistema genera report HTML completi con:

#### Dashboard Qualità
- **Schedule Quality Score** principale
- **Metriche dettagliate** per scenario
- **Statistiche esecuzione** (tempo, memoria)
- **Distribuzione priorità** task

#### Visualizzazioni
- **📅 Diagramma di Gantt**: Timeline attività
- **👥 Utilizzo Risorse**: Heatmap carico
- **📊 Distribuzione Task**: Statistiche ore
- **⏱️ Timeline Interattiva**: Grafico Plotly

#### Generazione Report
```bash
# Report completo (tutti gli scenari)
make generate-report

# Report specifico
python tests/quality_report_generator.py --scenarios production high_load

# Output:
# 📄 Report: reports/quality_report_20250608_125430.html
# 🌐 Open: file:///path/to/report.html
```

### Interpretazione Risultati

#### Risultati Ottimali
```
✅ SUCCESS: Production Scenario
📊 SQS: 85.2% (Eccellente)
📈 Completeness: 95.0%
🎯 Priority Compliance: 88.5%
👥 Resource Efficiency: 72.3%
⏱️ Execution Time: 5.8s
```

#### Risultati da Ottimizzare
```
⚠️ WARNING: High Load Scenario
📊 SQS: 62.1% (Buona)
📈 Completeness: 85.0%
🎯 Priority Compliance: 65.2%
👥 Resource Efficiency: 45.8%
⏱️ Execution Time: 18.3s
```

#### Azioni Correttive
- **SQS < 60%**: Verificare vincoli calendario e assenze
- **Completeness < 80%**: Aumentare orizzonte temporale
- **Priority Compliance < 70%**: Rivedere distribuzione priorità
- **Resource Efficiency < 50%**: Bilanciare carico risorse

### Troubleshooting Test

#### Test Falliscono
```bash
# Verifica setup
make setup

# Controlla dipendenze
pip install -r requirements.txt

# Test singolo per debug
pytest tests/test_scheduling_quality.py::TestSchedulingQuality::test_100_tasks_production_quality -v -s
```

#### Performance Lente
```bash
# Verifica sistema
make info

# Test rapido
make quick-test

# Profiling memoria
pytest tests/test_scheduling_quality.py --memray
```

#### Report Non Generati
```bash
# Verifica directory
mkdir -p reports/charts

# Test generatore
python tests/quality_report_generator.py --scenarios production

# Controlla log
tail -f logs/scheduler.log
```

### Integrazione CI/CD

```bash
# Pipeline completa
make ci-test

# Include:
# - Setup ambiente
# - Controlli stile codice
# - Test qualità completi
# - Generazione report
```

### Sviluppo e Debug

```bash
# Installa dipendenze sviluppo
make install-dev

# Controlli stile
make lint

# Formattazione codice
make format

# Coverage completa
make coverage

# Pulizia
make clean
```

## 📊 Monitoraggio e Performance

### Metriche Disponibili

```json
{
  "algorithm_used": "greedy",
  "tasks_scheduled": 45,
  "tasks_total": 50,
  "success_rate": 0.9,
  "solve_time": 0.123,
  "horizon_days": 28
}
```

### Log Levels

```bash
# Configurazione logging
LOG_LEVEL=DEBUG    # Dettagli completi
LOG_LEVEL=INFO     # Informazioni principali (default)
LOG_LEVEL=WARNING  # Solo avvisi ed errori
LOG_LEVEL=ERROR    # Solo errori
```

## 📊 Soglie di Accettabilità - Guida Completa

Questo documento descrive dove sono definite e come modificare tutte le soglie di accettabilità utilizzate dal sistema di Task Scheduler per test e profilazione.

## 🎯 File Principale: `src/config_thresholds.py`

**Tutte le soglie sono centralizzate in questo file unico** per facilitare manutenzione e modifiche.

### 📋 Struttura delle Soglie

#### 1. **Priority Compliance**
```python
# Classificazione priorità
PRIORITY_CLASSIFICATION = {
    'high': 80,      # Priorità >= 80 = Alta
    'medium': 50,    # Priorità >= 50 = Media
    'low': 0         # Priorità >= 0 = Bassa
}

# Soglie accettabilità Priority Compliance
PRIORITY_COMPLIANCE_THRESHOLDS = {
    'excellent': 85.0,    # >= 85% = Eccellente
    'good': 70.0,         # >= 70% = Buono
    'acceptable': 50.0,   # >= 50% = Accettabile
    'poor': 0.0           # < 50% = Scarso
}
```

#### 2. **Schedule Quality Score (SQS)**
```python
# Pesi per calcolo SQS
SQS_WEIGHTS = {
    'completeness': 0.4,        # 40% peso completezza
    'priority_compliance': 0.4, # 40% peso priorità
    'resource_efficiency': 0.2  # 20% peso efficienza risorse
}

# Soglie qualità SQS
SQS_THRESHOLDS = {
    'excellent': 80.0,    # >= 80% = Eccellente ✅
    'good': 60.0,         # >= 60% = Buono ⚠️
    'acceptable': 40.0,   # >= 40% = Accettabile
    'poor': 0.0           # < 40% = Scarso ❌
}
```

#### 3. **Soglie per Scenario di Test**
```python
# Scenario Produzione (100 task, 10 risorse)
PRODUCTION_SCENARIO_THRESHOLDS = {
    'sqs_min': 75.0,                    # SQS >= 75%
    'completeness_min': 80.0,           # Completeness >= 80%
    'priority_compliance_min': 70.0,    # Priority Compliance >= 70%
    'resource_efficiency_min': 50.0,    # Resource Efficiency >= 50%
    'max_execution_time': 10.0          # Tempo <= 10s (MacBook M4)
}

# Scenario Carico Elevato (200 task, 10 risorse)
HIGH_LOAD_SCENARIO_THRESHOLDS = {
    'sqs_min': 65.0,                    # SQS >= 65%
    'completeness_min': 70.0,           # Completeness >= 70%
    'priority_compliance_min': 80.0,    # Priority Compliance >= 80%
    'resource_efficiency_min': 40.0,    # Resource Efficiency >= 40%
    'max_execution_time': 20.0          # Tempo <= 20s (MacBook M4)
}

# Scenario Stress (500 task, 10 risorse)
STRESS_SCENARIO_THRESHOLDS = {
    'sqs_min': 50.0,                    # SQS >= 50%
    'completeness_min': 60.0,           # Completeness >= 60%
    'priority_compliance_min': 60.0,    # Priority Compliance >= 60%
    'resource_efficiency_min': 30.0,    # Resource Efficiency >= 30%
    'max_execution_time': 60.0          # Tempo <= 60s (MacBook M4)
}
```

#### 4. **Benchmark Performance (MacBook Pro M4)**
```python
BENCHMARK_M4_THRESHOLDS = [
    {
        'tasks': 50,
        'expected_time': 5.0,      # <= 5s
        'expected_sqs': 60.0,      # >= 60%
        'expected_memory': 500     # <= 500MB
    },
    {
        'tasks': 100,
        'expected_time': 10.0,     # <= 10s
        'expected_sqs': 55.0,      # >= 55%
        'expected_memory': 1000    # <= 1GB
    },
    {
        'tasks': 200,
        'expected_time': 30.0,     # <= 30s
        'expected_sqs': 50.0,      # >= 50%
        'expected_memory': 2000    # <= 2GB
    }
]
```

## 🔧 Come Modificare le Soglie

### 1. **Modifica Diretta**
Edita il file `src/config_thresholds.py` e modifica i valori desiderati:

```python
# Esempio: Rendere più stringenti i test di produzione
PRODUCTION_SCENARIO_THRESHOLDS = {
    'sqs_min': 80.0,                    # Era 75.0
    'completeness_min': 85.0,           # Era 80.0
    'priority_compliance_min': 75.0,    # Era 70.0
    'resource_efficiency_min': 60.0,    # Era 50.0
    'max_execution_time': 8.0           # Era 10.0
}
```

### 2. **Utilizzo Programmatico**
```python
from src.config_thresholds import get_scenario_thresholds

# Ottieni soglie per uno scenario
thresholds = get_scenario_thresholds('production')
print(f"SQS minimo: {thresholds['sqs_min']}%")

# Verifica se generare raccomandazione
from src.config_thresholds import should_generate_recommendation
if should_generate_recommendation('priority_compliance', 75.0):
    print("Genera raccomandazione per priority compliance")
```

## 📍 Dove Vengono Utilizzate

### 1. **Test di Qualità** (`tests/test_scheduling_quality.py`)
```python
from src.config_thresholds import PRODUCTION_SCENARIO_THRESHOLDS

# Usa soglie centralizzate nei test
thresholds = PRODUCTION_SCENARIO_THRESHOLDS
self.assertGreaterEqual(quality_metrics['sqs'], thresholds['sqs_min'])
```

### 2. **Sistema di Profilazione** (`src/scheduler/profiler.py`)
```python
from src.config_thresholds import (
    PRIORITY_CLASSIFICATION,
    RECOMMENDATION_THRESHOLDS,
    should_generate_recommendation
)

# Usa soglie per classificazione priorità
if priority_score >= PRIORITY_CLASSIFICATION['high']:
    return 'high'

# Usa soglie per raccomandazioni
if should_generate_recommendation('priority_compliance', value):
    recommendations.append("Migliora priority compliance")
```

### 3. **Comandi Makefile**
I comandi di test utilizzano automaticamente le soglie centralizzate:
```bash
make test-quality          # Usa PRODUCTION_SCENARIO_THRESHOLDS
make test-stress           # Usa STRESS_SCENARIO_THRESHOLDS
make benchmark-m4          # Usa BENCHMARK_M4_THRESHOLDS
```

## 🎯 Soglie Specifiche per Metrica

### **Priority Compliance**
- **Eccellente**: ≥ 85%
- **Buono**: ≥ 70%
- **Accettabile**: ≥ 50%
- **Scarso**: < 50%

### **Schedule Quality Score (SQS)**
- **Eccellente**: ≥ 80% ✅
- **Buono**: ≥ 60% ⚠️
- **Accettabile**: ≥ 40%
- **Scarso**: < 40% ❌

### **Completeness**
- **Eccellente**: ≥ 95%
- **Buono**: ≥ 85%
- **Accettabile**: ≥ 70%
- **Scarso**: < 70%

### **Resource Efficiency**
- **Eccellente**: ≥ 80%
- **Buono**: ≥ 60%
- **Accettabile**: ≥ 40%
- **Scarso**: < 40%

## ⚡ Performance (MacBook Pro M4)

### **Tempi di Esecuzione Attesi**
| Task | Tempo Max | SQS Min | Memoria Max |
|------|-----------|---------|-------------|
| 50   | 5s        | 60%     | 500MB       |
| 100  | 10s       | 55%     | 1GB         |
| 200  | 30s       | 50%     | 2GB         |

### **Efficienza Algoritmo**
- **Excellent**: < 0.01s per task
- **Good**: < 0.05s per task
- **Fair**: < 0.1s per task
- **Poor**: ≥ 0.1s per task

## 🚨 Anomalie e Violazioni

### **Anomalie Temporali**
```python
TEMPORAL_ANOMALY_THRESHOLDS = {
    'large_gap_hours': 48.0,      # Gap > 48h = anomalia
    'concentration_max': 80.0     # Concentrazione > 80% = anomalia
}
```

### **Conflitti Risorse**
```python
RESOURCE_CONFLICT_THRESHOLDS = {
    'max_conflicts': 0,           # 0 conflitti accettabili
    'max_overlaps_per_resource': 0 # 0 sovrapposizioni per risorsa
}
```

### **Violazioni Severe**
```python
SEVERE_PRIORITY_VIOLATION_THRESHOLD = 30.0  # Gap priorità > 30 = violazione severa
```

## 💡 Raccomandazioni Automatiche

### **Soglie per Raccomandazioni**
```python
RECOMMENDATION_THRESHOLDS = {
    'priority_compliance_warning': 80.0,    # < 80% → raccomandazione priorità
    'resource_efficiency_warning': 60.0,    # < 60% → raccomandazione risorse
    'completeness_warning': 90.0,           # < 90% → raccomandazione orizzonte
    'high_priority_completion_warning': 95.0, # < 95% → raccomandazione task critici
    'severe_violations_warning': 5          # > 5 violazioni severe → raccomandazione
}
```

## 🔄 Funzioni Helper

### **Valutazione Qualità**
```python
from src.config_thresholds import evaluate_sqs_quality

quality_level = evaluate_sqs_quality(85.0)  # Returns: 'excellent'
```

### **Soglie per Scenario**
```python
from src.config_thresholds import get_scenario_thresholds

thresholds = get_scenario_thresholds('production')
# Returns: PRODUCTION_SCENARIO_THRESHOLDS
```

### **Controllo Raccomandazioni**
```python
from src.config_thresholds import should_generate_recommendation

if should_generate_recommendation('priority_compliance', 75.0):
    # Genera raccomandazione perché 75.0 < 80.0 (soglia warning)
    pass
```

## 📝 Best Practices

### 1. **Modifica Centralizzata**
- ✅ Modifica sempre `src/config_thresholds.py`
- ❌ Non hardcodare soglie nei singoli file

### 2. **Test delle Modifiche**
```bash
# Testa le modifiche
make test-quality
make profile-demo

# Verifica benchmark
make benchmark-m4
```

### 3. **Documentazione**
- Documenta il motivo delle modifiche
- Aggiorna questo file se necessario
- Testa su scenari diversi

### 4. **Backup**
- Salva le soglie precedenti prima di modificare
- Testa gradualmente le nuove soglie
- Monitora l'impatto sui test esistenti

## 🎯 Esempi Pratici

### **Scenario 1: Test Troppo Permissivi**
```python
# Prima (troppo permissivo)
PRODUCTION_SCENARIO_THRESHOLDS = {
    'sqs_min': 60.0,  # Troppo basso
}

# Dopo (più stringente)
PRODUCTION_SCENARIO_THRESHOLDS = {
    'sqs_min': 75.0,  # Più realistico
}
```

### **Scenario 2: Performance Lente**
```python
# Prima (troppo ottimistico)
BENCHMARK_M4_THRESHOLDS = [
    {'tasks': 100, 'expected_time': 5.0}  # Troppo veloce
]

# Dopo (più realistico)
BENCHMARK_M4_THRESHOLDS = [
    {'tasks': 100, 'expected_time': 10.0}  # Più realistico
]
```

### **Scenario 3: Priority Compliance Basso**
```python
# Abbassa soglia se il sistema ha limitazioni strutturali
PRIORITY_COMPLIANCE_THRESHOLDS = {
    'good': 60.0,  # Era 70.0
}
```

## 🔍 Monitoraggio

### **Comandi per Verificare Soglie**
```bash
# Test con soglie attuali
make test-all

# Profilazione dettagliata
make profile-demo

# Benchmark performance
make benchmark-m4

# Report completo
make generate-report
```

### **Log delle Soglie**
Il sistema logga automaticamente le soglie utilizzate:
```
📊 Quality Metrics:
   SQS: 85.2% (Soglia: 75.0%) ✅
   Priority Compliance: 77.8% (Soglia: 70.0%) ✅
   Completeness: 98.0% (Soglia: 80.0%) ✅
```

---

## 📞 Supporto

Per domande sulle soglie:
1. Consulta questo documento
2. Verifica `src/config_thresholds.py`
3. Testa con `make profile-demo`
4. Controlla i log per dettagli

## 🚨 Troubleshooting

### Problemi Comuni

#### 1. API non risponde
```bash
# Verifica stato container
docker-compose ps

# Controlla log
docker-compose logs task-scheduler-api

# Restart servizio
docker-compose restart task-scheduler-api
```

#### 2. Nessuna soluzione trovata
```bash
# Verifica dati input:
- Calendar slots sufficienti
- Assenze non eccessive
- Orizzonte temporale adeguato

# Aumenta orizzonte massimo
MAX_HORIZON_DAYS=3650  # 10 anni
```

#### 3. Performance lente
```bash
# Usa algoritmo Greedy
GREEDY_THRESHOLD_TASKS=10  # Soglia più bassa

# Riduci timeout OrTools
ORTOOLS_TIMEOUT_SECONDS=15

# Aumenta worker
ORTOOLS_WORKERS=8
```

#### 4. Memoria insufficiente
```bash
# Aumenta limiti Docker
mem_limit: 8g

# Riduci orizzonte
MAX_HORIZON_DAYS=365  # 1 anno

# Usa solo Greedy
HYBRID_MODE=false
```

### Debug Avanzato

```bash
# Log dettagliato
LOG_LEVEL=DEBUG

# Progress OrTools
ORTOOLS_LOG_PROGRESS=true

# Shell interattiva per debug
docker-compose exec task-scheduler-api python -m src.run
scheduler> status
scheduler> list
```

## 🔗 Integrazione con Sistemi Esterni

### Esempio Odoo

```python
# In un modulo Odoo personalizzato
import requests

def schedule_tasks(self):
    # Prepara dati
    tasks_data = []
    for task in self:
        tasks_data.append({
            'id': task.id,
            'name': task.name,
            'user_id': task.user_id.id,
            'remaining_hours': task.remaining_hours
        })

    # Chiama API
    response = requests.post(
        'http://task-scheduler-api:5050/api/v1/schedule',
        json={'tasks': tasks_data, 'calendar_slots': [...], 'leaves': [...]}
    )

    # Gestisci risposta
    if response.status_code == 202:
        # Pianificazione avviata
        return self._poll_for_results()
```

### Esempio Python Generico

```python
import requests
import time

# Avvia pianificazione
response = requests.post('http://localhost:5050/api/v1/schedule', json={
    'tasks': [...],
    'calendar_slots': [...],
    'leaves': [...]
})

if response.status_code == 202:
    # Attendi completamento
    while True:
        status = requests.get('http://localhost:5050/api/v1/schedule/status')
        if status.json()['status'] == 'completed':
            # Recupera risultati
            result = requests.get('http://localhost:5050/api/v1/schedule/result')
            schedule = result.json()['data']
            break
        time.sleep(1)
```

## 📝 Changelog

### v2.0.0 - Algoritmo Ibrido
- ✅ Implementazione algoritmo Greedy per performance
- ✅ Strategia ibrida Greedy + OrTools
- ✅ Fallback intelligente tra algoritmi
- ✅ Ottimizzazione per grandi volumi di task

### v1.5.0 - API REST Completa
- ✅ API REST con dati completi (no più dipendenza da database)
- ✅ Endpoint status e result separati
- ✅ Supporto CORS per integrazione web

### v1.0.0 - Versione Iniziale
- ✅ Modello OrTools CP-SAT
- ✅ Estensione automatica orizzonte temporale
- ✅ Visualizzazioni grafiche
- ✅ Containerizzazione Docker

## 📄 Licenza

Questo progetto è distribuito sotto licenza MIT. Vedi il file `LICENSE` per i dettagli.

## 🤝 Contributi

I contributi sono benvenuti! Per favore:

1. Fork del repository
2. Crea un branch per la feature (`git checkout -b feature/AmazingFeature`)
3. Commit delle modifiche (`git commit -m 'Add some AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Apri una Pull Request

## 📞 Supporto

Per supporto e domande:
- Apri un issue su GitHub
- Consulta i log per debugging: `docker-compose logs -f task-scheduler-api`
- Usa la shell interattiva per test: `docker-compose exec task-scheduler-api python -m src.run`
