FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Non aggiornare pip, usa quello che c'è
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copia codice sorgente
COPY ./src /app/src
COPY setup.py README.md ./

# Installa il pacchetto
RUN pip install -e .

# Crea directory
RUN mkdir -p /app/logs /app/data && \
    chmod -R 777 /app/logs /app/data

# User non-root
RUN useradd -m appuser
USER appuser

EXPOSE 5000
CMD ["python", "-m", "src.run"]