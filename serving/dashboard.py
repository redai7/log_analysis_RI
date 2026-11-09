"""
Dashboard HTML (sans aucune bibliothèque externe) : lit data/processed/events.csv
et écrit serving/dashboard.html, à ouvrir dans le navigateur.

    python main.py            (génère le CSV puis le dashboard)
    python serving/dashboard.py   (régénère seulement le dashboard)

Erreurs gérées (logs/dashboard.log) : CSV absent ou vide, écriture impossible.
"""
import sys
from html import escape
from math import ceil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))                    # pour importer logger_config et processing/

from logger_config import get_logger             # noqa: E402
from processing import analyse, storage          # noqa: E402

logger = get_logger('dashboard')

CSV_FILE = ROOT / 'data' / 'processed' / 'events.csv'
HTML_FILE = ROOT / 'serving' / 'dashboard.html'

CSS = """
:root{--bg:#f5f6f8;--card:#fff;--text:#1f2430;--muted:#6b7280;--line:#e5e7eb;
--failed:#d62728;--success:#2ca02c;--invalid:#e08a00}
@media (prefers-color-scheme:dark){:root{--bg:#14161b;--card:#1d2027;--text:#e6e8ec;
--muted:#9aa1ad;--line:#2d313a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,Segoe UI,Arial,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}
h1{margin:0 0 4px;font-size:26px} h2{margin:32px 0 12px;font-size:19px}
h3{margin:0 0 10px;font-size:15px}
.sub{color:var(--muted);margin:0 0 20px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.kpi,.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kpi b{display:block;font-size:26px;line-height:1.2} .kpi span{color:var(--muted);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
.note{background:var(--card);border-left:4px solid var(--invalid);padding:10px 14px;border-radius:6px;margin:16px 0}
.bars .row{display:grid;grid-template-columns:minmax(90px,150px) 1fr 70px;gap:8px;align-items:center;margin:5px 0}
.label{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}
.track{background:var(--line);border-radius:4px;height:14px;display:block}
.fill{display:block;height:100%;border-radius:4px}
.value{text-align:right;font-variant-numeric:tabular-nums;font-size:13px}
.c-failed{background:var(--failed);fill:var(--failed)}
.c-success{background:var(--success);fill:var(--success)}
.c-invalid{background:var(--invalid);fill:var(--invalid)}
svg.col{width:100%;height:auto} svg text{fill:var(--muted);font-size:10px}
svg line{stroke:var(--line)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:right;padding:5px 8px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left} th{color:var(--muted);font-weight:600}
details{margin-top:10px} summary{cursor:pointer;color:var(--muted)}
.empty{color:var(--muted)}
"""


def fmt(n):
    """12345 -> '12 345'"""
    return f"{n:,}".replace(',', ' ')


def bar_chart(rows, css_class):
    """Barres horizontales. rows = [(libellé, valeur)]"""
    if not rows:
        return '<p class="empty">Aucune donnée.</p>'
    biggest = max(v for _, v in rows) or 1
    html = ['<div class="bars">']
    for label, value in rows:
        label = label if label != '' else '(vide)'
        html.append(
            f'<div class="row"><span class="label" title="{escape(label)}">{escape(label)}</span>'
            f'<span class="track"><span class="fill {css_class}" style="width:{value / biggest * 100:.1f}%">'
            f'</span></span><span class="value">{fmt(value)}</span></div>')
    html.append('</div>')
    return ''.join(html)


def column_chart(points, css_class):
    """Histogramme SVG. points = [(libellé, valeur)]"""
    if not points:
        return '<p class="empty">Aucune donnée.</p>'
    width, height, left, bottom, top = 640, 220, 44, 24, 10
    plot_h = height - bottom - top
    peak = max(v for _, v in points) or 1
    slot = (width - left - 8) / len(points)
    bar_w = slot * 0.7
    step = max(1, ceil(len(points) / 10))         # une étiquette sur 'step' pour rester lisible

    svg = [f'<svg class="col" viewBox="0 0 {width} {height}" role="img">']
    for frac in (0, 0.5, 1):
        y = top + plot_h * (1 - frac)
        svg.append(f'<line x1="{left}" x2="{width - 8}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<text x="{left - 6}" y="{y + 3:.1f}" text-anchor="end">{fmt(round(peak * frac))}</text>')
    for i, (label, value) in enumerate(points):
        h = value / peak * plot_h
        x = left + i * slot + (slot - bar_w) / 2
        svg.append(f'<rect class="{css_class}" x="{x:.1f}" y="{top + plot_h - h:.1f}" '
                   f'width="{bar_w:.1f}" height="{h:.1f}"><title>{escape(label)} : {fmt(value)}</title></rect>')
        if i % step == 0:
            svg.append(f'<text x="{x + bar_w / 2:.1f}" y="{height - 8}" text-anchor="middle">{escape(label)}</text>')
    svg.append('</svg>')
    return ''.join(svg)


def table(headers, rows):
    head = ''.join(f'<th>{escape(h)}</th>' for h in headers)
    body = ''.join('<tr>' + ''.join(f'<td>{escape(str(c))}</td>' for c in row) + '</tr>' for row in rows)
    return f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def card(title, content):
    return f'<div class="card"><h3>{escape(title)}</h3>{content}</div>'


def build_html(events):
    k = analyse.kpis(events)
    countries = analyse.by_country(events)
    days = analyse.per_day(events)
    months = analyse.per_month(events)
    first, last = days[0][0], days[-1][0]

    parts = [f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analyse des logs SSH</title><style>{CSS}</style></head><body><main>
<h1>Analyse des connexions SSH</h1>
<p class="sub">Logs du {first:%d/%m/%Y} au {last:%d/%m/%Y} &middot; {fmt(len(events))} évènements sshd</p>"""]

    if all(e['country'] == '??' for e in events):
        parts.append('<div class="note">Les pays ne sont pas encore connus : lancez <code>python main.py</code> '
                     'avec une connexion internet (géolocalisation ipinfo.io).</div>')

    # --- indicateurs
    parts.append('<div class="kpis">'
                 f'<div class="kpi"><b>{fmt(k["failed"])}</b><span>Tentatives échouées</span></div>'
                 f'<div class="kpi"><b>{fmt(k["success"])}</b><span>Tentatives réussies</span></div>'
                 f'<div class="kpi"><b>{fmt(k["invalid_user"])}</b><span>Tentatives invalid user</span></div>'
                 f'<div class="kpi"><b>{fmt(k["failed_ips"])}</b><span>IP à l\'origine d\'échecs</span></div>'
                 f'<div class="kpi"><b>{k["failure_rate"]:.2f} %</b><span>Taux d\'échec</span></div></div>')

    # --- 1. échecs par pays
    top = [(f'{r["name"]}', r['failed']) for r in countries[:15]]
    all_rows = [(r['name'], fmt(r['failed']), fmt(r['success']), fmt(r['invalid_user']), fmt(r['ips']))
                for r in countries]
    parts.append('<h2>1. Nombre de tentatives échouées par pays</h2>')
    parts.append(card('Top 15 des pays', bar_chart(top, 'c-failed') +
                      '<details><summary>Voir tous les pays</summary>' +
                      table(['Pays', 'Échecs', 'Réussites', 'Invalid user', 'IP uniques'], all_rows) +
                      '</details>'))

    # --- 2. réussites par user
    success = analyse.success_by_user(events)
    parts.append('<h2>2. Nombre de tentatives réussies par user</h2>')
    parts.append(card('Connexions réussies', bar_chart(success[:15], 'c-success') +
                      (f'<details><summary>Voir tous les users ({len(success)})</summary>'
                       + table(['User', 'Réussites'], [(u, fmt(n)) for u, n in success]) + '</details>'
                       if len(success) > 15 else '')))

    # --- 3. invalid user
    parts.append('<h2>3. Tentatives échouées avec invalid user</h2><div class="grid">')
    parts.append(card(f'Noms d\'utilisateur inexistants les plus essayés ({fmt(k["invalid_user"])} tentatives)',
                      bar_chart(analyse.invalid_by_user(events)[:10], 'c-invalid')))
    parts.append(card('Pays d\'origine des tentatives invalid user',
                      bar_chart(analyse.invalid_by_country(events)[:10], 'c-invalid')))
    parts.append('</div>')

    # --- par jour / par mois
    parts.append('<h2>Connexions par jour</h2><div class="grid">')
    parts.append(card('Échecs par jour', column_chart([(f'{d:%d/%m}', f) for d, f, _, _ in days], 'c-failed')))
    parts.append(card('Réussites par jour', column_chart([(f'{d:%d/%m}', s) for d, _, s, _ in days], 'c-success')))
    parts.append('</div>')
    parts.append('<h2>Connexions par mois</h2>')
    parts.append(card('Échecs et réussites par mois',
                      table(['Mois', 'Échecs', 'Réussites', 'Invalid user'],
                            [(m, fmt(f), fmt(s), fmt(i)) for m, f, s, i in months])))

    # --- analyse des échecs
    parts.append('<h2>Analyse des échecs</h2><div class="grid">')
    parts.append(card('Top 10 des IP', bar_chart(analyse.top_ips(events, 10), 'c-failed')))
    parts.append(card('Top 10 des users visés', bar_chart(analyse.top_users(events, 10), 'c-failed')))
    parts.append('</div><div style="margin-top:12px">')
    parts.append(card('Échecs par heure de la journée',
                      column_chart([(f'{h}h', v) for h, v in enumerate(analyse.per_hour(events))], 'c-failed')))
    parts.append('</div></main></body></html>')
    return ''.join(parts)


def generate(csv_path=CSV_FILE, html_path=HTML_FILE):
    """in : CSV des évènements / out : chemin du HTML écrit, ou None en cas d'erreur."""
    events = storage.load_events(csv_path)
    if not events:
        logger.error("Aucun évènement à afficher : dashboard non généré")
        return None
    try:
        html = build_html(events)
    except Exception:                                  # bug inattendu : on garde la trace complète
        logger.exception("Erreur pendant la construction du dashboard")
        return None
    try:
        Path(html_path).write_text(html, encoding='utf-8')
    except OSError as e:
        logger.error("Écriture impossible de %s : %s", html_path, e)
        return None
    logger.info("Dashboard écrit : %s", html_path)
    return Path(html_path)


if __name__ == '__main__':
    out = generate()
    print(f"Dashboard : {out}" if out else "Échec, voir logs/dashboard.log")
