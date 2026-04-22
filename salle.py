import random


class Salle:
    """
    Une salle de vote : une playlist, un pool, une couleur de thème, et l'état d'un tour de vote.
    Les salles sont indépendantes ; plusieurs peuvent coexister (ex: pop + nostalgie).
    """

    def __init__(self, nom, playlist_id, couleur='#1DB954', seuil_file=0.5):
        self.nom = nom
        self.playlist_id = playlist_id
        self.couleur = couleur
        self.seuil_file = seuil_file
        self.pool_playlist = []
        self.chansons = [
            {'id': i + 1, 'titre': '', 'artiste': '', 'pochette': '', 'votes': 0}
            for i in range(3)
        ]
        self.ips_ayant_vote = set()
        self.detail_votes_tour = {}
        self.tour = 0

    # --- Pool ---

    def initialiser_pool(self, sp):
        items = []
        offset = 0
        while True:
            results = sp.playlist_tracks(self.playlist_id, limit=100, offset=offset)
            for item in results['items']:
                if item['item'] is None or item['item']['type'] != 'track':
                    continue
                track = item['item']
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

    def piocher(self, sp):
        if len(self.pool_playlist) < 3:
            print(f"[{self.nom}] Pool épuisé, rechargement")
            self.initialiser_pool(sp)
        pioche = self.pool_playlist[:3]
        self.pool_playlist = self.pool_playlist[3:]
        print(f"[{self.nom}] Piochées : {[c['titre'] for c in pioche]} | reste {len(self.pool_playlist)}")
        return pioche

    # --- Cycle de vote ---

    def nouveau_tirage(self, sp):
        pistes = self.piocher(sp)
        self.chansons = [{'id': i + 1, **p} for i, p in enumerate(pistes)]
        self.ips_ayant_vote = set()
        self.detail_votes_tour = {}
        self.tour += 1

    def ajouter_vote(self, chanson_id, pseudo, ip):
        """Retourne la chanson votée si accepté, None si l'IP a déjà voté / id inconnu."""
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
        """Retourne la liste des gagnantes. Ne reset pas — appeler nouveau_tirage après."""
        total = sum(c['votes'] for c in self.chansons)
        if total == 0:
            return [random.choice(self.chansons)]
        tri = sorted(self.chansons, key=lambda c: c['votes'], reverse=True)
        gagnante = tri[0]
        return [c for c in tri if c['votes'] >= gagnante['votes'] * self.seuil_file]

    def a_vote(self, ip):
        return ip in self.ips_ayant_vote
