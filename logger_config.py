"""
Configuration des logs de l'application : un fichier par module dans ./logs

    from logger_config import get_logger
    logger = get_logger('ingestion')      # -> logs/ingestion.log

- le fichier reçoit tous les niveaux (DEBUG, INFO, WARNING, ERROR)
- la console n'affiche que WARNING et plus (pour ne pas noyer l'utilisateur)
"""
import logging
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / 'logs'
FORMAT = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'


def get_logger(name):
    logger = logging.getLogger(name)
    if logger.handlers:                 # déjà configuré (évite les lignes en double)
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    formatter = logging.Formatter(FORMAT)

    try:
        LOG_DIR.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(LOG_DIR / f'{name}.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        print(f"Impossible de créer le fichier de log '{name}' : {e}")

    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger
