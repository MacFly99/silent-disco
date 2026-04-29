"""Mode fake : crée des salles bidons en RAM avec une simulation Spotify locale.

Lancé via `python app.py --fake`. Permet de visualiser /displays, /vote, /index
sans avoir à configurer de vrai compte Spotify.

Chaque salle simulée a son thread qui :
- fait progresser une "chanson en cours" toutes les 0.5s (émet chanson_en_cours)
- ajoute aléatoirement des votes aux 3 chansons proposées (émet mise_a_jour_votes)
- au bout de la durée de la chanson, fait un nouveau tirage et change de chanson
"""

import random
import threading

from salle import Salle


# 4 salles avec un thème, une couleur, et un pool de chansons (titre, artiste, seed pochette)
FAKE_SALLES = [
    {
        'nom': 'pop',
        'couleur': '#ec4899',
        'chansons': [
            ('Levitating', 'Dua Lipa'),
            ('Blinding Lights', 'The Weeknd'),
            ('As It Was', 'Harry Styles'),
            ('Anti-Hero', 'Taylor Swift'),
            ('Watermelon Sugar', 'Harry Styles'),
            ('Save Your Tears', 'The Weeknd'),
            ('Stay', 'The Kid LAROI'),
            ('Flowers', 'Miley Cyrus'),
        ],
    },
    {
        'nom': 'nostalgie',
        'couleur': '#f59e0b',
        'chansons': [
            ('Wonderwall', 'Oasis'),
            ('Smells Like Teen Spirit', 'Nirvana'),
            ('Sweet Child O Mine', "Guns N' Roses"),
            ('Take On Me', 'a-ha'),
            ('Africa', 'Toto'),
            ('Livin On A Prayer', 'Bon Jovi'),
            ('Bohemian Rhapsody', 'Queen'),
            ('Dont Stop Believin', 'Journey'),
        ],
    },
    {
        'nom': 'electro',
        'couleur': '#06b6d4',
        'chansons': [
            ('One More Time', 'Daft Punk'),
            ('Strobe', 'deadmau5'),
            ('Titanium', 'David Guetta'),
            ('Animals', 'Martin Garrix'),
            ('Levels', 'Avicii'),
            ('Clarity', 'Zedd'),
            ('Around The World', 'Daft Punk'),
            ('Wake Me Up', 'Avicii'),
        ],
    },
    {
        'nom': 'rock',
        'couleur': '#ef4444',
        'chansons': [
            ('Highway to Hell', 'AC/DC'),
            ('Enter Sandman', 'Metallica'),
            ('Seven Nation Army', 'The White Stripes'),
            ('Killing in the Name', 'Rage Against The Machine'),
            ('Smoke on the Water', 'Deep Purple'),
            ('Master of Puppets', 'Metallica'),
            ('Whole Lotta Love', 'Led Zeppelin'),
            ('Black Dog', 'Led Zeppelin'),
        ],
    },
]


def _pochette(seed):
    """Image placeholder déterministe (300x300)."""
    return f'https://picsum.photos/seed/{seed}/300'


def _piste(titre, artiste):
    seed = (titre + artiste).replace(' ', '').lower()[:32]
    return {
        'titre': titre,
        'artiste': artiste,
        'pochette': _pochette(seed),
        'uri': f'fake:track:{seed}',
    }


def _construire_salle_fake(spec):
    """Construit une Salle avec creds bidons. SpotifyOAuth ne fait pas de réseau à l'init."""
    config = {
        'nom': spec['nom'],
        'couleur': spec['couleur'],
        'client_id': 'fake_client_id',
        'client_secret': 'fake_client_secret',
        'playlist_id': 'fake_playlist',
    }
    salle = Salle(config)

    # Pool : toutes les chansons du thème
    salle.pool_playlist = [_piste(t, a) for (t, a) in spec['chansons']]
    random.shuffle(salle.pool_playlist)

    # Premier tirage : 3 chansons à voter
    pioche = salle.pool_playlist[:3]
    salle.pool_playlist = salle.pool_playlist[3:]
    salle.chansons = [{'id': i + 1, 'votes': 0, **p} for i, p in enumerate(pioche)]
    salle.tour = 1

    # Chanson en cours : on prend une autre du pool
    en_cours = salle.pool_playlist.pop()
    salle.chanson_en_cours = {
        'titre': en_cours['titre'],
        'artiste': en_cours['artiste'],
        'pochette': en_cours['pochette'],
        'progression_ms': 0,
        'duree_ms': random.randint(150_000, 240_000),
        'en_lecture': True,
    }
    return salle


def _boucle_simulation(salle, socketio):
    """Simule la lecture d'une chanson + des votes aléatoires."""
    # Émission initiale
    socketio.emit(
        'chanson_en_cours',
        {**salle.chanson_en_cours, 'salle': salle.nom},
        room=salle.nom,
    )
    socketio.emit(
        'mise_a_jour_votes',
        {'chansons': salle.chansons, 'tour': salle.tour, 'salle': salle.nom},
        room=salle.nom,
    )

    tick_ms = 1000
    derniere_emission_progression = 0
    derniere_emission_votes = 0

    while not salle.stop_flag.is_set():
        if salle.stop_flag.wait(tick_ms / 1000):
            return

        # Avance la chanson
        salle.chanson_en_cours['progression_ms'] += tick_ms

        # Émet la progression toutes les 2s pour économiser les events
        derniere_emission_progression += tick_ms
        if derniere_emission_progression >= 2000:
            derniere_emission_progression = 0
            socketio.emit(
                'chanson_en_cours',
                {**salle.chanson_en_cours, 'salle': salle.nom},
                room=salle.nom,
            )

        # Génère des votes aléatoires (~1 vote toutes les 3s en moyenne)
        if random.random() < 0.33:
            chanson = random.choice(salle.chansons)
            chanson['votes'] += 1
            derniere_emission_votes += tick_ms
            if derniere_emission_votes >= 1000:
                derniere_emission_votes = 0
                socketio.emit(
                    'mise_a_jour_votes',
                    {'chansons': salle.chansons, 'tour': salle.tour, 'salle': salle.nom},
                    room=salle.nom,
                )

        # Fin de chanson : nouveau tirage + nouvelle chanson en cours
        if salle.chanson_en_cours['progression_ms'] >= salle.chanson_en_cours['duree_ms']:
            _nouvelle_chanson(salle)
            socketio.emit(
                'chanson_en_cours',
                {**salle.chanson_en_cours, 'salle': salle.nom},
                room=salle.nom,
            )
            socketio.emit(
                'mise_a_jour_votes',
                {'chansons': salle.chansons, 'tour': salle.tour, 'salle': salle.nom},
                room=salle.nom,
            )


def _nouvelle_chanson(salle):
    """Recharge le pool si vide, pioche une chanson à jouer + 3 nouvelles à voter."""
    if len(salle.pool_playlist) < 4:
        # Recharge en clonant les chansons existantes (boucle infinie pour la démo)
        toutes = [
            {'titre': c['titre'], 'artiste': c['artiste'],
             'pochette': c['pochette'], 'uri': c.get('uri', '')}
            for c in salle.chansons
        ] + salle.pool_playlist
        random.shuffle(toutes)
        salle.pool_playlist = toutes

    # Nouvelle chanson en cours
    en_cours = salle.pool_playlist.pop()
    salle.chanson_en_cours = {
        'titre': en_cours['titre'],
        'artiste': en_cours['artiste'],
        'pochette': en_cours['pochette'],
        'progression_ms': 0,
        'duree_ms': random.randint(150_000, 240_000),
        'en_lecture': True,
    }

    # Nouveau tirage de 3 chansons
    pioche = salle.pool_playlist[:3]
    salle.pool_playlist = salle.pool_playlist[3:]
    salle.chansons = [{'id': i + 1, 'votes': 0, **p} for i, p in enumerate(pioche)]
    salle.tour += 1
    print(f"[fake/{salle.nom}] tour {salle.tour} — joue : {salle.chanson_en_cours['titre']}")


def lancer_fake(manager, socketio, nb_salles=None):
    """Injecte N salles fake dans le manager et démarre les threads de simulation.

    nb_salles : nombre de salles à créer (cappé au nombre dispo). None = toutes.
    """
    specs = FAKE_SALLES if nb_salles is None else FAKE_SALLES[:max(1, nb_salles)]
    print(f"[fake] démarrage de {len(specs)} salle(s) simulée(s)")
    for spec in specs:
        salle = _construire_salle_fake(spec)
        thread = threading.Thread(
            target=_boucle_simulation,
            args=(salle, socketio),
            daemon=True,
        )
        manager._salles[salle.nom] = salle
        manager._threads[salle.nom] = thread
        thread.start()
        print(f"[fake] salle '{salle.nom}' lancée — {len(spec['chansons'])} chansons, "
              f"joue : {salle.chanson_en_cours['titre']}")
