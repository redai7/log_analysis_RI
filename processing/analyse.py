"""
Agrégations (bibliothèque standard uniquement) utilisées par le dashboard.

Toutes les fonctions prennent la liste d'évènements (dict) venant de storage.load_events()
et additionnent le champ 'count' (les "message repeated N times" comptent N).
"""
from collections import Counter, defaultdict
from datetime import timedelta

from logger_config import get_logger

logger = get_logger('analyse')

COUNTRY_NAMES = {
    'LOCAL': 'Réseau local', '??': 'Inconnu',
    'US': 'États-Unis', 'CN': 'Chine', 'RU': 'Russie', 'FR': 'France', 'DE': 'Allemagne',
    'NL': 'Pays-Bas', 'GB': 'Royaume-Uni', 'IN': 'Inde', 'BR': 'Brésil', 'ID': 'Indonésie',
    'VN': 'Vietnam', 'KR': 'Corée du Sud', 'JP': 'Japon', 'SG': 'Singapour',
    'HK': 'Hong Kong', 'TW': 'Taïwan', 'TH': 'Thaïlande', 'PH': 'Philippines',
    'PK': 'Pakistan', 'BD': 'Bangladesh', 'IR': 'Iran', 'TR': 'Turquie', 'UA': 'Ukraine',
    'PL': 'Pologne', 'RO': 'Roumanie', 'BG': 'Bulgarie', 'IT': 'Italie', 'ES': 'Espagne',
    'PT': 'Portugal', 'BE': 'Belgique', 'CH': 'Suisse', 'SE': 'Suède', 'NO': 'Norvège',
    'FI': 'Finlande', 'DK': 'Danemark', 'IE': 'Irlande', 'CZ': 'Tchéquie', 'HU': 'Hongrie',
    'MD': 'Moldavie', 'LT': 'Lituanie', 'LV': 'Lettonie', 'EE': 'Estonie', 'CA': 'Canada',
    'MX': 'Mexique', 'AR': 'Argentine', 'CL': 'Chili', 'CO': 'Colombie',
    'ZA': 'Afrique du Sud', 'EG': 'Égypte', 'MA': 'Maroc', 'DZ': 'Algérie', 'TN': 'Tunisie',
    'NG': 'Nigeria', 'KE': 'Kenya', 'SA': 'Arabie saoudite', 'AE': 'Émirats arabes unis',
    'IL': 'Israël', 'AU': 'Australie', 'NZ': 'Nouvelle-Zélande', 'KZ': 'Kazakhstan',
    'BY': 'Biélorussie', 'GR': 'Grèce', 'AT': 'Autriche', 'SC': 'Seychelles',
    'PA': 'Panama', 'VG': 'Îles Vierges britanniques', 'NA': 'Namibie',
}


def country_name(code):
    """'FR' -> 'France' (le code lui-même si le pays n'est pas dans la liste)."""
    return COUNTRY_NAMES.get(code, code)


def _count(events, event_type, key):
    """Counter {valeur de 'key': nombre de tentatives} pour un type d'évènement."""
    counter = Counter()
    for e in events:
        if e['event_type'] == event_type:
            counter[e[key]] += e['count']
    return counter


def kpis(events):
    totals = Counter()
    for e in events:
        totals[e['event_type']] += e['count']
    failed, success = totals['failed'], totals['success']
    return {
        'failed': failed,
        'success': success,
        'invalid_user': totals['invalid_user'],
        'failed_ips': len({e['ip'] for e in events if e['event_type'] == 'failed'}),
        'failure_rate': failed / (failed + success) * 100 if (failed + success) else 0.0,
    }


def by_country(events):
    """Tentatives par pays : liste de dict triée par nombre d'échecs décroissant."""
    stats = defaultdict(lambda: {'failed': 0, 'success': 0, 'invalid_user': 0})
    ips = defaultdict(set)
    for e in events:
        stats[e['country']][e['event_type']] += e['count']
        ips[e['country']].add(e['ip'])
    rows = [{'country': c, 'name': country_name(c), 'ips': len(ips[c]), **s}
            for c, s in stats.items()]
    rows.sort(key=lambda r: (-r['failed'], -r['invalid_user'], r['country']))
    return rows


def success_by_user(events):
    """Tentatives réussies par utilisateur : [(user, nombre)] triée."""
    return _count(events, 'success', 'user').most_common()


def invalid_by_user(events):
    """Tentatives 'Invalid user' par nom d'utilisateur essayé."""
    return _count(events, 'invalid_user', 'user').most_common()


def invalid_by_country(events):
    """Tentatives 'Invalid user' par pays : [(nom du pays, nombre)]."""
    return [(country_name(c), n) for c, n in _count(events, 'invalid_user', 'country').most_common()]


def top_ips(events, n=10):
    """IP les plus actives en échecs : [(ip, tentatives)]."""
    return _count(events, 'failed', 'ip').most_common(n)


def top_users(events, n=10):
    """Noms d'utilisateur les plus visés par les échecs."""
    return _count(events, 'failed', 'user').most_common(n)


def per_hour(events):
    """Échecs par heure de la journée : liste de 24 valeurs."""
    hours = Counter()
    for e in events:
        if e['event_type'] == 'failed':
            hours[e['datetime'].hour] += e['count']
    return [hours[h] for h in range(24)]


def per_day(events):
    """Liste [(date, échecs, réussites, invalid_user)] de la 1ère à la dernière date (jours vides inclus)."""
    if not events:
        return []
    days = defaultdict(Counter)
    for e in events:
        days[e['datetime'].date()][e['event_type']] += e['count']
    first, last = min(days), max(days)
    rows = []
    for i in range((last - first).days + 1):
        d = first + timedelta(days=i)
        c = days[d]            # defaultdict : un jour absent donne un Counter vide
        rows.append((d, c['failed'], c['success'], c['invalid_user']))
    return rows


def per_month(events):
    """Liste [('AAAA-MM', échecs, réussites, invalid_user)] triée."""
    months = defaultdict(Counter)
    for e in events:
        months[e['datetime'].strftime('%Y-%m')][e['event_type']] += e['count']
    return [(m, c['failed'], c['success'], c['invalid_user']) for m, c in sorted(months.items())]
