"""
Gestionnaire du cycle de vie des salles :
- charge/recharge depuis config_salles.json
- démarre / arrête les threads de surveillance
- invalide les caches Spotify quand les credentials changent
- nettoie les caches orphelins quand une salle est supprimée
- expose une API simple : lister, récupérer, rebuild complet, modifier une salle
"""

import glob
import os
import threading
from threading import Thread

from config_salles import charger, sauvegarder
from salle import Salle
from spotify_sync import demarrer_surveillance_salle

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.environ.get('SPOTIFY_CACHE_DIR', BASE_DIR)


class SalleManager:
    def __init__(self, socketio):
        self.socketio = socketio
        self._salles = {}       # nom -> Salle
        self._threads = {}      # nom -> Thread
        self._lock = threading.Lock()

    # --- Lecture ---

    def liste(self):
        return list(self._salles.values())

    def get(self, nom):
        return self._salles.get(nom)

    def __contains__(self, nom):
        return nom in self._salles

    def noms(self):
        return list(self._salles.keys())

    # --- Cycle de vie ---

    def charger_depuis_config(self):
        """Charge toutes les salles depuis config/salles.json."""
        configs = charger()
        with self._lock:
            for cfg in configs:
                self._demarrer(cfg)
            self._nettoyer_caches_orphelins()

    def rebuild(self, nouvelles_configs):
        """
        Remplace la config complète : stoppe tout, sauvegarde, redémarre.
        Invalide les caches dont le client_id a changé.
        Nettoie les caches orphelins (salles qui n'existent plus).
        """
        sauvegarder(nouvelles_configs)  # valide + écrit
        with self._lock:
            anciens_clients = {
                s.nom: s.auth_manager.client_id
                for s in self._salles.values()
            }
            for nom in list(self._salles.keys()):
                self._arreter(nom)
            for cfg in nouvelles_configs:
                nom = cfg['nom']
                self._demarrer(cfg)
                nouvelle = self._salles[nom]
                ancien_client = anciens_clients.get(nom)
                if ancien_client and ancien_client != cfg['client_id']:
                    print(f"[{nom}] client_id changé -> invalidation du cache")
                    nouvelle.invalider_cache()
            self._nettoyer_caches_orphelins()

    def _nettoyer_caches_orphelins(self):
        """Supprime les fichiers .cache-<nom> dont la salle n'existe plus."""
        noms_actifs = set(self._salles.keys())
        for chemin in glob.glob(os.path.join(CACHE_DIR, '.cache-*')):
            nom_cache = os.path.basename(chemin)[len('.cache-'):]
            if nom_cache and nom_cache not in noms_actifs:
                try:
                    os.remove(chemin)
                    print(f"[manager] cache orphelin supprimé : {os.path.basename(chemin)}")
                except OSError as e:
                    print(f"[manager] impossible de supprimer {chemin} : {e}")

    # --- Internes (appelés avec le lock déjà pris) ---

    def _demarrer(self, cfg):
        nom = cfg['nom']
        salle = Salle(cfg)
        if salle.est_authentifie():
            try:
                salle.initialiser_pool()
                salle.nouveau_tirage()
            except Exception as e:
                print(f"[{nom}] init pool impossible : {e}")
        thread = Thread(
            target=demarrer_surveillance_salle,
            args=(salle, self.socketio),
            daemon=True,
        )
        thread.start()
        self._salles[nom] = salle
        self._threads[nom] = thread
        print(f"[manager] salle '{nom}' démarrée")

    def _arreter(self, nom):
        salle = self._salles.pop(nom, None)
        thread = self._threads.pop(nom, None)
        if salle:
            salle.demander_arret()
        # On n'attend pas la thread (daemon, timeout 2s max)
        print(f"[manager] salle '{nom}' arrêtée")
