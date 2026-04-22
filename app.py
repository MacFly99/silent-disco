import os
import time
from functools import wraps
from threading import Thread

from dotenv import load_dotenv
from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_file, session, url_for)
from flask_socketio import SocketIO, emit, join_room

import admin
from logs_util import logger_vote
from salle import Salle
from spotify_sync import demarrer_surveillance_salle
from stats import enregistrer_vote, obtenir_classement

load_dotenv()

# --- Flask / SocketIO ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'musique2024'
socketio = SocketIO(app)

# --- Salles ---
# Chaque salle a son propre compte Spotify (credentials + cache séparés).
SALLES_CONFIG = [
    ('pop', '#3b82f6'),
    ('nostalgie', '#1DB954'),
]

salles = {}
for nom, couleur in SALLES_CONFIG:
    prefixe = f'SPOTIFY_{nom.upper()}'
    if all(os.environ.get(f'{prefixe}_{k}') for k in ('CLIENT_ID', 'CLIENT_SECRET', 'PLAYLIST_ID')):
        salles[nom] = Salle(nom, couleur=couleur)

if not salles:
    raise RuntimeError(
        "Aucune salle configurée. Définis dans .env :\n"
        "  SPOTIFY_POP_CLIENT_ID, SPOTIFY_POP_CLIENT_SECRET, SPOTIFY_POP_PLAYLIST_ID\n"
        "et/ou équivalents pour NOSTALGIE."
    )


# --- Démarrage en arrière-plan ---

def demarrer():
    time.sleep(1)
    for salle in salles.values():
        # Si déjà auth (cache présent), initialise le pool tout de suite
        if salle.est_authentifie():
            try:
                salle.initialiser_pool()
                salle.nouveau_tirage()
            except Exception as e:
                print(f"[{salle.nom}] init pool impossible : {e}")
        # La thread tourne toujours : elle reprend dès qu'une auth est complétée
        Thread(
            target=demarrer_surveillance_salle,
            args=(salle, socketio),
            daemon=True,
        ).start()


# --- Routes publiques ---

@app.route('/')
def index():
    return render_template('index.html', salles=list(salles.values()))


@app.route('/vote/<salle_nom>')
def vote(salle_nom):
    salle = salles.get(salle_nom)
    if salle is None:
        abort(404)
    deja_vote = salle.a_vote(request.remote_addr)
    return render_template('vote.html', salle=salle, deja_vote=deja_vote)


@app.route('/display/<salle_nom>')
def display(salle_nom):
    salle = salles.get(salle_nom)
    if salle is None:
        abort(404)
    return render_template('display.html', salle=salle)


@app.route('/stats')
def stats_page():
    return render_template('stats.html', classement=obtenir_classement())


# --- SocketIO ---

@socketio.on('rejoindre_salle')
def on_rejoindre(data):
    salle_nom = (data or {}).get('salle')
    if salle_nom not in salles:
        return
    join_room(salle_nom)
    salle = salles[salle_nom]
    emit('mise_a_jour_votes', {
        'chansons': salle.chansons,
        'tour': salle.tour,
        'salle': salle.nom,
    })
    emit('file_attente', {'file': salle.file_attente})
    if salle.chanson_en_cours['titre']:
        emit('chanson_en_cours', salle.chanson_en_cours)


@socketio.on('voter')
def on_vote(data):
    ip = request.remote_addr
    salle_nom = (data or {}).get('salle')
    chanson_id = (data or {}).get('chanson_id')
    pseudo = ((data or {}).get('pseudo') or 'anonyme').strip()[:30] or 'anonyme'
    user_uuid = (data or {}).get('uuid')

    salle = salles.get(salle_nom)
    if salle is None:
        emit('erreur', {'message': 'Salle inconnue'})
        return

    chanson = salle.ajouter_vote(chanson_id, pseudo, ip)
    if chanson is None:
        emit('erreur', {'message': 'Tu as déjà voté !'})
        return

    logger_vote(salle.nom, pseudo, ip, chanson)
    enregistrer_vote(user_uuid, pseudo)
    socketio.emit(
        'mise_a_jour_votes',
        {'chansons': salle.chansons, 'tour': salle.tour, 'salle': salle.nom},
        room=salle.nom,
    )


# --- Admin : auth + logs + connexion Spotify par salle ---

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')


def _admin_requis(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return view(*args, **kwargs)
    return wrapped


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    erreur = None
    if request.method == 'POST':
        pwd = request.form.get('password', '')
        if ADMIN_PASSWORD and pwd == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_page'))
        erreur = 'Mot de passe incorrect'
    return render_template('admin_login.html', erreur=erreur)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
@_admin_requis
def admin_page():
    fichiers = admin.lister_fichiers_logs()
    tails = {f['nom']: admin.lire_tail(f['nom'], n=30) for f in fichiers}
    auth_statuses = [
        {'nom': s.nom, 'couleur': s.couleur, 'authentifie': s.est_authentifie()}
        for s in salles.values()
    ]
    return render_template(
        'admin.html',
        fichiers=fichiers,
        tails=tails,
        types=list(admin.TYPES.keys()),
        auth_statuses=auth_statuses,
    )


@app.route('/admin/spotify/login/<salle_nom>')
@_admin_requis
def admin_spotify_login(salle_nom):
    salle = salles.get(salle_nom)
    if salle is None:
        abort(404)
    return redirect(salle.authorize_url())


@app.route('/admin/archiver/<log_type>', methods=['POST'])
@_admin_requis
def admin_archiver(log_type):
    deplaces = admin.archiver_type(log_type)
    return jsonify({'archived': deplaces})


@app.route('/admin/download/<path:nom_fichier>')
@_admin_requis
def admin_download(nom_fichier):
    chemin = admin.chemin_fichier_log(nom_fichier)
    if chemin is None:
        abort(404)
    return send_file(chemin, as_attachment=True)


# --- Lancement ---

Thread(target=demarrer, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port, debug=True,
                 allow_unsafe_werkzeug=True, use_reloader=False)
