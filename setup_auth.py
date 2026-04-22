"""
Script à lancer UNE FOIS par salle pour obtenir le refresh_token Spotify.
Ensuite tu colles ce token dans ton .env et l'app s'auth automatiquement.

Usage :
    python setup_auth.py pop
    python setup_auth.py nostalgie

Important :
- Ferme d'abord l'app Flask (Ctrl+C) car le script ouvre un mini serveur
  sur le même port que ton SPOTIFY_REDIRECT_URI.
- Pour la 2e salle avec un compte différent : déconnecte-toi de spotify.com
  dans ton navigateur (ou utilise un onglet privé) AVANT de lancer le script.
"""

import os
import sys

from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

SCOPE = 'user-read-currently-playing user-read-playback-state user-modify-playback-state'


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('pop', 'nostalgie'):
        print("Usage : python setup_auth.py <pop|nostalgie>")
        sys.exit(1)

    nom = sys.argv[1]
    prefixe = f'SPOTIFY_{nom.upper()}'

    try:
        client_id = os.environ[f'{prefixe}_CLIENT_ID']
        client_secret = os.environ[f'{prefixe}_CLIENT_SECRET']
    except KeyError as e:
        print(f"Variable manquante dans .env : {e}")
        sys.exit(1)

    redirect_uri = os.environ.get('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:5001/callback')
    tmp_cache = f'.cache-setup-{nom}'

    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPE,
        cache_path=tmp_cache,
        show_dialog=True,
        open_browser=True,
    )

    print(f"\nOuverture du navigateur pour authentifier la salle '{nom}'...")
    print("(Connecte-toi avec le compte Spotify qui va jouer la musique de cette salle)\n")

    # Lance l'OAuth interactif, catche le callback via un mini serveur local
    token_info = auth.get_access_token(as_dict=True)

    print(f"\n✓ Auth réussie pour '{nom}'\n")
    print("Ajoute cette ligne dans ton .env :\n")
    print(f"    {prefixe}_REFRESH_TOKEN={token_info['refresh_token']}\n")

    # On supprime le cache temporaire, le token vit dans le .env
    try:
        os.remove(tmp_cache)
    except OSError:
        pass


if __name__ == '__main__':
    main()
