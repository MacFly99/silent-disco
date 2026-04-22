"""
Génère 50 users avec des votes aléatoires pour tester la page /stats.

Usage : python seed_fake_data.py

Ça écrit dans :
  - logs/users.log         (append : une ligne par user créé)
  - logs/user_stats.json   (merge : compteurs par uuid)
  - logs/votes-YYYY-MM-DD.log  (append : une ligne par vote)
"""

import json
import os
import random
import uuid
from datetime import datetime, timedelta

LOGS_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

USERS_LOG = os.path.join(LOGS_DIR, 'users.log')
STATS_FILE = os.path.join(LOGS_DIR, 'user_stats.json')

PSEUDOS = [
    'Olive', 'Marie', 'Paul', 'Sophie', 'Julie', 'Max', 'Léa', 'Tom', 'Emma', 'Hugo',
    'Camille', 'Louis', 'Chloé', 'Nico', 'Lucie', 'Arthur', 'Zoé', 'Théo', 'Jade', 'Raph',
    'DJKebab', 'Nono', 'Lulu', 'Fanfan', 'PouletFroid', 'Biscotte', 'Kiki', 'Momo', 'Titi',
    'Seb', 'Anaïs', 'Pierre', 'Clara', 'Baptiste', 'Océane', 'Mathieu', 'Romain', 'Julia',
    'Alex', 'Manon', 'Guillaume', 'Sarah', 'Vincent', 'Elise', 'Antoine', 'Léo', 'Mila',
    'Yanis', 'Inès', 'Nathan', 'Ambre',
]

CHANSONS_FAKE = [
    (1, 'Dis-moi je t\'aime', 'arøne'),
    (2, 'FOMO', 'Juste Shani'),
    (3, 'Vendredi 13', 'Georgio'),
    (1, 'Les Avions', 'Lomepal'),
    (2, 'Puzzle', 'Nekfeu'),
    (3, 'Plus Haut', 'Ben Mazué'),
    (1, 'Tout Va Bien', 'Orelsan'),
    (2, 'Zéro', 'Jul'),
    (3, 'La Grenade', 'Clara Luciani'),
]

SALLES = ['pop', 'nostalgie']


def iso(dt):
    return dt.isoformat(timespec='seconds')


def seed(clear_first=False):
    """Génère des users fake. Si clear_first=True, vide user_stats.json et users.log d'abord."""
    maintenant = datetime.now()
    debut = maintenant - timedelta(hours=2)

    stats = {}
    if clear_first:
        # Efface les fichiers existants pour repartir propre
        for path in (STATS_FILE, USERS_LOG):
            try:
                os.remove(path)
            except OSError:
                pass
    else:
        # Sinon on merge avec l'existant
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, 'r', encoding='utf-8') as f:
                    stats = json.load(f)
            except Exception:
                stats = {}

    users_lignes = []
    votes_par_jour = {}  # {date_str: [ligne, ...]}

    for pseudo in PSEUDOS:
        user_uuid = str(uuid.uuid4())
        # Distribution : 70% d'users avec peu de votes (1-5), 30% actifs (6-30)
        nb_votes = random.randint(1, 5) if random.random() < 0.7 else random.randint(6, 30)

        first_seen_dt = debut + timedelta(seconds=random.randint(0, 3600))
        last_vote_dt = first_seen_dt

        votes_par_salle = {}

        # Générer `nb_votes` lignes dans votes-YYYY-MM-DD.log et compter par salle
        for _ in range(nb_votes):
            vote_dt = first_seen_dt + timedelta(seconds=random.randint(0, 3600))
            if vote_dt > last_vote_dt:
                last_vote_dt = vote_dt
            salle = random.choice(SALLES)
            votes_par_salle[salle] = votes_par_salle.get(salle, 0) + 1
            cid, titre, artiste = random.choice(CHANSONS_FAKE)
            ip = f'192.168.1.{random.randint(2, 254)}'
            ligne = (f'{iso(vote_dt)} | {salle} | {pseudo} | {ip} | '
                     f'{cid} | {titre} - {artiste}')
            jour = vote_dt.strftime('%Y-%m-%d')
            votes_par_jour.setdefault(jour, []).append(ligne)

        stats[user_uuid] = {
            'pseudo': pseudo,
            'votes': nb_votes,
            'votes_par_salle': votes_par_salle,
            'first_seen': iso(first_seen_dt),
            'last_vote': iso(last_vote_dt),
        }

        users_lignes.append(f'{iso(first_seen_dt)} | NOUVEAU | {user_uuid} | {pseudo}')

    # Écrit users.log (append)
    with open(USERS_LOG, 'a', encoding='utf-8') as f:
        f.write('\n'.join(users_lignes) + '\n')

    # Écrit user_stats.json (merge — overwrite)
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # Écrit votes-YYYY-MM-DD.log (append par jour)
    for jour, lignes in votes_par_jour.items():
        # Tri chronologique dans le fichier
        lignes.sort()
        path = os.path.join(LOGS_DIR, f'votes-{jour}.log')
        with open(path, 'a', encoding='utf-8') as f:
            f.write('\n'.join(lignes) + '\n')

    total_votes = sum(u['votes'] for u in stats.values())
    print(f"✓ {len(PSEUDOS)} users fake ajoutés ({total_votes} votes générés)")
    print(f"  {len(stats)} users au total dans user_stats.json")


if __name__ == '__main__':
    import sys
    clear = '--clear' in sys.argv
    seed(clear_first=clear)
