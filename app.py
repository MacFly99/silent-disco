"""Silent Disco — entry point : init Flask, manager, câble les routes.

Options CLI :
  --clear       Efface user_stats.json et users.log avant de lancer
  --seed        Ajoute ~50 users fake avec votes aléatoires (pour tester /stats)
  --seed-clear  --clear + --seed
"""

import os
import sys

from dotenv import load_dotenv
from flask import Flask
from flask_socketio import SocketIO

from routes_admin import register_admin_routes
from routes_public import register_public_routes
from salle_manager import SalleManager
from sockets import register_sockets

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'musique2024')
socketio = SocketIO(app)

# --- Manager qui orchestre les salles (config/salles.json) ---
manager = SalleManager(socketio)
manager.charger_depuis_config()

# --- Wire-up ---
register_public_routes(app, socketio, manager)
register_admin_routes(app, manager)
register_sockets(socketio, manager)


if __name__ == '__main__':
    do_clear = '--clear' in sys.argv or '--seed-clear' in sys.argv
    do_seed = '--seed' in sys.argv or '--seed-clear' in sys.argv

    if do_clear:
        from seed_fake_data import STATS_FILE, USERS_LOG
        for path in (STATS_FILE, USERS_LOG):
            try:
                os.remove(path)
                print(f"✓ {os.path.basename(path)} effacé")
            except OSError:
                pass

    if do_seed:
        from seed_fake_data import seed
        seed(clear_first=False)

    port = int(os.environ.get('PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port, debug=True,
                 allow_unsafe_werkzeug=True, use_reloader=False)
