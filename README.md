# TASK Scheduler

Un sistema di pianificazione delle attività, progettato per ottimizzare l'allocazione delle risorse e la pianificazione delle attività.

## Caratteristiche

- Pianificazione automatica delle attività basata su vincoli
- Integrazione con database PostgreSQL
- Supporto per tunnel SSH per connessioni a database remoti
- Gestione dei calendari e delle assenze del personale
- Ottimizzazione della pianificazione utilizzando il solutore SCIP

## Requisiti

- Docker e Docker Compose
- Python 3.9+
- SCIP Optimizer (installato automaticamente nel Dockerfile)

## Struttura del Progetto

```
task-scheduler/
├── src/
│   ├── __init__.py
│   ├── run.py              # Punto di ingresso principale
│   ├── config.py           # Configurazioni e parametri
│   ├── db.py               # Connessione al database
│   ├── fetch.py            # Funzioni per recuperare dati
│   └── scheduler/          # Logica di scheduling
│       ├── __init__.py
│       ├── model.py        # Definizione del modello SCIP
│       └── utils.py        # Funzioni di utilità
├── tests/                  # Test unitari
├── logs/                   # Directory per i log
├── data/                   # Directory per i dati
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── setup.py
└── README.md
```

## Installazione

1. Clone il repository:
   ```bash
   git clone https://github.com/yourusername/task-scheduler.git
   cd task-scheduler
   ```

2. Crea un file `.env` basato su `.env.example`:
   ```bash
   cp .env.example .env
   ```

3. Modifica il file `.env` con le tue configurazioni

4. Avvia i container Docker:
   ```bash
   docker-compose up -d
   ```

## Utilizzo

### Esecuzione dello scheduler

```bash
docker-compose exec task-scheduler python -m src.run
```

### Accesso al container in modalità interattiva

```bash
docker-compose exec task-scheduler bash
```

### Visualizzazione dei log

```bash
docker-compose logs -f task-scheduler
```

## Configurazione

### Database

Il sistema si connette a un database PostgreSQL. Puoi configurare i parametri di connessione nel file `.env`:

```
DB_HOST=db
DB_PORT=5432
DB_NAME=scip_db
DB_USER=scip_user
DB_PASSWORD=scip_password
```

### Tunnel SSH

Se hai bisogno di connetterti a un database remoto attraverso un tunnel SSH, puoi abilitarlo e configurarlo nel file `.env`:

```
SSH_ENABLED=true
SSH_HOST=remote.example.com
SSH_PORT=22
SSH_USERNAME=user
SSH_KEY_PATH=/app/ssh_key
```

### Parametri SCIP

Puoi configurare i parametri del solutore SCIP nel file `.env`:

```
SCIP_TIME_LIMIT=3600
SCIP_GAP_LIMIT=0.01
SCIP_THREADS=4
SCIP_OUTPUT_FILE=/app/data/schedule.json
```

## Sviluppo

### Installazione in modalità sviluppo

```bash
pip install -e .
```

### Esecuzione dei test

```bash
pytest
```

## Licenza

Questo progetto è distribuito con licenza MIT.