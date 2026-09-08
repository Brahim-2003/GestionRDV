"""Configuration Celery pour le projet GestionRDV.

Ce module doit être importé au démarrage de chaque processus (web, worker,
beat) — voir GestionRDV/__init__.py — pour que les tâches déclarées avec
@shared_task se lient à cette instance plutôt qu'à une app Celery par
défaut non configurée.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GestionRDV.settings")

app = Celery("GestionRDV")

# Charge la config Celery depuis settings.py (toutes les clés CELERY_*).
app.config_from_object("django.conf:settings", namespace="CELERY")

# Découvre automatiquement rdv/tasks.py et users/tasks.py.
app.autodiscover_tasks()
