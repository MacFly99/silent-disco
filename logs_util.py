import os
from datetime import datetime

LOGS_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)


def logger_vote(salle_nom, pseudo, ip, chanson):
    nom_fichier = os.path.join(LOGS_DIR, f'votes-{datetime.now().strftime("%Y-%m-%d")}.log')
    ligne = (
        f'{datetime.now().isoformat(timespec="seconds")} | {salle_nom} | {pseudo} | {ip} | '
        f'{chanson["id"]} | {chanson["titre"]} - {chanson["artiste"]}\n'
    )
    with open(nom_fichier, 'a', encoding='utf-8') as f:
        f.write(ligne)


def logger_tour(salle_nom, numero_tour, chansons_tour, detail_votes, gagnantes):
    nom_fichier = os.path.join(LOGS_DIR, f'tours-{datetime.now().strftime("%Y-%m-%d")}.log')
    liste_gagnantes = ', '.join(c['titre'] for c in gagnantes) or '(aucune)'

    lignes = [f'=== {datetime.now().isoformat(timespec="seconds")} | [{salle_nom}] Tour {numero_tour} ===']
    for c in chansons_tour:
        pseudos = detail_votes.get(c['id'], [])
        pluriel = 's' if len(pseudos) > 1 else ''
        lignes.append(f'  [{c["id"]}] {c["titre"]} - {c["artiste"]} ({len(pseudos)} vote{pluriel})')
        for p in pseudos:
            lignes.append(f'      - {p}')
    lignes.append(f'  -> File attente : {liste_gagnantes}')
    lignes.append('')

    with open(nom_fichier, 'a', encoding='utf-8') as f:
        f.write('\n'.join(lignes) + '\n')
