import os
import random
import threading

import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPE = 'user-read-currently-playing user-read-playback-state user-modify-playback-state'


class Salle:
    """
    Une salle = une playlist + un compte Spotify + un état de vote.
    Chaque salle est 100% indépendante : propre client Spotify (cache séparé),
    propre thread de surveillance, propre queue.

    `config` est un dict issu de config/salles.json :
        { nom, couleur, client_id, client_secret, playlist_id }
    """

    def __init__(self, config, seuil_file=0.5):
        self.nom = config['nom']
        self.couleur = config.get('couleur', '#1DB954')
        self.playlist_id = config['playlist_id']
        self.seuil_file = seuil_file

        # Flag d'arrêt pour la thread de surveillance
        self.stop_flag = threading.Event()

        # État du vote
        self.pool_playlist = []
        self.chansons = [
            {'id': i + 1, 'titre': '', 'artiste': '', 'pochette': '', 'votes': 0}
            for i in range(3)
        ]
        self.ips_ayant_vote = set()
        self.detail_votes_tour = {}
        self.tour = 0

        # État de lecture Spotify
        self.titre_en_cours = ''
        self.vote_calcule = False
        self.chanson_en_cours = {
            'titre': '', 'artiste': '', 'pochette': '',
            'progression_ms': 0, 'duree_ms': 0, 'en_lecture': False,
        }
        self.file_attente = []

        # Spotify : cache fichier par salle
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_path = os.path.join(base_dir, f'.cache-{self.nom}')
        self.auth_manager = SpotifyOAuth(
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            redirect_uri=os.environ.get('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:5001/callback'),
            scope=SCOPE,
            cache_path=self.cache_path,
            show_dialog=True,
            open_browser=False,
        )
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

    # --- Cycle de vie ---

    def invalider_cache(self):
        """Supprime le cache .cache-<nom> (utilisé quand on change les credentials)."""
        try:
            os.remove(self.cache_path)
        except OSError:
            pass

    def demander_arret(self):
        """Signale à la thread de surveillance de s'arrêter à son prochain tick."""
        self.stop_flag.set()

    # --- Authentification ---

    def est_authentifie(self):
        try:
            token = self.auth_manager.get_cached_token()
            return token is not None and token.get('access_token') is not None
        except Exception:
            return False

    def authorize_url(self):
        return self.auth_manager.get_authorize_url(state=self.nom)

    def finaliser_auth(self, code):
        self.auth_manager.get_access_token(code, as_dict=False)

    # --- Pool ---

    def initialiser_pool(self):
        items = []
        offset = 0
        while True:
            results = self.sp.playlist_tracks(self.playlist_id, limit=100, offset=offset)
            for item in results['items']:
                track = item.get('track') or item.get('item')
                if track is None or track.get('type') != 'track':
                    continue
                if not track.get('album', {}).get('images'):
                    continue
                items.append({
                    'titre': track['name'],
                    'artiste': track['artists'][0]['name'],
                    'pochette': track['album']['images'][0]['url'],
                    'uri': track['uri'],
                    'votes': 0,
                })
            if results['next'] is None:
                break
            offset += 100
        random.shuffle(items)
        self.pool_playlist = items
        print(f"[{self.nom}] Pool initialisé : {len(self.pool_playlist)} chansons")

    def piocher(self):
        if len(self.pool_playlist) < 3:
            print(f"[{self.nom}] Pool épuisé, rechargement")
            self.initialiser_pool()
        pioche = self.pool_playlist[:3]
        self.pool_playlist = self.pool_playlist[3:]
        print(f"[{self.nom}] Piochées : {[c['titre'] for c in pioche]} | reste {len(self.pool_playlist)}")
        return pioche

    # --- Cycle de vote ---

    def nouveau_tirage(self):
        pistes = self.piocher()
        self.chansons = [{'id': i + 1, **p} for i, p in enumerate(pistes)]
        self.ips_ayant_vote = set()
        self.detail_votes_tour = {}
        self.tour += 1

    def ajouter_vote(self, chanson_id, pseudo, ip):
        if ip in self.ips_ayant_vote:
            return None
        for chanson in self.chansons:
            if chanson['id'] == chanson_id:
                chanson['votes'] += 1
                self.ips_ayant_vote.add(ip)
                self.detail_votes_tour.setdefault(chanson_id, []).append(pseudo)
                return chanson
        return None

    def cloturer_vote(self):
        total = sum(c['votes'] for c in self.chansons)
        if total == 0:
            return [random.choice(self.chansons)]
        tri = sorted(self.chansons, key=lambda c: c['votes'], reverse=True)
        gagnante = tri[0]
        return [c for c in tri if c['votes'] >= gagnante['votes'] * self.seuil_file]

    def a_vote(self, ip):
        return ip in self.ips_ayant_vote
