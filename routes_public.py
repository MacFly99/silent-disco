"""Routes accessibles sans authentification : vote, display, stats, OAuth Spotify."""

import traceback

from flask import abort, redirect, render_template, request, url_for

from stats import obtenir_classement


def register_public_routes(app, socketio, salles):

    @app.route('/')
    def index():
        return render_template('index.html', salles=list(salles.values()))

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

    @app.route('/stats')
    def stats_page():
        classements = {
            'general': obtenir_classement(),
            'pop': obtenir_classement('pop'),
            'nostalgie': obtenir_classement('nostalgie'),
        }
        return render_template('stats.html', classements=classements)

    # --- OAuth Spotify : à faire UNE FOIS par salle. Ensuite le cache persiste. ---

    @app.route('/login/<salle_nom>')
    def login(salle_nom):
        salle = salles.get(salle_nom)
        if salle is None:
            abort(404)
        return redirect(salle.authorize_url())

    @app.route('/callback')
    def callback():
        salle_nom = request.args.get('state')
        code = request.args.get('code')
        salle = salles.get(salle_nom)
        if salle is None or not code:
            abort(400)
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
            return f"<p>Erreur : {e}</p>"
        return f"<p>Salle <b>{salle_nom}</b> connectée. Tu peux fermer cet onglet.</p>"
