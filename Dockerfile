FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Installa solo le dipendenze Python pure (senza compilazione)
COPY requirements.txt .

# Modifica requirements.txt per versioni precompilate
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --only-binary=all \
        pandas \
        psycopg2-binary \
        sshtunnel \
        python-dotenv \
        pytest \
        pytest-cov \
        ortools \
        matplotlib \
        seaborn \
        plotly \
        flask \
        flask-restful \
        flask-cors \
        gunicorn \
        sqlalchemy

# Copia codice sorgente
COPY ./src /app/src
COPY setup.py README.md ./

# Installa il pacchetto in modalità sviluppo
RUN pip install -e . --no-deps

# Crea directory
RUN mkdir -p /app/logs /app/data && \
    chmod -R 777 /app/logs /app/data

# User non-root
RUN useradd -m appuser
USER appuser

EXPOSE 5000
CMD ["python", "-m", "src.run"]