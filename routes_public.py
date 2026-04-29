"""Routes accessibles sans authentification : vote, display, stats, OAuth Spotify."""

import traceback

from flask import abort, redirect, render_template, request, url_for

from stats import obtenir_classement


def _ip_reelle():
    """IP du client réel derrière Cloudflare / Caddy."""
    cf = request.headers.get('CF-Connecting-IP')
    if cf:
        return cf.strip()
    xff = request.headers.get('X-Forwarded-For')
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr


def register_public_routes(app, socketio, manager):

    @app.route('/')
    def index():
        return render_template('index.html', salles=manager.liste())

    @app.route('/vote/<salle_nom>')
    def vote(salle_nom):
        salle = manager.get(salle_nom)
        if salle is None:
            abort(404)
        deja_vote = salle.a_vote(_ip_reelle())
        return render_template('vote.html', salle=salle, deja_vote=deja_vote)

    @app.route('/display/<salle_nom>')
    def display(salle_nom):
        salle = manager.get(salle_nom)
        if salle is None:
            abort(404)
        return render_template('display.html', salle=salle)

    @app.route('/displays')
    def displays():
        salles_data = [{
            'nom': s.nom,
            'couleur': s.couleur,
            'couleur_rgb': s.couleur_rgb,
            'chansons': s.chansons,
            'tour': s.tour,
            'chanson_en_cours': s.chanson_en_cours,
            'vote_url': url_for('vote', salle_nom=s.nom, _external=True),
        } for s in manager.liste()]
        return render_template('displays.html', salles=salles_data)

    def _build_classements():
        salles = manager.liste()
        out = [
            {'key': 'general', 'label': 'Général', 'couleur': None, 'users': obtenir_classement()}
        ]
        for s in salles:
            out.append({
                'key': s.nom,
                'label': s.nom,
                'couleur': s.couleur,
                'couleur_rgb': s.couleur_rgb,
                'users': obtenir_classement(s.nom),
            })
        return out

    @app.route('/stats')
    def stats_page():
        return render_template('stats.html', classements=_build_classements())

    @app.route('/stats.json')
    def stats_json():
        from flask import jsonify
        return jsonify(_build_classements())

    # --- OAuth Spotify : à faire UNE FOIS par salle. Le cache persiste. ---

    @app.route('/login/<salle_nom>')
    def login(salle_nom):
        salle = manager.get(salle_nom)
        if salle is None:
            abort(404)
        return redirect(salle.authorize_url())

    @app.route('/callback')
    def callback():
        salle_nom = request.args.get('state')
        code = request.args.get('code')
        erreur_spotify = request.args.get('error')

        print(f"[callback] state={salle_nom!r} code={'present' if code else 'absent'} "
              f"error={erreur_spotify!r}")

        if erreur_spotify:
            return f"<p>Spotify a refusé l'autorisation : <b>{erreur_spotify}</b></p>", 400
        if not salle_nom:
            return "<p>Paramètre <code>state</code> manquant.</p>", 400
        if not code:
            return "<p>Paramètre <code>code</code> manquant.</p>", 400

        salle = manager.get(salle_nom)
        if salle is None:
            return (f"<p>Salle <b>{salle_nom}</b> inconnue. Salles actives : "
                    f"{', '.join(manager.noms()) or '(aucune)'}.</p>"), 400

        try:
            salle.finaliser_auth(code)
            salle.initialiser_pool()
            salle.nouveau_tirage()
            socketio.emit(
                'mise_a_jour_votes',
                {'chansons': salle.chansons, 'tour': salle.tour, 'salle': salle.nom},
                room=salle.nom,
            )
        except Exception as e:
            traceback.print_exc()
            return f"<p>Erreur d'auth ou de chargement : {e}</p>", 500
        return f"<p>Salle <b>{salle_nom}</b> connectée. Tu peux fermer cet onglet.</p>"
