"""Routes admin : login par mot de passe + visualisation/archivage des logs."""

import os
from functools import wraps

from flask import (abort, jsonify, redirect, render_template, request,
                   send_file, session, url_for)

import admin


def admin_requis(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return view(*args, **kwargs)
    return wrapped


def register_admin_routes(app, salles):

    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        erreur = None
        if request.method == 'POST':
            pwd = request.form.get('password', '')
            attendu = os.environ.get('ADMIN_PASSWORD', '')
            if attendu and pwd == attendu:
                session['admin'] = True
                return redirect(url_for('admin_page'))
            erreur = 'Mot de passe incorrect'
        return render_template('admin_login.html', erreur=erreur)

    @app.route('/admin/logout')
    def admin_logout():
        session.pop('admin', None)
        return redirect(url_for('admin_login'))

    @app.route('/admin')
    @admin_requis
    def admin_page():
        fichiers = admin.lister_fichiers_logs()
        tails = {f['nom']: admin.lire_tail(f['nom'], n=30) for f in fichiers}
        auth_statuses = [
            {'nom': s.nom, 'couleur': s.couleur, 'authentifie': s.est_authentifie()}
            for s in salles.values()
        ]
        return render_template(
            'admin.html',
            fichiers=fichiers,
            tails=tails,
            types=list(admin.TYPES.keys()),
            auth_statuses=auth_statuses,
        )

    @app.route('/admin/archiver/<log_type>', methods=['POST'])
    @admin_requis
    def admin_archiver(log_type):
        return jsonify({'archived': admin.archiver_type(log_type)})

    @app.route('/admin/download/<path:nom_fichier>')
    @admin_requis
    def admin_download(nom_fichier):
        chemin = admin.chemin_fichier_log(nom_fichier)
        if chemin is None:
            abort(404)
        return send_file(chemin, as_attachment=True)
