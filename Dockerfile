FROM python:3.11-slim

# Imposta variabili di ambiente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Disabilita gli script post-invoke di APT che causano errori in slim
RUN echo 'APT::Update::Post-Invoke-Success "true";' > /etc/apt/apt.conf.d/no-postinvoke && \
    apt-get update && \
    apt-get install -y build-essential && \
    rm -rf /var/lib/apt/lists/*

# Crea e attiva l'ambiente dell'applicazione
WORKDIR /app

# Copia e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia il codice sorgente
COPY ./src /app/src
COPY setup.py README.md ./

# Installa il pacchetto in modalità sviluppo
RUN pip install -e .

# Crea directory per log e dati con permessi adeguati
RUN mkdir -p /app/logs /app/data && \
    chmod -R 777 /app/logs /app/data

# Utente non-root per maggiore sicurezza
RUN useradd -m appuser
USER appuser

# Esponi la porta per l'API
EXPOSE 5000

# Comando di avvio (può essere sovrascritto in docker-compose.yml)
CMD ["python", "-m", "src.run"]
