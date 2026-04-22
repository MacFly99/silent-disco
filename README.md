# Silent Disco

App web de vote musical pour soirée silent disco : les invités votent depuis leur téléphone parmi 3 chansons, la gagnante passe dans la playlist Spotify. Plusieurs salles en parallèle (pop, nostalgie, …), chacune branchée sur un compte Spotify séparé. Configuration des salles **à chaud depuis l'UI admin**, aucun redémarrage nécessaire.

## Stack

- Flask + Flask-SocketIO (temps réel)
- Spotipy (API Spotify + OAuth)
- HTML/CSS/JS vanilla (pas de framework front)
- État en mémoire + logs fichier (pas de DB)
- gunicorn + eventlet pour la prod

## Setup minimal

### 1. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 2. Configurer `.env`

Copier `.env.example` → `.env` et remplir :

```
SPOTIFY_REDIRECT_URI=http://127.0.0.1:5001/callback
PORT=5001
ADMIN_PASSWORD=ton_mot_de_passe
```

> Les credentials Spotify des salles **ne sont plus dans `.env`** — ils se configurent depuis l'UI admin (section "Salles & playlists"). Voir étape 4.

### 3. Lancer l'app

```bash
python app.py
```

### 4. Configurer les salles depuis l'admin

1. Ouvrir http://127.0.0.1:5001/admin/login → entrer le mot de passe
2. Section "Salles & playlists" → cliquer **+ Ajouter une salle**
3. Remplir nom (`pop`), couleur, Client ID, Client Secret, Playlist ID (voir section Spotify plus bas)
4. **Sauvegarder** → la salle est créée à chaud, sa thread démarre
5. Répéter pour chaque salle

### 5. Connecter chaque salle à un compte Spotify (OAuth, une seule fois)

Toujours dans `/admin`, section "Comptes Spotify" :

1. Pastille grise = pas encore connectée. Clic → redirection Spotify → se connecter au compte qui jouera la musique de cette salle
2. Pour la 2e salle avec un autre compte : se déconnecter de spotify.com (ou onglet privé) avant de cliquer
3. Au retour, pastille verte = c'est bon, le cache `.cache-<salle>` est créé

Les tokens sont rafraîchis automatiquement ensuite. L'app se reconnecte seule à chaque restart.

## Créer une app Spotify

Pour chaque salle, créer une app sur https://developer.spotify.com/dashboard :

- **Name** : libre (ex: `Silent Disco Pop`)
- **Redirect URI** : exactement ce qui est dans ton `.env` (`SPOTIFY_REDIRECT_URI`)
- **Which API** : Web API

Récupérer **Client ID** + **Client Secret** dans les Settings, les coller dans l'UI admin.

L'ID de playlist se trouve dans l'URL Spotify : `https://open.spotify.com/playlist/<ID>?si=...`

> **Une seule app Spotify suffit** si toutes tes salles utilisent le même compte (mais alors elles jouent en séquence, pas en vrai parallèle — Spotify = un seul playback par compte). Pour de vraies ambiances simultanées : **une app + un compte Premium par salle**.

## URLs

### Invités

- `/` — accueil (pseudo + choix salle)
- `/vote/<salle>` — voter
- `/display/<salle>` — écran à projeter
- `/stats` — classement (onglets : général / par salle)

### Admin

- `/admin/login` — saisie mot de passe
- `/admin` — config salles + comptes Spotify + logs + archivage

Depuis téléphones sur même Wi-Fi : remplacer `127.0.0.1` par l'IP locale (`ipconfig getifaddr en0` sur macOS).

## Fonctionnement

### Cycle de vote

Pendant qu'une chanson joue, les invités votent parmi 3 candidates. 5 secondes avant la fin :

1. La salle clôture le vote
2. Toutes les chansons avec ≥ 50 % des votes de la gagnante entrent dans la file d'attente
3. La première passe dans la queue Spotify
4. 3 nouvelles chansons sont tirées pour le tour suivant

Chaque salle est **indépendante** : son compte Spotify, sa queue, sa thread de surveillance. Aucune alternance, aucune coordination.

### Pseudo + UUID

À l'accueil, saisie du pseudo → UUID généré côté client (`localStorage`). Chaque vote porte pseudo + UUID. Les stats sont agrégées par UUID (le pseudo peut changer).

### Logs

| Fichier | Contenu |
| --- | --- |
| `logs/votes-YYYY-MM-DD.log` | Une ligne par vote individuel |
| `logs/tours-YYYY-MM-DD.log` | Résumé par tour (3 chansons, votants, file d'attente) |
| `logs/users.log` | Append-only : nouveaux users + changements de pseudo |
| `logs/user_stats.json` | État agrégé : pseudo, votes total, par salle, timestamps |
| `logs/archive/<ts>_<type>/` | Archives créées depuis l'admin (jamais supprimées) |

## CLI

```bash
python app.py                 # normal
python app.py --clear         # fresh start : efface user_stats.json + users.log
python app.py --seed          # ajoute ~50 users fake (pour tester /stats)
python app.py --seed-clear    # fresh start + fakes
```

## Architecture

```
silent-disco/
├── app.py                    # Init Flask, manager, câblage, lancement
├── config_salles.py          # I/O config/salles.json (avec lock)
├── salle_manager.py          # Orchestration cycle de vie des salles (add/modify/remove à chaud)
├── salle.py                  # Classe Salle (pool, votes, auth Spotify)
├── spotify_sync.py           # Surveillance Spotify (une thread par salle, stoppable)
├── routes_public.py          # /, /vote, /display, /stats, /login, /callback
├── routes_admin.py           # /admin/* (mot de passe) + CRUD salles + logs
├── sockets.py                # Handlers SocketIO
├── logs_util.py              # logger_vote, logger_tour
├── admin.py                  # Listing / archivage des logs
├── stats.py                  # user_stats.json + classement
├── seed_fake_data.py         # Génération de données factices
├── gunicorn_conf.py          # Config gunicorn (prod)
├── config/
│   └── salles.json           # Config éditable via UI admin (gitignored)
├── static/                   # CSS + JS
├── templates/                # HTML (Jinja2)
├── logs/                     # Runtime (gitignored)
├── .env                      # Secrets machine (gitignored)
├── .env.example              # Template
└── .cache-<salle>            # Tokens Spotify par salle (gitignored)
```

## Déploiement sur NAS / VPS / domaine

### 1. Serveur de prod (gunicorn + eventlet)

Le serveur Flask dev (`python app.py`) n'est **pas** fait pour la prod. En prod :

```bash
gunicorn -c gunicorn_conf.py app:app
```

`gunicorn_conf.py` est déjà fourni, configuré avec 1 worker eventlet (requis par Flask-SocketIO).

### 2. HTTPS obligatoire

Spotify exige HTTPS pour les redirect URIs en production (pas en dev local via `127.0.0.1`). À mettre devant :

- **Synology** : Control Panel → Login Portal → Advanced → Reverse Proxy. Ajouter une entrée `silentdisco.tondomaine.com` → `http://127.0.0.1:5001`. Activer HTTPS avec un cert Let's Encrypt.
- **nginx standalone** : reverse proxy classique avec certbot pour Let's Encrypt.

Une fois le domaine actif, dans `.env` :
```
SPOTIFY_REDIRECT_URI=https://silentdisco.tondomaine.com/callback
```

Et dans chaque app Spotify dashboard, remplacer la Redirect URI par cette URL.

### 3. Mode "Extended Quota" sur l'app Spotify

En mode développement Spotify, seuls les users whitelistés (max 25) peuvent s'auth sur ton app. Pour passer en production (plus de limite), c'est dans le dashboard de l'app Spotify → "Request extension". Pour silent disco, le dev mode est largement suffisant : tu whitelistes juste les 1 ou 2 comptes qui vont jouer la musique.

### 4. Variables d'env en prod

Plutôt que `.env`, sur un NAS / Docker, passe les vars via le système d'init :

```bash
ADMIN_PASSWORD=... PORT=5001 SPOTIFY_REDIRECT_URI=... gunicorn -c gunicorn_conf.py app:app
```

Ou via systemd / Docker `ENV` / docker-compose `environment:`.

## Limitations connues

- État en mémoire : un restart efface les votes en cours. À lancer une fois par soirée, ne pas redémarrer pendant.
- Un vote par IP par tour (simple, contournable via NAT). Pas de vraie authent.
- 1 worker eventlet uniquement : au-delà de ~100 connexions simultanées, il faudrait un message queue Redis (pour sharder entre workers SocketIO).
- Pas de backup automatique de `config/salles.json` — si tu changes des creds par erreur, c'est écrasé. Pense à le copier ailleurs avant un gros changement.
