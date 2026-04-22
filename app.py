import os
import time
from threading import Thread

from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, url_for
from flask_socketio import SocketIO, emit, join_room

from logs_util import logger_vote
from salle import Salle
from spotify_setup import build_auth_manager, build_client
from spotify_sync import EtatGlobal, demarrer_surveillance

load_dotenv()

# --- Flask / SocketIO ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'musique2024'
socketio = SocketIO(app)

# --- Spotify ---
auth_manager = build_auth_manager()
sp = build_client(auth_manager)

# --- Salles ---
# Chaque salle a sa propre playlist, son pool et son état de vote.
# L'ordre compte : l'alternance pour la queue Spotify suit cet ordre.
salles = {}
playlist_pop = os.environ.get('SPOTIFY_PLAYLIST_ID_POP') or os.environ.get('SPOTIFY_PLAYLIST_ID')
if playlist_pop:
    salles['pop'] = Salle('pop', playlist_pop, couleur='#3b82f6')

playlist_nostalgie = os.environ.get('SPOTIFY_PLAYLIST_ID_NOSTALGIE')
if playlist_nostalgie:
    salles['nostalgie'] = Salle('nostalgie', playlist_nostalgie, couleur='#1DB954')

if not salles:
    raise RuntimeError(
        "Aucune playlist configurée. Définis SPOTIFY_PLAYLIST_ID_POP "
        "et/ou SPOTIFY_PLAYLIST_ID_NOSTALGIE dans .env."
    )

etat = EtatGlobal(ordre_salles=list(salles.keys()))


# --- Démarrage en arrière-plan ---

def demarrer():
    time.sleep(1)
    for salle in salles.values():
        salle.initialiser_pool(sp)
        salle.nouveau_tirage(sp)
    demarrer_surveillance(sp, salles, socketio, etat)


# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html', salles=list(salles.values()))


@app.route('/login')
def login():
    return redirect(auth_manager.get_authorize_url())


@app.route('/callback')
def callback():
    code = request.args.get('code')
    auth_manager.get_access_token(code)
    premiere = next(iter(salles.keys()))
    liens = ''.join(f"<li><a href='/display/{n}'>/display/{n}</a> · <a href='/vote/{n}'>/vote/{n}</a></li>" for n in salles)
    return f"<p>Authentification réussie.</p><ul>{liens}</ul>"


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
    emit('file_attente', {'file': etat.file_attente})
    if etat.chanson_en_cours['titre']:
        emit('chanson_en_cours', etat.chanson_en_cours)


@socketio.on('voter')
def on_vote(data):
    ip = request.remote_addr
    salle_nom = (data or {}).get('salle')
    chanson_id = (data or {}).get('chanson_id')
    pseudo = ((data or {}).get('pseudo') or 'anonyme').strip()[:30] or 'anonyme'

    salle = salles.get(salle_nom)
    if salle is None:
        emit('erreur', {'message': 'Salle inconnue'})
        return

    chanson = salle.ajouter_vote(chanson_id, pseudo, ip)
    if chanson is None:
        emit('erreur', {'message': 'Tu as déjà voté !'})
        return

    logger_vote(salle.nom, pseudo, ip, chanson)
    socketio.emit(
        'mise_a_jour_votes',
        {'chansons': salle.chansons, 'tour': salle.tour, 'salle': salle.nom},
        room=salle.nom,
    )


# --- Lancement ---

Thread(target=demarrer, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port, debug=True,
                 allow_unsafe_werkzeug=True, use_reloader=False)
