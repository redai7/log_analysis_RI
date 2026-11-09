"""
Sauvegarde / lecture des évènements dans un fichier CSV (data/processed/events.csv).
Erreurs gérées : dossier non inscriptible, fichier absent, ligne CSV invalide
(écrites dans logs/storage.log).
"""
import csv
from datetime import datetime
from pathlib import Path

from logger_config import get_logger

logger = get_logger('storage')

FIELDS = ['datetime', 'ip', 'user', 'event_type', 'method', 'count', 'country']


def save_events(events, path):
    """in : liste d'évènements, chemin / out : True si l'écriture a réussi."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
            writer.writeheader()
            for e in events:
                writer.writerow({**e, 'datetime': e['datetime'].isoformat(sep=' ')})
    except OSError as e:
        logger.error("Écriture impossible de %s : %s", path, e)
        return False
    logger.info("%d évènements écrits dans %s", len(events), path)
    return True


def load_events(path):
    """in : chemin du CSV / out : liste d'évènements ([] si le fichier est absent)."""
    path = Path(path)
    events = []
    try:
        with open(path, newline='', encoding='utf-8') as f:
            for n, row in enumerate(csv.DictReader(f), start=2):
                try:
                    row['datetime'] = datetime.fromisoformat(row['datetime'])
                    row['count'] = int(row['count'])
                    events.append(row)
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning("%s ligne %d ignorée (%s: %s)", path.name, n,
                                   type(e).__name__, e)
    except FileNotFoundError:
        logger.error("Fichier introuvable : %s (lancez d'abord python main.py)", path)
        return []
    except OSError as e:
        logger.error("Lecture impossible de %s : %s", path, e)
        return []
    logger.info("%d évènements lus depuis %s", len(events), path)
    return events
