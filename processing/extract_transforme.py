"""
Extraction et transformation des lignes de log SSH (auth.log).

in  : liste de lignes brutes
out : liste de dictionnaires, un par évènement sshd :
      {datetime, ip, user, event_type, method, count}

event_type :
    - success       : "Accepted password/publickey for ..."
    - failed        : "Failed password for ..."   (échec d'authentification)
    - invalid_user  : "Invalid user ... from ..." (utilisateur inexistant)

Remarque : un "Failed password for invalid user X" est compté comme 'failed'
(et pas deux fois) ; la ligne "Invalid user X" est un évènement à part.
Les erreurs (lignes mal formées, dates impossibles) vont dans logs/extract_transforme.log
"""
import re
from datetime import datetime

from logger_config import get_logger

logger = get_logger('extract_transforme')

# Le format syslog n'a pas d'année : on la fixe ici (logs de mai 2026)
DEFAULT_YEAR = 2026

MONTHS = {m: i for i, m in enumerate(
    ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], start=1)}

# Ex : "May 24 00:26:51 ns sshd[1351208]: Invalid user test from 1.2.3.4 port 35940"
# (le [pid] est optionnel : "sudo:" et "systemd:" n'en ont pas)
pattern = re.compile(
    r'^(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+'
    r'(?P<server>\S+)\s+(?P<service>[\w.-]+)(?:\[(?P<pid>\d+)\])?:\s+(?P<message>.*)$'
)

# Messages sshd qui nous intéressent
RE_FAILED = re.compile(
    r'^Failed (?P<method>\S+) for (?P<invalid>invalid user )?(?P<user>.*?) from (?P<ip>\S+) port \d+')
RE_SUCCESS = re.compile(
    r'^Accepted (?P<method>\S+) for (?P<user>\S+) from (?P<ip>\S+) port \d+')
RE_INVALID = re.compile(
    r'^Invalid user (?P<user>.*?) from (?P<ip>\S+) port \d+')
# Ex : "message repeated 4 times: [ Failed password for root from 1.2.3.4 port 80 ssh2]"
# syslog a déjà écrit la 1ère occurrence : "4 times" = 4 tentatives en plus
RE_REPEAT = re.compile(r'^message repeated (?P<n>\d+) times: \[\s*(?P<inner>.*?)\s*\]$')


def _classify(message):
    """Retourne (event_type, ip, user, method) ou None si le message n'est pas pertinent."""
    m = RE_FAILED.match(message)
    if m:
        return 'failed', m['ip'], m['user'], m['method']
    m = RE_SUCCESS.match(message)
    if m:
        return 'success', m['ip'], m['user'], m['method']
    m = RE_INVALID.match(message)
    if m:
        return 'invalid_user', m['ip'], m['user'], ''
    return None


def _event_from_match(match, year):
    """Construit l'évènement à partir d'une ligne reconnue (peut lever KeyError/ValueError)."""
    message = match['message']
    count = 1
    rep = RE_REPEAT.match(message)
    if rep:
        count = int(rep['n'])
        message = rep['inner']

    result = _classify(message)
    if result is None:
        return None
    event_type, ip, user, method = result

    hour, minute, second = (int(x) for x in match['time'].split(':'))
    dt = datetime(year, MONTHS[match['month']], int(match['day']), hour, minute, second)
    return {'datetime': dt, 'ip': ip, 'user': user,
            'event_type': event_type, 'method': method, 'count': count}


def extract_from_row(row, year=DEFAULT_YEAR):
    """
    in  : une ligne de log (str)
    out : dict {datetime, ip, user, event_type, method, count} ou None
    """
    match = pattern.search(row.strip())
    if not match or match['service'] != 'sshd':
        return None
    try:
        return _event_from_match(match, year)
    except (KeyError, ValueError) as e:
        logger.error("Date invalide (%s) : %.100s", e, row.strip())
        return None


def parse_rows(rows, year=DEFAULT_YEAR):
    """in : liste de lignes brutes / out : liste d'évènements triée par date."""
    events = []
    stats = {'malformed': 0, 'other_service': 0, 'ignored': 0, 'bad_date': 0}

    for n, row in enumerate(rows, start=1):
        line = row.strip()
        if not line:
            continue
        match = pattern.search(line)
        if not match:
            stats['malformed'] += 1
            logger.warning("Ligne %d : format syslog non reconnu : %.100s", n, line)
            continue
        if match['service'] != 'sshd':
            stats['other_service'] += 1            # CRON, sudo, systemd... : normal
            continue
        try:
            event = _event_from_match(match, year)
        except (KeyError, ValueError) as e:
            stats['bad_date'] += 1
            logger.error("Ligne %d : date invalide (%s) : %.100s", n, e, line)
            continue
        if event is None:
            stats['ignored'] += 1                  # sshd mais ni échec, ni réussite, ni invalid user
            continue
        events.append(event)

    events.sort(key=lambda e: e['datetime'])
    logger.info("%d lignes -> %d évènements | autres services : %d | sshd ignorés : %d | "
                "mal formées : %d | dates invalides : %d",
                len(rows), len(events), stats['other_service'], stats['ignored'],
                stats['malformed'], stats['bad_date'])
    return events


if __name__ == '__main__':
    exemple = "May 24 00:27:58 ns sshd[1351222]: Failed password for invalid user test from 45.156.87.204 port 41740 ssh2"
    print(extract_from_row(exemple))
