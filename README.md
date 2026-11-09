# Analyse des logs SSH

Petit projet Python pour analyser les tentatives de connexion SSH d'un serveur à partir de ses fichiers `auth.log`.

L'idée de départ : mon serveur est exposé sur internet et je voulais voir concrètement qui essaie de s'y connecter, depuis quels pays, avec quels noms d'utilisateur, et à quelle heure. Le script lit les logs, garde seulement ce qui concerne `sshd`, géolocalise les adresses IP, sauvegarde le tout dans un CSV et génère une page HTML avec les statistiques.

## Ce que ça fait

1. **Ingestion** : lecture de tous les fichiers du dossier `data/` (les `.gz` sont lus directement, pas besoin de les décompresser).
2. **Extraction** : une regex récupère les lignes `sshd` et les classe en trois types d'évènements :
   - `success` : `Accepted password/publickey for ...`
   - `failed` : `Failed password for ...`
   - `invalid_user` : `Invalid user ... from ...`
3. **Géolocalisation** : le pays de chaque IP est demandé à [ipinfo.io](https://ipinfo.io) et mis en cache, pour ne jamais interroger deux fois la même IP.
4. **Stockage** : tout est écrit dans `data/processed/events.csv`.
5. **Dashboard** : une page HTML autonome (pas de JS, pas de librairie externe, les graphiques sont en SVG/CSS) est générée dans `serving/dashboard.html`.

Le dashboard affiche notamment :

- les tentatives échouées par pays
- les connexions réussies par utilisateur
- les tentatives avec un utilisateur qui n'existe pas (les noms les plus essayés et leurs pays d'origine)
- les échecs par jour, par mois et par heure de la journée
- le top 10 des IP et des utilisateurs les plus visés

## Installation

Il faut Python 3.9 ou plus récent (j'utilise des annotations du type `list[str]`).

```bash
git clone <url-du-repo>
cd log_analysis
pip install -r requirements.txt
```

Seule la librairie `requests` est nécessaire (pour appeler ipinfo). Tout le reste utilise la bibliothèque standard.

## Utilisation

Mettre les fichiers de logs dans le dossier `data/` (il y a déjà quatre fichiers `auth.log` dedans), puis :

```bash
python main.py
```

Au premier lancement la géolocalisation peut prendre plusieurs minutes, selon le nombre d'IP différentes. Ensuite le cache est réutilisé et ça va beaucoup plus vite.

Options disponibles :

| Option | Effet |
|---|---|
| `--no-geo` | pas d'appel réseau, on utilise seulement le cache (les IP inconnues sont marquées `??`) |
| `--open` | ouvre le dashboard dans le navigateur à la fin |

Exemple :

```bash
python main.py --no-geo --open
```

Si le CSV existe déjà et que tu veux juste refaire la page HTML :

```bash
python serving/dashboard.py
```

### Token ipinfo (optionnel)

Sans token, ipinfo limite le nombre de requêtes par jour. Si la limite est atteinte, le script s'arrête proprement, sauvegarde le cache, et il suffit de relancer plus tard pour continuer là où il s'est arrêté. On peut aussi créer un token gratuit sur [ipinfo.io/signup](https://ipinfo.io/signup) :

```bash
# Linux / Mac
export IPINFO_TOKEN=xxxxxxxx

# Windows (cmd)
set IPINFO_TOKEN=xxxxxxxx
```

## Organisation du projet

```
log_analysis/
├── main.py                       # point d'entrée, lance tout le pipeline
├── logger_config.py              # un fichier de log par module
├── requirements.txt
├── data/
│   ├── auth.log.1, auth.log.2    # logs bruts
│   ├── auth.log.3.gz, .4.gz      # logs bruts compressés
│   ├── geo_cache.json            # cache des IP -> pays (généré)
│   └── processed/events.csv      # évènements extraits (généré)
├── ingestion/
│   └── raw.py                    # lecture des fichiers (.gz compris)
├── processing/
│   ├── extract_transforme.py     # regex + classification des évènements
│   ├── geo_location.py           # appels ipinfo + cache
│   ├── storage.py                # lecture/écriture du CSV
│   └── analyse.py                # agrégations pour le dashboard
├── serving/
│   └── dashboard.py              # génère dashboard.html
└── logs/                         # logs de l'application (généré)
```

## Le fichier CSV

`data/processed/events.csv` contient un évènement par ligne avec ces colonnes :

`datetime, ip, user, event_type, method, count, country`

La colonne `count` vaut 1 en général. Elle est plus grande quand syslog a regroupé plusieurs lignes identiques en une seule (`message repeated 4 times: [ ... ]`), pour ne pas sous-estimer le nombre de tentatives.

## Gestion des erreurs

Chaque module écrit ses erreurs dans son propre fichier dans `logs/` (`ingestion.log`, `extract_transforme.log`, `geo_location.log`, etc.). Dans la console on voit seulement les warnings et les erreurs, pour ne pas être noyé. Si quelque chose se passe mal (fichier `.gz` corrompu, pas de connexion internet, CSV illisible...), c'est là qu'il faut regarder.

Le script essaie de ne pas planter pour rien : un fichier illisible est ignoré et les autres sont quand même traités, une ligne mal formée est sautée, et si internet est coupé la géolocalisation s'arrête après 5 échecs de suite.

## Choix et limites

- **L'année** : le format syslog (`May 24 00:26:51`) ne contient pas l'année. Elle est fixée à 2026 par défaut dans `extract_transforme.py`, et on peut la changer avec `--year`. Ça ne marche pas pour des logs qui chevauchent deux années.
- **« Failed password for invalid user »** est compté comme un `failed` (une seule fois), alors que la ligne `Invalid user ...` est comptée à part comme `invalid_user`. Du coup, pour une même tentative, on peut avoir un évènement de chaque type, c'est voulu.
- Les IP privées (10.x, 192.168.x, 127.x...) ne sont pas envoyées à ipinfo, elles sont marquées `LOCAL`.
- Le pays est celui renvoyé par ipinfo, donc à prendre avec des pincettes (VPN, proxys, serveurs loués dans un autre pays...).
- Seuls les messages `sshd` sont analysés. Les lignes `CRON`, `sudo`, `systemd` etc. sont ignorées.
- Les logs fournis dans `data/` contiennent de vraies adresses IP, donc à ne pas publier tels quels si le repo est public.
