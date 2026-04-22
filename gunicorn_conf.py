"""
Config gunicorn pour déploiement en prod (NAS, VPS, etc).

Lancement :
    gunicorn -c gunicorn_conf.py app:app

Flask-SocketIO nécessite un worker async (eventlet ici).
Un seul worker — SocketIO avec plusieurs workers demanderait un message queue
(Redis/RabbitMQ) entre workers, overkill pour une app de soirée.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5001')}"
workers = 1
worker_class = 'eventlet'
worker_connections = 1000
timeout = 60
accesslog = '-'
errorlog = '-'
loglevel = 'info'
