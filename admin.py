import glob
import os
from datetime import datetime

LOGS_DIR = os.path.join(os.path.dirname(__file__), 'logs')
ARCHIVE_DIR = os.path.join(LOGS_DIR, 'archive')
os.makedirs(ARCHIVE_DIR, exist_ok=True)


TYPES = {
    'votes':  ['votes-*.log'],
    'tours':  ['tours-*.log'],
    'users':  ['users.log', 'user_stats.json'],
}


def _fichiers_pour_type(log_type):
    """Retourne la liste absolue des fichiers correspondant à un type (hors archives)."""
    patterns = TYPES.get(log_type, [])
    fichiers = []
    for pat in patterns:
        fichiers.extend(
            f for f in glob.glob(os.path.join(LOGS_DIR, pat))
            if os.path.isfile(f)
        )
    return sorted(fichiers)


def lister_fichiers_logs():
    """Retourne la liste des fichiers de logs courants (hors archive) avec leur métadonnées."""
    resultats = []
    for log_type, patterns in TYPES.items():
        fichiers = _fichiers_pour_type(log_type)
        for f in fichiers:
            taille = os.path.getsize(f)
            lignes = _compter_lignes(f)
            resultats.append({
                'type': log_type,
                'nom': os.path.basename(f),
                'taille': taille,
                'lignes': lignes,
            })
    return resultats


def _compter_lignes(chemin):
    try:
        with open(chemin, 'r', encoding='utf-8', errors='replace') as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def archiver_type(log_type):
    """Déplace tous les fichiers d'un type dans logs/archive/<timestamp>/. Retourne la liste déplacée."""
    if log_type not in TYPES:
        return []
    fichiers = _fichiers_pour_type(log_type)
    if not fichiers:
        return []
    stamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
    dest_dir = os.path.join(ARCHIVE_DIR, f'{stamp}_{log_type}')
    os.makedirs(dest_dir, exist_ok=True)
    deplaces = []
    for chemin in fichiers:
        dest = os.path.join(dest_dir, os.path.basename(chemin))
        os.rename(chemin, dest)
        deplaces.append(os.path.basename(chemin))
    return deplaces


def lire_tail(nom_fichier, n=50):
    """Lit les N dernières lignes d'un fichier de log (pour affichage dans admin)."""
    chemin = os.path.join(LOGS_DIR, nom_fichier)
    if not os.path.isfile(chemin):
        return []
    try:
        with open(chemin, 'r', encoding='utf-8', errors='replace') as f:
            lignes = f.readlines()
        return lignes[-n:]
    except OSError:
        return []


def chemin_fichier_log(nom_fichier):
    """Retourne le chemin absolu d'un fichier de log (pour download), ou None s'il n'existe pas."""
    chemin = os.path.join(LOGS_DIR, nom_fichier)
    # Sécurité : empêcher les path traversal
    if not os.path.abspath(chemin).startswith(os.path.abspath(LOGS_DIR)):
        return None
    if not os.path.isfile(chemin):
        return None
    return chemin
