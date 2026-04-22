"""Routes admin : login par mot de passe, logs, config des salles."""

import os
from functools import wraps

from flask import (abort, jsonify, redirect, render_template, request,
                   send_file, session, url_for)

import admin
from config_salles import charger as charger_config


def admin_requis(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return view(*args, **kwargs)
    return wrapped


def register_admin_routes(app, manager):

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
            for s in manager.liste()
        ]
        return render_template(
            'admin.html',
            fichiers=fichiers,
            tails=tails,
            types=list(admin.TYPES.keys()),
            auth_statuses=auth_statuses,
            salles_config=_config_pour_ui(),
        )

    @app.route('/admin/salles', methods=['GET'])
    @admin_requis
    def admin_salles_get():
        return jsonify(_config_pour_ui())

    @app.route('/admin/salles', methods=['POST'])
    @admin_requis
    def admin_salles_post():
        """
        Remplace la config complète. Pour préserver les secrets quand l'admin
        ne les retape pas, on merge chaque salle avec l'existant si client_secret
        est vide dans le payload.
        """
        payload = request.get_json(silent=True) or []
        if not isinstance(payload, list):
            return jsonify({'error': "Le body doit être une liste de salles"}), 400

        existantes = {s['nom']: s for s in charger_config()}
        nouvelles = []
        for s in payload:
            nom = (s.get('nom') or '').strip().lower()
            if not nom:
                return jsonify({'error': "Une salle sans nom"}), 400
            ancien = existantes.get(nom, {})
            # Si client_secret vide dans le payload, on garde l'ancien
            client_secret = (s.get('client_secret') or '').strip() or ancien.get('client_secret', '')
            entry = {
                'nom': nom,
                'couleur': (s.get('couleur') or ancien.get('couleur') or '#1DB954').strip(),
                'client_id': (s.get('client_id') or '').strip(),
                'client_secret': client_secret,
                'playlist_id': (s.get('playlist_id') or '').strip(),
            }
            for champ in ('client_id', 'client_secret', 'playlist_id'):
                if not entry[champ]:
                    return jsonify({'error': f"Champ '{champ}' manquant pour la salle '{nom}'"}), 400
            nouvelles.append(entry)

        try:
            manager.rebuild(nouvelles)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        return jsonify({'ok': True, 'salles': _config_pour_ui()})

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


def _config_pour_ui():
    """Charge la config et masque les secrets (les 4 derniers chars visibles uniquement)."""
    salles = []
    for s in charger_config():
        secret = s.get('client_secret', '')
        salles.append({
            'nom': s['nom'],
            'couleur': s.get('couleur', '#1DB954'),
            'client_id': s.get('client_id', ''),
            'client_secret_masque': _masquer(secret),
            'playlist_id': s.get('playlist_id', ''),
        })
    return salles


def _masquer(secret):
    if not secret:
        return ''
    if len(secret) <= 4:
        return '•' * len(secret)
    return '•' * (len(secret) - 4) + secret[-4:]
