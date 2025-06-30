#!/usr/bin/env python
"""
Script di avvio per il server API del Task Scheduler.
Questo script avvia un server Flask che espone API REST per interagire con il Task Scheduler.
"""

import argparse
from src.api import run_api_server
from src.config import setup_logging

# Configura il logging
logger = setup_logging()


def main():
    """Punto di ingresso principale per il server API"""
    parser = argparse.ArgumentParser(description='Task Scheduler API Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host su cui avviare il server (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000, help='Porta su cui avviare il server (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Avvia il server in modalità debug')

    args = parser.parse_args()

    logger.info(f"Avvio del server API su {args.host}:{args.port} (debug: {args.debug})")

    try:
        run_api_server(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("Server API terminato dall'utente")
    except Exception as e:
        logger.exception(f"Errore durante l'esecuzione del server API: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
