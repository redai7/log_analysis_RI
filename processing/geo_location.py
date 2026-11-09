"""
Géolocalisation des adresses IP (pays) via ipinfo.io.

- get_location(ip)  : une IP -> dict ipinfo (ou None)
- locate_many(ips)  : plusieurs IP -> {ip: code_pays}, avec cache JSON
                      (on n'interroge jamais deux fois la même IP)

Erreurs gérées (écrites dans logs/geo_location.log) :
    - pas de connexion internet / timeout : arrêt après 5 échecs de suite
    - quota ipinfo dépassé (429) ou token refusé (401/403) : arrêt, le cache est sauvegardé
    - réponse invalide, cache JSON corrompu, écriture du cache impossible
Token gratuit (optionnel) : https://ipinfo.io/signup  puis  set IPINFO_TOKEN=xxxx
"""
import ipaddress
import json
import os
from pathlib import Path

import requests

from logger_config import get_logger

logger = get_logger('geo_location')

URL_IPINFO = "https://ipinfo.io"
CACHE_FILE = Path('./data/geo_cache.json')
UNKNOWN = '??'      # IP non localisée
LOCAL = 'LOCAL'     # IP privée / loopback (10.x, 192.168.x, 127.x ...)
MAX_NETWORK_ERRORS = 5


class RateLimitError(Exception):
    """Quota dépassé (429) ou token refusé (401/403) : inutile de continuer."""


class NetworkError(Exception):
    """Pas de réponse d'ipinfo (internet coupé, timeout...)."""


def get_location(ip):
    token = os.environ.get('IPINFO_TOKEN')
    params = {'token': token} if token else None
    try:
        response = requests.get(URL_IPINFO + '/' + ip + '/json', params=params, timeout=5)
    except requests.RequestException as e:
        logger.warning("%s : erreur réseau (%s)", ip, type(e).__name__)
        raise NetworkError(str(e))

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError:
            logger.error("%s : réponse ipinfo invalide (JSON attendu)", ip)
            return None
    if response.status_code in (401, 403, 429):
        logger.error("%s : ipinfo a répondu %d (quota dépassé ou token refusé)",
                     ip, response.status_code)
        raise RateLimitError(response.status_code)
    logger.warning("%s : ipinfo a répondu %d", ip, response.status_code)
    return None


def _load_cache():
    try:
        return json.loads(CACHE_FILE.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:       # ValueError : JSON corrompu
        logger.error("Cache illisible (%s) : on repart d'un cache vide", e)
        return {}


def _save_cache(cache):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache), encoding='utf-8')
    except OSError as e:
        logger.error("Écriture du cache impossible : %s", e)


def locate_many(ips, use_network=True):
    """
    in  : itérable d'IP ; use_network=False pour n'utiliser que le cache
    out : dict {ip: code_pays}  (LOCAL pour une IP privée, ?? si inconnu)
    """
    cache = _load_cache()
    result = {}
    todo = []
    for ip in sorted(set(ips)):
        try:
            if ipaddress.ip_address(ip).is_private:
                result[ip] = LOCAL
                continue
        except ValueError:
            logger.warning("Adresse IP invalide ignorée : %r", ip)
            result[ip] = UNKNOWN
            continue
        if ip in cache:
            result[ip] = cache[ip]
        else:
            todo.append(ip)

    logger.info("%d IP : %d en cache ou locales, %d à interroger",
                len(result) + len(todo), len(result), len(todo))

    if todo and not use_network:
        logger.warning("%d IP non localisées (mode sans réseau)", len(todo))
    elif todo:
        print(f"Géolocalisation de {len(todo)} IP (la 1ère fois, cela peut prendre plusieurs minutes)...")
        network_errors = 0
        for i, ip in enumerate(todo, start=1):
            try:
                info = get_location(ip)
            except RateLimitError:
                print("Limite ipinfo atteinte : cache sauvegardé, relancez plus tard "
                      "ou définissez IPINFO_TOKEN.")
                break
            except NetworkError:
                network_errors += 1
                if network_errors >= MAX_NETWORK_ERRORS:
                    logger.error("%d erreurs réseau de suite : arrêt de la géolocalisation",
                                 MAX_NETWORK_ERRORS)
                    print("Pas de connexion à ipinfo.io : géolocalisation interrompue.")
                    break
                continue
            network_errors = 0
            if info and info.get('country'):
                cache[ip] = result[ip] = info['country']
            else:
                logger.info("%s : pays inconnu (bogon ou réponse sans pays)", ip)
            if i % 100 == 0:
                _save_cache(cache)
                logger.info("%d/%d IP traitées", i, len(todo))
        _save_cache(cache)

    for ip in todo:
        result.setdefault(ip, UNKNOWN)
    return result


if __name__ == '__main__':
    print(get_location('103.215.80.173'))
