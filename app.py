"""Silent Disco — entry point : init Flask, salles, threads, câble les routes."""

import os
import time
from threading import Thread

from dotenv import load_dotenv
from flask import Flask
from flask_socketio import SocketIO

from routes_admin import register_admin_routes
from routes_public import register_public_routes
from salle import Salle
from sockets import register_sockets
from spotify_sync import demarrer_surveillance_salle

load_dotenv()

# --- Flask / SocketIO ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'musique2024'
socketio = SocketIO(app)

# --- Salles ---
# Une salle = une playlist + un compte Spotify (cache séparé).
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

# --- Wire-up ---
register_public_routes(app, socketio, salles)
register_admin_routes(app)
register_sockets(socketio, salles)


# --- Démarrage en arrière-plan : chaque salle a sa propre thread ---

def demarrer():
    time.sleep(1)
    for salle in salles.values():
        if salle.est_authentifie():
            try:
                salle.initialiser_pool()
                salle.nouveau_tirage()
            except Exception as e:
                print(f"[{salle.nom}] init pool impossible : {e}")
        Thread(
            target=demarrer_surveillance_salle,
            args=(salle, socketio),
            daemon=True,
        ).start()


Thread(target=demarrer, daemon=True).start()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port, debug=True,
                 allow_unsafe_werkzeug=True, use_reloader=False)
