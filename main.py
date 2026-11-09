"""
Pipeline : ingestion (data/) -> extraction -> géolocalisation -> CSV -> dashboard HTML

Usage :
    python main.py              # pipeline complet (géolocalisation via internet)
    python main.py --open       # ouvre le dashboard dans le navigateur

Les erreurs de chaque module sont écrites dans ./logs/<module>.log
"""
import argparse
import webbrowser
from pathlib import Path

from logger_config import get_logger
from ingestion import raw
from processing import extract_transforme, geo_location, analyse, storage
from serving import dashboard

logger = get_logger('main')

OUTPUT = Path('./data/processed/events.csv')


def run(year, use_network):
    rows = raw.to_rows('./data')
    if not rows:
        logger.error("Aucune ligne lue : vérifiez le dossier ./data (voir logs/ingestion.log)")
        return None
    print(f"{len(rows)} lignes lues")

    events = extract_transforme.parse_rows(rows, year)
    if not events:
        logger.error("Aucun évènement sshd extrait (voir logs/extract_transforme.log)")
        return None
    print(f"{len(events)} évènements sshd extraits "
          f"({events[0]['datetime']:%d/%m/%Y} -> {events[-1]['datetime']:%d/%m/%Y})")

    countries = geo_location.locate_many([e['ip'] for e in events], use_network=use_network)
    for e in events:
        e['country'] = countries.get(e['ip'], geo_location.UNKNOWN)

    if not storage.save_events(events, OUTPUT):
        return None
    print(f"Fichier écrit : {OUTPUT}")
    return events


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Analyse des logs SSH")
    parser.add_argument('--no-geo', action='store_true', help="ne pas appeler ipinfo.io")
    parser.add_argument('--year', type=int, default=extract_transforme.DEFAULT_YEAR)
    parser.add_argument('--open', action='store_true', help="ouvrir le dashboard dans le navigateur")
    args = parser.parse_args()

    try:
        events = run(args.year, use_network=not args.no_geo)
    except Exception:
        logger.exception("Erreur inattendue dans le pipeline")
        raise SystemExit(1)
    if events is None:
        raise SystemExit(1)

    k = analyse.kpis(events)
    print(f"\nÉchecs : {k['failed']} | Réussites : {k['success']} | "
          f"Invalid user : {k['invalid_user']} | IP à l'origine d'échecs : {k['failed_ips']}")

    page = dashboard.generate()
    if page:
        print(f"Dashboard : {page}")
        if args.open:
            webbrowser.open(page.as_uri())
