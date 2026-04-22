import json
import os
import threading
from datetime import datetime

LOGS_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

USERS_LOG = os.path.join(LOGS_DIR, 'users.log')
STATS_FILE = os.path.join(LOGS_DIR, 'user_stats.json')

_lock = threading.Lock()


def _load():
    if not os.path.exists(STATS_FILE):
        return {}
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(stats):
    tmp = STATS_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATS_FILE)


def _append_users_log(ligne):
    with open(USERS_LOG, 'a', encoding='utf-8') as f:
        f.write(ligne + '\n')


def enregistrer_vote(user_uuid, pseudo):
    """Crée l'entrée utilisateur si nouvelle, sinon incrémente le compteur."""
    if not user_uuid:
        return
    now = datetime.now().isoformat(timespec='seconds')
    with _lock:
        stats = _load()
        entry = stats.get(user_uuid)

        if entry is None:
            stats[user_uuid] = {
                'pseudo': pseudo,
                'votes': 1,
                'first_seen': now,
                'last_vote': now,
            }
            _append_users_log(f'{now} | NOUVEAU | {user_uuid} | {pseudo}')
        else:
            if entry['pseudo'] != pseudo:
                _append_users_log(
                    f'{now} | CHANGEMENT | {user_uuid} | {entry["pseudo"]} -> {pseudo}'
                )
                entry['pseudo'] = pseudo
            entry['votes'] += 1
            entry['last_vote'] = now

        _save(stats)


def obtenir_classement():
    """Retourne la liste triée par votes décroissants."""
    stats = _load()
    items = list(stats.values())
    items.sort(key=lambda u: (u['votes'], u['last_vote']), reverse=True)
    return items
