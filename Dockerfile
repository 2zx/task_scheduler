FROM python:3.11-slim

# Imposta variabili di ambiente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SCIP_VERSION=v922 \
    SCIPOPTDIR=/opt/scip/install

# Installa dipendenze di sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    libgmp-dev \
    libreadline-dev \
    libz-dev \
    libboost-all-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Clona e compila SCIP con AUTOBUILD
WORKDIR /opt
RUN git clone https://github.com/scipopt/scip.git && \
    cd scip && \
    git checkout ${SCIP_VERSION} && \
    mkdir build && cd build && \
    cmake .. -DAUTOBUILD=ON -DCMAKE_INSTALL_PREFIX=${SCIPOPTDIR} && \
    make -j4 && make install && \
    cd /opt && rm -rf scip/build

# Crea e attiva l'ambiente dell'applicazione
WORKDIR /app

# Copia e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir git+https://github.com/scipopt/PySCIPOpt.git

# Copia il codice sorgente
COPY ./src /app/src
COPY setup.py README.md ./

# Installa il pacchetto in modalità sviluppo
RUN pip install -e .

# Crea directory per log e dati
RUN mkdir -p /app/logs /app/data && \
    chmod -R 777 /app/logs /app/data

# Utente non-root per maggiore sicurezza
RUN useradd -m appuser
USER appuser

# Comando di avvio
CMD ["python", "-m", "src.run"]