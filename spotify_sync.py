import time
from logs_util import logger_tour


class EtatGlobal:
    """
    État Spotify partagé entre toutes les salles.
    Une seule instance de lecture Spotify = une seule file d'attente.
    """
    def __init__(self, ordre_salles):
        self.file_attente = []           # gagnantes en attente de passer (toutes salles confondues)
        self.chanson_en_cours = {
            'titre': '', 'artiste': '', 'pochette': '',
            'progression_ms': 0, 'duree_ms': 0, 'en_lecture': False,
        }
        self.titre_en_cours = ''
        self.vote_calcule = False
        self.ordre_salles = ordre_salles   # ex: ['pop', 'nostalgie']
        self.prochaine_salle = ordre_salles[0]

    def toggle_salle(self):
        idx = self.ordre_salles.index(self.prochaine_salle)
        self.prochaine_salle = self.ordre_salles[(idx + 1) % len(self.ordre_salles)]


def demarrer_surveillance(sp, salles, socketio, etat):
    """Boucle infinie : poll Spotify, détecte fin de chanson, alterne les salles."""
    # Synchroniser le titre au démarrage pour ne pas déclencher un faux changement
    try:
        current = sp.current_playback()
        if current and current['item']:
            etat.titre_en_cours = current['item']['name']
            print(f"Chanson initiale : {etat.titre_en_cours}")
    except Exception as e:
        print(f"Impossible de lire la chanson initiale : {e}")

    while True:
        try:
            current = sp.current_playback()
            if current and current['item']:
                _traiter_tick(sp, salles, socketio, etat, current)
        except Exception as e:
            print(f"Erreur surveillance Spotify : {e}")
        time.sleep(2)


def _traiter_tick(sp, salles, socketio, etat, current):
    nouveau_titre = current['item']['name']
    progression = current['progress_ms']
    duree = current['item']['duration_ms']
    temps_restant = duree - progression

    # --- Changement de chanson ---
    if nouveau_titre != etat.titre_en_cours:
        print(f"Changement : '{etat.titre_en_cours}' -> '{nouveau_titre}'")
        etat.titre_en_cours = nouveau_titre
        etat.vote_calcule = False
        if etat.file_attente:
            etat.file_attente.pop(0)
            socketio.emit('file_attente', {'file': etat.file_attente})

    # --- Fin imminente : clôture + queue ---
    if temps_restant < 5000 and not etat.vote_calcule:
        print(f"Fin imminente ({temps_restant}ms)")
        etat.vote_calcule = True

        if not etat.file_attente:
            _cloturer_prochaine_salle(sp, salles, socketio, etat)

        if etat.file_attente:
            _ajouter_a_spotify(sp, etat.file_attente[0])
            socketio.emit('file_attente', {'file': etat.file_attente})

    # --- Diffusion de l'état de lecture ---
    etat.chanson_en_cours = {
        'titre': nouveau_titre,
        'artiste': current['item']['artists'][0]['name'],
        'pochette': current['item']['album']['images'][0]['url'],
        'progression_ms': progression,
        'duree_ms': duree,
        'en_lecture': current['is_playing'],
    }
    socketio.emit('chanson_en_cours', etat.chanson_en_cours)


def _cloturer_prochaine_salle(sp, salles, socketio, etat):
    salle = salles[etat.prochaine_salle]
    gagnantes = salle.cloturer_vote()
    logger_tour(salle.nom, salle.tour, salle.chansons, salle.detail_votes_tour, gagnantes)
    etat.file_attente = [dict(c, salle=salle.nom) for c in gagnantes]

    salle.nouveau_tirage(sp)
    socketio.emit(
        'mise_a_jour_votes',
        {'chansons': salle.chansons, 'tour': salle.tour, 'salle': salle.nom},
        room=salle.nom,
    )
    etat.toggle_salle()


def _ajouter_a_spotify(sp, chanson):
    try:
        sp.add_to_queue(chanson['uri'])
        print(f"Ajouté à la file Spotify : {chanson['titre']}")
    except Exception as e:
        print(f"Erreur ajout file Spotify : {e}")
