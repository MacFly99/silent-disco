import time
from logs_util import logger_tour


def demarrer_surveillance_salle(salle, socketio):
    """Boucle infinie pour UNE salle : poll son Spotify, gère ses votes, queue ses gagnantes."""
    # Synchronisation du titre initial (évite un faux changement au démarrage)
    if salle.est_authentifie():
        try:
            current = salle.sp.current_playback()
            if current and current['item']:
                salle.titre_en_cours = current['item']['name']
                print(f"[{salle.nom}] chanson initiale : {salle.titre_en_cours}")
        except Exception as e:
            print(f"[{salle.nom}] lecture initiale impossible : {e}")

    while True:
        try:
            if salle.est_authentifie():
                current = salle.sp.current_playback()
                if current and current['item']:
                    _traiter_tick(salle, socketio, current)
        except Exception as e:
            print(f"[{salle.nom}] erreur surveillance : {e}")
        time.sleep(2)


def _traiter_tick(salle, socketio, current):
    nouveau_titre = current['item']['name']
    progression = current['progress_ms']
    duree = current['item']['duration_ms']
    temps_restant = duree - progression

    # Changement de chanson : reset du flag, pop de la file d'attente
    if nouveau_titre != salle.titre_en_cours:
        print(f"[{salle.nom}] changement : '{salle.titre_en_cours}' -> '{nouveau_titre}'")
        salle.titre_en_cours = nouveau_titre
        salle.vote_calcule = False
        if salle.file_attente:
            salle.file_attente.pop(0)
            socketio.emit('file_attente', {'file': salle.file_attente}, room=salle.nom)

    # Fin imminente : on clôture le vote et on queue la gagnante
    if temps_restant < 5000 and not salle.vote_calcule:
        print(f"[{salle.nom}] fin imminente ({temps_restant}ms)")
        salle.vote_calcule = True

        if not salle.file_attente:
            gagnantes = salle.cloturer_vote()
            logger_tour(salle.nom, salle.tour, salle.chansons, salle.detail_votes_tour, gagnantes)
            salle.file_attente = list(gagnantes)
            salle.nouveau_tirage()
            socketio.emit(
                'mise_a_jour_votes',
                {'chansons': salle.chansons, 'tour': salle.tour, 'salle': salle.nom},
                room=salle.nom,
            )

        if salle.file_attente:
            _ajouter_a_spotify(salle, salle.file_attente[0])
            socketio.emit('file_attente', {'file': salle.file_attente}, room=salle.nom)

    # Diffusion de l'état de lecture
    salle.chanson_en_cours = {
        'titre': nouveau_titre,
        'artiste': current['item']['artists'][0]['name'],
        'pochette': current['item']['album']['images'][0]['url'],
        'progression_ms': progression,
        'duree_ms': duree,
        'en_lecture': current['is_playing'],
    }
    socketio.emit('chanson_en_cours', salle.chanson_en_cours, room=salle.nom)


def _ajouter_a_spotify(salle, chanson):
    try:
        salle.sp.add_to_queue(chanson['uri'])
        print(f"[{salle.nom}] ajouté à la queue : {chanson['titre']}")
    except Exception as e:
        print(f"[{salle.nom}] erreur add_to_queue : {e}")
