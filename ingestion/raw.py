import gzip
from pathlib import Path

from logger_config import get_logger

logger = get_logger('ingestion')


def to_rows(path: str) -> list[str]:
    """
    Lit tous les fichiers d'un répertoire (.gz inclus).

    in  : path (répertoire)
    out : liste de lignes
    Erreurs gérées (écrites dans logs/ingestion.log) : répertoire absent ou illisible,
    fichier illisible, .gz corrompu ou tronqué. Un fichier en erreur est ignoré,
    les autres sont quand même lus.
    """
    data_dir = Path(path)
    rows = []

    try:
        files = sorted(data_dir.iterdir())
    except FileNotFoundError:
        logger.error("Répertoire introuvable : %s", path)
        return []
    except NotADirectoryError:
        logger.error("%s n'est pas un répertoire", path)
        return []
    except PermissionError:
        logger.error("Accès refusé au répertoire : %s", path)
        return []

    logger.info("Lecture de %d élément(s) dans %s", len(files), path)

    for file_path in files:
        if not file_path.is_file():
            logger.debug("Ignoré (pas un fichier) : %s", file_path.name)
            continue

        opener = gzip.open if file_path.suffix == '.gz' else open
        try:
            # encoding explicite : sous Windows l'encodage par défaut (cp1252) peut planter
            with opener(file_path, mode='rt', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except PermissionError:
            logger.error("Accès refusé au fichier : %s", file_path.name)
            continue
        except (OSError, EOFError) as e:       # .gz corrompu (BadGzipFile) ou tronqué (EOFError)
            logger.error("Lecture impossible de %s : %s: %s", file_path.name,
                         type(e).__name__, e)
            continue

        logger.info("%s : %d lignes", file_path.name, len(lines))
        rows.extend(lines)

    if not rows:
        logger.warning("Aucune ligne lue dans %s", path)
    return rows


if __name__ == '__main__':
    data = to_rows('./data')
    if data:
        print(data[:10])
