"""
Lecture / écriture de la config des salles (config/salles.json).

Une salle = { nom, couleur, client_id, client_secret, playlist_id }.
Les deux derniers sont des credentials Spotify, donc à protéger.

Si le fichier n'existe pas au premier démarrage, on tente une migration
depuis les anciennes variables d'env SPOTIFY_POP_* / SPOTIFY_NOSTALGIE_*.
"""

import json
import os
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'salles.json')

os.makedirs(CONFIG_DIR, exist_ok=True)

_lock = threading.Lock()

CHAMPS_OBLIGATOIRES = ('nom', 'client_id', 'client_secret', 'playlist_id')
COULEUR_DEFAUT = '#1DB954'


def charger():
    """Retourne la liste des salles (liste de dicts). Jamais None."""
    with _lock:
        if not os.path.exists(CONFIG_FILE):
            migrees = _migrer_depuis_env()
            if migrees:
                _ecrire(migrees)
                return migrees
            return []
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []


def sauvegarder(salles):
    """Écrit la liste complète (remplace l'existant). Valide avant d'écrire."""
    for s in salles:
        for champ in CHAMPS_OBLIGATOIRES:
            if not s.get(champ):
                raise ValueError(f"Champ '{champ}' manquant pour la salle '{s.get('nom', '?')}'")
        s.setdefault('couleur', COULEUR_DEFAUT)
    with _lock:
        _ecrire(salles)


def _ecrire(salles):
    tmp = CONFIG_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(salles, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)


def _migrer_depuis_env():
    """Si .env contient des creds salle style historique, les migrer en liste."""
    resultat = []
    for nom, couleur in (('pop', '#3b82f6'), ('nostalgie', '#1DB954')):
        prefixe = f'SPOTIFY_{nom.upper()}'
        client_id = os.environ.get(f'{prefixe}_CLIENT_ID', '').strip()
        client_secret = os.environ.get(f'{prefixe}_CLIENT_SECRET', '').strip()
        playlist_id = os.environ.get(f'{prefixe}_PLAYLIST_ID', '').strip()
        if all((client_id, client_secret, playlist_id)):
            resultat.append({
                'nom': nom,
                'couleur': couleur,
                'client_id': client_id,
                'client_secret': client_secret,
                'playlist_id': playlist_id,
            })
    if resultat:
        print(f"[config] Migration depuis .env : {len(resultat)} salle(s) importée(s)")
    return resultat
