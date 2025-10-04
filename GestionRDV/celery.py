# GestionRDV/celery.py

import os
from celery import Celery

# Définir le module de settings Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GestionRDV.settings')

app = Celery('GestionRDV')

# Configuration depuis Django settings avec le namespace 'CELERY'
app.config_from_object('django.conf:settings', namespace='CELERY')

# Découverte automatique des tâches dans tous les fichiers tasks.py
app.autodiscover_tasks()

# Configuration avancée mais PAS de beat_schedule ici !
app.conf.update(
    # Configuration des workers
    worker_max_tasks_per_child=100,  # Redémarre le worker après 100 tâches pour éviter les fuites mémoire
    task_acks_late=True,  # Acknowledge la tâche après son exécution (plus sûr)
    task_reject_on_worker_lost=True,  # Rejette les tâches si le worker crash
    task_time_limit=300,  # 5 minutes max par tâche
    task_soft_time_limit=240,  # Warning à 4 minutes
    worker_prefetch_multiplier=1,  # Nombre de tâches à précharger
    worker_disable_rate_limits=False,
    
    # Configuration timezone
    timezone='Africa/Ndjamena',
    enable_utc=False,
)

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Tâche de débogage pour tester Celery"""
    print(f'Request: {self.request!r}')
    return f'Debug task executed on worker: {self.request.hostname}'