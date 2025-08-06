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

## 🧪 Testing e Benchmark

### Test di Qualità del Prodotto

Il sistema include una suite completa di test per verificare la qualità della pianificazione prodotta, indipendentemente dall'algoritmo utilizzato internamente.

#### Comandi Rapidi

```bash
# Setup ambiente di test
make setup

# Test rapido (50 task)
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
