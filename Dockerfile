FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Installa solo le dipendenze Python pure (senza compilazione)
COPY requirements.txt .

# Installa pacchetti in piccoli batch per evitare problemi di threading
RUN pip install --no-cache-dir --disable-pip-version-check \
        pandas psycopg2-binary sshtunnel python-dotenv

RUN pip install --no-cache-dir --disable-pip-version-check \
        pytest pytest-cov

RUN pip install --no-cache-dir --disable-pip-version-check \
        ortools

RUN pip install --no-cache-dir --disable-pip-version-check \
        matplotlib seaborn plotly

RUN pip install --no-cache-dir --disable-pip-version-check \
        flask flask-restful flask-cors gunicorn sqlalchemy

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