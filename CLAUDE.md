# CLAUDE.md — Silent Disco

Instructions pour Claude qui travaille sur ce projet. Lire en premier.

## Contexte

App Flask pour soirée silent disco. **Cible : jusqu'à ~100 invités simultanés** (vraies soirées, pas un démo). Une-soirée = perd l'état au restart, pas une appli "production" 24/7 critique.

**Pragmatique > parfait.** Pas de SOLID strict, pas de tests, pas d'abstractions inutiles. Le projet n'a aucun rapport avec les conventions Connectic — on fait du Python/Flask/HTML simple.

**Considérations charge :**
- 1 worker gunicorn + eventlet supporte 500-1000 connexions WebSocket. Soirée à 200-300 personnes : tranquille.
- Goulot principal sous très grosse charge : le lock sur `user_stats.json` (lecture+écriture sérialisée par vote, ~5-10ms). À ~500+ votes par seconde ça commence à traîner. Solution : SQLite WAL ou simplement désactiver le live update du compteur.
- À 1000+ : multi-worker + `message_queue=redis://...` dans `flask_socketio.SocketIO`.
- **Ne JAMAIS redémarrer l'app pendant la soirée** : l'état runtime (votes en cours, file d'attente, tour) est en RAM.

## Stack & archi

- Flask + Flask-SocketIO + Spotipy
- HTML/CSS/JS vanilla (templates Jinja, statics dans `static/`)
- État runtime en mémoire ; persistance sur disque via fichiers (logs, JSON config, caches OAuth)
- Multi-salles : chaque salle = sa playlist + son compte Spotify + sa thread de surveillance, indépendantes
- Déploiement : Docker (`Dockerfile` + `docker-compose.yml`), gunicorn + eventlet en prod (eventlet nécessaire pour SocketIO)

## Fichiers clés

| Fichier | Rôle |
| --- | --- |
| `app.py` | Entry point. Crée Flask + SocketIO + manager, câble les routes, lance les threads |
| `salle.py` | Classe `Salle` : état du vote + auth Spotify + pool playlist |
| `salle_manager.py` | Cycle de vie : `charger_depuis_config`, `rebuild`, démarre/arrête les threads, nettoie les caches orphelins |
| `config_salles.py` | I/O thread-safe de `config/salles.json` ; migration auto depuis `.env` au premier lancement |
| `spotify_sync.py` | Boucle de surveillance par salle, stoppable via `salle.stop_flag` |
| `routes_public.py`, `routes_admin.py`, `sockets.py` | Découpés par responsabilité, pattern `register_xxx(app, ...)` |
| `stats.py`, `logs_util.py`, `admin.py` | Helpers pour stats, logs, archivage |

## Conventions à respecter

### Configuration
- **Credentials Spotify (client_id/secret/playlist_id) ne vont JAMAIS dans `.env`** — uniquement dans `config/salles.json`, éditable via l'UI admin.
- `.env` contient seulement la config machine : `SPOTIFY_REDIRECT_URI`, `PORT`, `ADMIN_PASSWORD`, `SECRET_KEY`, optionnel `SPOTIFY_CACHE_DIR`.
- Migration historique : si l'utilisateur a un vieux `.env` avec `SPOTIFY_POP_*`, c'est migré automatiquement à la première exécution puis ignoré.

### IP réelle (anti-NAT proxy)
L'app tourne souvent derrière Cloudflare + Caddy. `request.remote_addr` retourne alors l'IP du proxy → tous les votants partagent la même IP. **Toujours utiliser `_ip_reelle()`** (présent dans `routes_public.py` et `sockets.py`) qui priorise `CF-Connecting-IP` > `X-Forwarded-For` > `remote_addr`.

### Restart
`debug=True` mais `use_reloader=False` (volontaire — le reloader créerait deux threads de surveillance Spotify). **Tout changement Python nécessite un restart manuel** (`Ctrl+C` + `python app.py` ou `docker compose restart`). Les templates Jinja, eux, sont rechargés à chaque requête en debug.

### Threads & shutdown propre
La boucle de surveillance utilise `salle.stop_flag.wait(2)` plutôt que `time.sleep(2)` → réveil immédiat si la salle est demandée à l'arrêt (utilisé par `manager.rebuild`). Si tu modifies cette boucle, garde ce pattern.

### Couleurs des salles
Dynamiques, pas hardcodées par nom. La couleur (hex) vient de la config, et `Salle.couleur_rgb` (property) retourne le format `"r, g, b"` pour usage dans `rgba(var(--..-rgb), alpha)`.
- `templates/base.html` : injecte `--accent` et `--accent-rgb` inline sur `<body>` pour les pages vote/display
- `templates/index.html` : injecte `--c1-rgb` / `--c2-rgb` (les 2 premières salles) pour la landing
- Pas de règles CSS du genre `body.salle-pop { ... }` — tout passe par les CSS vars

### Jinja gotchas connus
- **`{% set %}` à l'intérieur de `{% if %}` ne sort pas du scope du bloc** — utiliser des branches `{% if %} ... {% else %} ... {% endif %}` qui contiennent chacune le rendu, ou un `{% set ns = namespace() %}` extérieur
- **`c.items` sur un dict** retourne la méthode built-in `dict.items()`, pas la clé `'items'` — toujours utiliser `c['items']` ou renommer la clé

### Logs
- `logs/votes-*.log` : append-only, une ligne par vote
- `logs/tours-*.log` : append-only, résumé par tour
- `logs/users.log` : append-only, nouveaux users + changements pseudo
- `logs/user_stats.json` : k/v par UUID, écrit atomiquement (`.tmp` + rename), lock dans `stats.py`
- Archivage admin : déplace dans `logs/archive/<ts>_<type>/`, ne supprime jamais

### OAuth Spotify
- Flow standard : `/login/<salle>` redirige vers Spotify → `/callback?state=<salle>&code=...`
- `state` identifie la salle (Spotipy le passe via `get_authorize_url(state=...)`)
- Tokens cachés dans `caches/.cache-<salle>` (path configurable via `SPOTIFY_CACHE_DIR`), Spotipy auto-refresh
- Si `client_id` change pour une salle, le manager invalide automatiquement le cache → `/login/<salle>` à refaire
- Le manager nettoie les caches orphelins (`.cache-<nom>` dont la salle n'existe plus) au load et après chaque rebuild

## Commandes

```bash
# Dev local
python app.py
python app.py --clear        # efface user_stats + users.log
python app.py --seed         # +50 fakes
python app.py --seed-clear   # fresh + fakes

# Docker
docker compose up -d --build
docker compose logs -f silent-disco
```

## Quand l'utilisateur dit...
- **"Ça plante"** → demander quelle action a été faite, regarder les logs (`docker compose logs`), vérifier `config/salles.json` et `caches/.cache-<salle>`
- **"Pas de couleur"** → vérifier que les CSS vars sont bien injectées via inline style sur `<body>` (curl le HTML pour voir)
- **"Tu as déjà voté !" alors qu'il y a plusieurs personnes** → IP partagée derrière proxy, vérifier que `_ip_reelle()` est bien utilisée et que Cloudflare/Caddy passe les bons headers
- **"redirect_uri: Not matching"** → Spotify dashboard, ajouter exactement la valeur de `SPOTIFY_REDIRECT_URI` dans Redirect URIs de l'app
- **"Bad Request" sur callback** → souvent Spotify a renvoyé `?error=...`, le plus souvent un `state` qui ne matche pas une salle (creds bidons dans la config) ou app pas whitelistée

## À ne PAS faire

- Ne pas remettre les credentials Spotify dans `.env`
- Ne pas hardcoder les couleurs par nom de salle (`body.salle-pop {...}`) — c'est dynamique
- Ne pas activer `use_reloader=True` (double thread Spotify, queue dupliquée, gros bordel)
- Ne pas commit `config/salles.json`, `.cache-*`, `.env`, `logs/` — tous gitignored
- Ne pas créer de tests / CI / docs en plus, sauf si demandé explicitement (c'est une app de soirée, pas un produit)
