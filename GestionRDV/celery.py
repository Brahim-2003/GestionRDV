# GestionRDV/celery.py

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GestionRDV.settings')

app = Celery('GestionRDV')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
