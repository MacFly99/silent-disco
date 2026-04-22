# Silent Disco

App web de vote musical pour soirée silent disco : les invités votent depuis leur téléphone parmi 3 chansons, la gagnante passe dans la playlist Spotify. Deux salles en parallèle (pop + nostalgie), chacune branchée sur un compte Spotify séparé.

## Stack

- Flask + Flask-SocketIO (temps réel)
- Spotipy (API Spotify + OAuth)
- HTML/CSS/JS vanilla (pas de framework front)
- État en mémoire + logs fichier (pas de DB)

## Setup initial

### 1. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 2. Créer les apps Spotify

Pour chaque salle, créer une app sur https://developer.spotify.com/dashboard :

- Name : `Silent Disco Pop` / `Silent Disco Nostalgie`
- Redirect URI : `http://127.0.0.1:5001/callback`
- Which API : Web API

Noter le **Client ID** et **Client Secret** de chaque app.

> Astuce : une seule app Spotify suffit si les deux salles utilisent le même compte. Mais pour vraiment jouer en parallèle sur deux enceintes, il faut **deux comptes Spotify Premium** distincts (`add_to_queue` ne fonctionne pas en gratuit).

### 3. Configurer `.env`

Copier `.env.example` en `.env` et remplir :

```
SPOTIFY_REDIRECT_URI=http://127.0.0.1:5001/callback

SPOTIFY_POP_CLIENT_ID=...
SPOTIFY_POP_CLIENT_SECRET=...
SPOTIFY_POP_PLAYLIST_ID=...

SPOTIFY_NOSTALGIE_CLIENT_ID=...
SPOTIFY_NOSTALGIE_CLIENT_SECRET=...
SPOTIFY_NOSTALGIE_PLAYLIST_ID=...

PORT=5001
ADMIN_PASSWORD=change_me
```

L'ID de playlist se trouve dans l'URL Spotify : `https://open.spotify.com/playlist/<ID>?si=...`

### 4. Premier lancement + OAuth

```bash
python app.py
```

Une fois par salle (le cache `.cache-<salle>` persiste après) :

1. Ouvrir http://127.0.0.1:5001/login/pop → se connecter au compte Spotify A
2. Se déconnecter de spotify.com (ou onglet privé)
3. Ouvrir http://127.0.0.1:5001/login/nostalgie → se connecter au compte B

Les liens sont aussi disponibles depuis la page `/admin`.

Après ces 2 OAuth, l'app se reconnecte toute seule à chaque `python app.py`.

## Utilisation

### URLs invités

- http://127.0.0.1:5001/ — accueil (saisie pseudo + choix salle)
- http://127.0.0.1:5001/vote/pop — voter dans la salle pop
- http://127.0.0.1:5001/vote/nostalgie — voter dans la salle nostalgie
- http://127.0.0.1:5001/display/pop — écran à projeter (pop)
- http://127.0.0.1:5001/display/nostalgie — écran à projeter (nostalgie)
- http://127.0.0.1:5001/stats — classement des votants (3 onglets : général / pop / nostalgie)

### URLs admin

- http://127.0.0.1:5001/admin/login — saisie du mot de passe
- http://127.0.0.1:5001/admin — visualisation des logs + archivage + liens OAuth Spotify

Depuis un téléphone sur le même Wi-Fi, remplacer `127.0.0.1` par l'IP locale (`ipconfig getifaddr en0` sur macOS).

## Comment ça marche

### Cycle de vote

Pendant qu'une chanson joue, les invités votent parmi 3 candidates. 5 secondes avant la fin :

1. La salle clôture le vote
2. Toutes les chansons avec ≥ 50 % des votes de la gagnante entrent dans la file d'attente
3. La première passe dans la queue Spotify
4. 3 nouvelles chansons sont tirées pour le tour suivant

Chaque salle est **indépendante** : propre compte Spotify, propre queue, propre surveillance. Elles tournent en parallèle sur deux enceintes.

### Pseudo + UUID

- À l'accueil, l'invité saisit un pseudo → généré un UUID stocké dans `localStorage` (persistant)
- Chaque vote inclut le pseudo + l'UUID
- Les stats sont agrégées par UUID (pseudo peut changer, l'UUID reste)

### Logs

Tout est dans `logs/` :

| Fichier | Contenu |
| --- | --- |
| `votes-YYYY-MM-DD.log` | Une ligne par vote individuel |
| `tours-YYYY-MM-DD.log` | Résumé par tour (3 chansons, qui a voté pour quoi, file d'attente) |
| `users.log` | Append-only : nouveaux users + changements de pseudo |
| `user_stats.json` | État agrégé : pseudo, votes total, votes par salle, premier/dernier vote |
| `archive/<timestamp>_<type>/` | Archives créées depuis l'admin (pas de suppression) |

## Lancement

```bash
python app.py                 # normal
python app.py --clear         # fresh start : efface user_stats.json + users.log
python app.py --seed          # ajoute ~50 users fake avec votes aléatoires (pour tester /stats)
python app.py --seed-clear    # fresh start + fakes
```

## Architecture

```
silent-disco/
├── app.py                    # Entry point : init Flask, salles, threads, wire-up
├── routes_public.py          # Routes publiques (/, /vote, /display, /stats, /login, /callback)
├── routes_admin.py           # Routes admin (avec décorateur admin_requis)
├── sockets.py                # Handlers SocketIO (rejoindre_salle, voter)
├── salle.py                  # Classe Salle (pool, votes, auth Spotify)
├── spotify_sync.py           # Surveillance Spotify par salle (thread dédiée)
├── logs_util.py              # logger_vote, logger_tour
├── admin.py                  # Listing / archivage des logs
├── stats.py                  # user_stats.json + classement
├── seed_fake_data.py         # Génération de données factices pour test
├── static/
│   ├── css/                  # base.css (vars), vote.css, display.css, landing.css, stats.css, admin.css
│   └── js/                   # vote.js, display.js, landing.js, admin.js
├── templates/                # base.html, index.html, vote.html, display.html, stats.html, admin.html, admin_login.html
├── logs/                     # logs runtime (gitignored)
├── .env                      # secrets (gitignored)
├── .env.example              # template à copier
└── .cache-<salle>            # tokens Spotify par salle (gitignored)
```

### Données stockées

- **En mémoire** (perdu au restart) : état des salles (chansons en cours, votes du tour, file d'attente, chanson en cours), sessions admin
- **Sur disque** : logs, stats users (`user_stats.json`), tokens Spotify (`.cache-<salle>`)

## Administration

Page `/admin` (mot de passe dans `.env`) :

- **Comptes Spotify** : pastilles vertes = connecté, clic pour (re)connecter
- **Archivage** : boutons "Archiver votes / tours / users" avec double confirmation (taper `CONFIRMER`). Les fichiers sont déplacés dans `logs/archive/<timestamp>_<type>/`, jamais supprimés.
- **Téléchargement** : chaque fichier de log courant est téléchargeable directement.

## Limitations connues

- État en mémoire : un restart efface les votes en cours. À lancer une fois, ne pas redémarrer pendant la soirée.
- Un seul vote par IP par tour (simple mais contournable). L'UUID dans `localStorage` aide au tracking, mais ne limite pas les votes.
- Mode développement Flask/Werkzeug : ne pas exposer publiquement sur internet, utiliser gunicorn + nginx si besoin.
- OAuth Spotify en mode développement : le compte connecté doit être whitelisté dans l'app Spotify (onglet "Users and Access"), ou l'app doit être passée en production mode sur le dashboard.
