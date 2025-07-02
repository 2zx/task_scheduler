FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Installa i pacchetti essenziali uno alla volta
RUN pip install --no-cache-dir --disable-pip-version-check pandas
RUN pip install --no-cache-dir --disable-pip-version-check psycopg2-binary
RUN pip install --no-cache-dir --disable-pip-version-check sshtunnel
RUN pip install --no-cache-dir --disable-pip-version-check python-dotenv
RUN pip install --no-cache-dir --disable-pip-version-check ortools
RUN pip install --no-cache-dir --disable-pip-version-check flask
RUN pip install --no-cache-dir --disable-pip-version-check flask-restful
RUN pip install --no-cache-dir --disable-pip-version-check flask-cors
RUN pip install --no-cache-dir --disable-pip-version-check matplotlib
RUN pip install --no-cache-dir --disable-pip-version-check plotly
RUN pip install --no-cache-dir --disable-pip-version-check sqlalchemy

# Copia codice sorgente
COPY ./src /app/src
COPY setup.py README.md ./

# Installa il pacchetto senza dipendenze
RUN pip install -e . --no-deps

# Crea directory
RUN mkdir -p /app/logs /app/data && \
    chmod -R 777 /app/logs /app/data

# User non-root
RUN useradd -m appuser
USER appuser

EXPOSE 5000
CMD ["python", "-m", "src.run"]