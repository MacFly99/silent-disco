# Silent Disco

App web de vote musical pour soirée silent disco : les invités votent depuis leur téléphone parmi 3 chansons, la gagnante passe dans la playlist Spotify. Plusieurs salles en parallèle (pop, nostalgie, …), chacune branchée sur un compte Spotify séparé. Configuration des salles **à chaud depuis l'UI admin**, aucun redémarrage nécessaire.

## Stack

- Flask + Flask-SocketIO (temps réel)
- Spotipy (API Spotify + OAuth)
- HTML/CSS/JS vanilla (pas de framework front)
- État en mémoire + logs fichier (pas de DB)
- gunicorn + eventlet pour la prod
- Docker pour le déploiement (NAS, VPS)

## Setup minimal (local dev)

```bash
pip install -r requirements.txt

# .env minimal
cat > .env <<EOF
SPOTIFY_REDIRECT_URI=http://127.0.0.1:5001/callback
PORT=5001
ADMIN_PASSWORD=ton_mot_de_passe
EOF

python app.py
```

Puis ouvrir http://127.0.0.1:5001/admin/login et configurer les salles depuis l'UI.

## Configuration des salles (depuis l'UI admin)

1. Ouvrir `/admin/login`, entrer le mot de passe
2. Section **Salles & playlists** → **+ Ajouter une salle**
3. Remplir : nom, couleur, Client ID Spotify, Client Secret, Playlist ID
4. Sauvegarder → la salle est créée à chaud, sa thread démarre
5. Dans **Comptes Spotify**, cliquer sur la pastille de la salle → OAuth
6. Pour la 2e salle avec un autre compte : se déconnecter de spotify.com (ou onglet privé) avant de cliquer

Tokens persistés dans `caches/.cache-<salle>` → l'app se reconnecte seule au restart.

## Créer une app Spotify

Pour chaque salle, sur https://developer.spotify.com/dashboard :

- **Name** : libre
- **Redirect URI** : exactement la valeur de `SPOTIFY_REDIRECT_URI` dans `.env`
- **API** : Web API

Une seule app suffit si toutes les salles utilisent le même compte (mais elles jouent en séquence). Pour de vraies ambiances simultanées : **une app + un compte Premium par salle**.

## URLs

### Invités
- `/` — accueil (pseudo + choix salle)
- `/vote/<salle>` — voter
- `/display/<salle>` — écran à projeter
- `/stats` — classement (onglets : général + une par salle)

### Admin
- `/admin/login`
- `/admin` — config salles, comptes Spotify, logs, archivage

## Fonctionnement

### Cycle de vote

Pendant qu'une chanson joue, les invités votent parmi 3 candidates. 5 secondes avant la fin :

1. La salle clôture le vote
2. Les chansons avec ≥ 50 % des votes de la gagnante entrent dans la file d'attente
3. La première passe dans la queue Spotify
4. 3 nouvelles chansons sont tirées pour le tour suivant

Chaque salle est **indépendante** : son compte Spotify, sa queue, sa thread. Aucune coordination entre salles.

### Dedup des votes

Un vote par IP par tour. Derrière un proxy (Cloudflare, Caddy), l'IP est lue depuis les headers `CF-Connecting-IP` puis `X-Forwarded-For`, fallback sur `request.remote_addr` (voir `routes_public._ip_reelle()` et `sockets._ip_reelle()`).

### Pseudo + UUID

Pseudo saisi à l'accueil → UUID généré côté client (`localStorage`). Chaque vote porte pseudo + UUID. Les stats sont agrégées par UUID (le pseudo peut changer).

### Logs

| Fichier | Contenu |
| --- | --- |
| `logs/votes-YYYY-MM-DD.log` | Une ligne par vote individuel |
| `logs/tours-YYYY-MM-DD.log` | Résumé par tour (3 chansons, votants, gagnantes) |
| `logs/users.log` | Append-only : nouveaux users + changements de pseudo |
| `logs/user_stats.json` | État agrégé par UUID : pseudo, total, par salle |
| `logs/archive/<ts>_<type>/` | Archives via admin (jamais supprimé) |

## CLI

```bash
python app.py                 # normal
python app.py --clear         # efface user_stats.json + users.log
python app.py --seed          # ajoute ~50 users fake (test /stats)
python app.py --seed-clear    # fresh start + fakes
```

## Architecture

```
silent-disco/
├── app.py                    # Init Flask, manager, câblage, lancement
├── config_salles.py          # I/O config/salles.json (lock thread-safe)
├── salle_manager.py          # Cycle de vie des salles (add/modify/remove à chaud, cache cleanup)
├── salle.py                  # Classe Salle (pool, votes, auth Spotify)
├── spotify_sync.py           # Surveillance Spotify (une thread par salle, stop_flag)
├── routes_public.py          # /, /vote, /display, /stats, /login, /callback
├── routes_admin.py           # /admin/* (mot de passe) + CRUD salles + logs
├── sockets.py                # Handlers SocketIO (rejoindre_salle, voter)
├── logs_util.py              # logger_vote, logger_tour
├── admin.py                  # Listing / archivage des logs
├── stats.py                  # user_stats.json + classement
├── seed_fake_data.py         # Génération de données factices
├── gunicorn_conf.py          # Config gunicorn (prod)
├── Dockerfile                # Image Docker
├── docker-compose.yml        # Stack prod
├── config/
│   └── salles.json           # Config éditable via UI (gitignored)
├── static/                   # CSS + JS
├── templates/                # HTML (Jinja2)
├── logs/                     # Runtime (gitignored)
├── caches/                   # Tokens OAuth Spotify (gitignored)
├── .env                      # Secrets machine (gitignored)
└── .env.example              # Template
```

## Déploiement Docker (NAS / VPS / domaine)

### 1. Stack Docker

`Dockerfile` + `docker-compose.yml` fournis. Sur la machine cible :

```bash
git clone <repo> silent-disco
cd silent-disco
mkdir -p config logs caches

# .env minimal (les secrets viennent ici)
cat > .env <<EOF
ADMIN_PASSWORD=un_vrai_mot_de_passe
SECRET_KEY=$(openssl rand -hex 32)
EOF

docker compose up -d --build
```

L'app écoute sur `localhost:5001` (modifiable dans `docker-compose.yml`).

### 2. Reverse proxy + HTTPS

Spotify exige HTTPS pour les redirect URIs en production (sauf `127.0.0.1`).

#### Exemple Caddy

```caddy
silentdisco.mondomaine.com:8443 {
    reverse_proxy localhost:5001
    tls /etc/caddy/certs/mondomaine.com.crt /etc/caddy/certs/mondomaine.com.key
}
```

#### Exemple nginx + Let's Encrypt

```nginx
server {
    listen 443 ssl http2;
    server_name silentdisco.mondomaine.com;

    ssl_certificate /etc/letsencrypt/live/.../fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/.../privkey.pem;

    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Pour Socket.IO (websockets)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 3. DNS Cloudflare (si utilisé)

Si Cloudflare est devant ton serveur (proxied) :

| Type | Name | Content | Proxy |
|---|---|---|---|
| CNAME | `silentdisco` | `mondomaine.com` | Proxied |

Cloudflare envoie l'IP du visiteur dans le header `CF-Connecting-IP` — le code l'utilise déjà pour le dedup des votes.

### 4. Spotify dashboard

Pour chaque app Spotify utilisée, ajouter dans Settings → Redirect URIs :
```
https://silentdisco.mondomaine.com/callback
```

### 5. Mode développement Spotify

L'app est en "Development mode" par défaut → seuls les users whitelistés (max 25) peuvent s'auth. Pour silent disco c'est suffisant : tu whitelistes juste les 1-2 comptes qui jouent la musique. Pour plus, demander "Extended Quota Mode" sur le dashboard.

## Capacité & charge

L'archi tient sans souci une **soirée de 200-300 personnes** sur une instance modeste (NAS, mini-VPS).

**Pourquoi ça tient :**
- 1 worker gunicorn + **eventlet** (green threads) : facilement 500-1000 connexions WebSocket simultanées par worker
- `user_stats.json` protégé par `threading.Lock` + écriture atomique (`.tmp` + rename) — safe sous charge concurrente
- Logs append-only (`votes-*.log`, `tours-*.log`) — pas de contention
- État runtime des salles entièrement en mémoire — pas de DB qui pourrait être un point chaud

**Vrais goulots si la soirée explose :**

| Charge | Symptôme | Action |
| --- | --- | --- |
| ~300 personnes | Tout va bien, compteurs en temps réel | Rien |
| ~500+ personnes | Compteurs qui mettent ~1s à se mettre à jour (lock sur user_stats.json sous pression) | Passer le stockage en SQLite WAL ou supprimer les stats live |
| ~1000+ personnes | Saturation worker, latence WebSocket | Multi-worker + `message_queue=redis://...` dans Flask-SocketIO |
| Bande passante NAS | Pochettes Spotify (~50 Ko chacune) × N invités | Cache des images via Caddy / nginx |

**Recommandations pour le jour J (peu importe la taille) :**
- **Ne pas redémarrer** l'app pendant la soirée : l'état runtime (votes, file, tour) est en RAM
- Préparer la veille : créer les salles, faire les OAuth Spotify, tester avec quelques amis
- Whitelister les comptes Spotify dans le dashboard de chaque app (Settings → Users and Access) si l'app est en mode développement (max 25 users autorisés)
- Vérifier le Wi-Fi / data dispo pour les invités
- Garder un onglet `/admin` ouvert pour pouvoir archiver les logs ou ajuster une salle

## Limitations connues

- État en mémoire : un restart efface les votes en cours
- 1 vote par IP par tour. Derrière un NAT, plusieurs personnes peuvent partager une IP — limitation acceptable
- Pas de backup auto de `config/salles.json` — copier ailleurs avant gros changement
