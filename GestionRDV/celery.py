# GestionRDV/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GestionRDV.settings')

app = Celery('GestionRDV')

# Configuration depuis Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-découverte
app.autodiscover_tasks()