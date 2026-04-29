"""Handlers SocketIO : rejoindre une salle, voter."""

from flask import request
from flask_socketio import emit, join_room

from logs_util import logger_vote
from stats import enregistrer_vote


def _ip_reelle():
    """
    Récupère l'IP du client réel derrière Cloudflare / Caddy.
    Priorité : CF-Connecting-IP (Cloudflare) > X-Forwarded-For > remote_addr.
    """
    cf = request.headers.get('CF-Connecting-IP')
    if cf:
        return cf.strip()
    xff = request.headers.get('X-Forwarded-For')
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr


def register_sockets(socketio, manager):

    @socketio.on('rejoindre_salle')
    def on_rejoindre(data):
        salle_nom = (data or {}).get('salle')
        salle = manager.get(salle_nom)
        if salle is None:
            return
        join_room(salle_nom)
        emit('mise_a_jour_votes', {
            'chansons': salle.chansons,
            'tour': salle.tour,
            'salle': salle.nom,
        })
        emit('file_attente', {'file': salle.file_attente})
        if salle.chanson_en_cours['titre']:
            emit('chanson_en_cours', {**salle.chanson_en_cours, 'salle': salle.nom})

    @socketio.on('voter')
    def on_vote(data):
        ip = _ip_reelle()
        salle_nom = (data or {}).get('salle')
        chanson_id = (data or {}).get('chanson_id')
        pseudo = ((data or {}).get('pseudo') or 'anonyme').strip()[:30] or 'anonyme'
        user_uuid = (data or {}).get('uuid')

        salle = manager.get(salle_nom)
        if salle is None:
            emit('erreur', {'message': 'Salle inconnue'})
            return

        chanson = salle.ajouter_vote(chanson_id, pseudo, ip)
        if chanson is None:
            emit('erreur', {'message': 'Tu as déjà voté !'})
            return

        logger_vote(salle.nom, pseudo, ip, chanson)
        enregistrer_vote(user_uuid, pseudo, salle.nom)
        socketio.emit(
            'mise_a_jour_votes',
            {'chansons': salle.chansons, 'tour': salle.tour, 'salle': salle.nom},
            room=salle.nom,
        )
