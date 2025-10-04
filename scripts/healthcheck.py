#!/usr/bin/env python3
"""
Script de healthcheck pour surveiller l'état des services Celery
Usage: python scripts/healthcheck.py
"""

import sys
import os
import django
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GestionRDV.settings')
django.setup()

from celery import Celery
from django.core.cache import cache
from django.db import connection
import redis


def check_database():
    """Vérifie la connexion à la base de données"""
    try:
        connection.ensure_connection()
        return True, "Base de données : OK"
    except Exception as e:
        return False, f"Base de données : ERREUR - {str(e)}"


def check_redis():
    """Vérifie la connexion à Redis"""
    try:
        cache.set('healthcheck', 'ok', 10)
        value = cache.get('healthcheck')
        if value == 'ok':
            return True, "Redis : OK"
        return False, "Redis : ERREUR - valeur incorrecte"
    except Exception as e:
        return False, f"Redis : ERREUR - {str(e)}"


def check_celery_worker():
    """Vérifie que le worker Celery répond"""
    try:
        from GestionRDV.celery import app
        inspect = app.control.inspect()
        active = inspect.active()
        
        if active is None:
            return False, "Celery Worker : ERREUR - Aucun worker actif"
        
        worker_count = len(active)
        return True, f"Celery Worker : OK ({worker_count} worker(s))"
    except Exception as e:
        return False, f"Celery Worker : ERREUR - {str(e)}"


def check_celery_beat():
    """Vérifie l'état de Celery Beat"""
    try:
        from django_celery_beat.models import PeriodicTask
        active_tasks = PeriodicTask.objects.filter(enabled=True).count()
        return True, f"Celery Beat : OK ({active_tasks} tâches actives)"
    except Exception as e:
        return False, f"Celery Beat : ERREUR - {str(e)}"


def check_pending_tasks():
    """Compte les tâches en attente"""
    try:
        from GestionRDV.celery import app
        inspect = app.control.inspect()
        
        reserved = inspect.reserved()
        if reserved:
            total = sum(len(tasks) for tasks in reserved.values())
            return True, f"Tâches en attente : {total}"
        return True, "Tâches en attente : 0"
    except Exception as e:
        return False, f"Tâches : ERREUR - {str(e)}"


def main():
    """Exécute tous les checks"""
    print("\n" + "="*50)
    print("  HEALTHCHECK - Système de Gestion RDV")
    print("="*50 + "\n")
    
    checks = [
        check_database,
        check_redis,
        check_celery_worker,
        check_celery_beat,
        check_pending_tasks,
    ]
    
    all_ok = True
    
    for check in checks:
        success, message = check()
        status = "✓" if success else "✗"
        color = "\033[92m" if success else "\033[91m"
        reset = "\033[0m"
        
        print(f"{color}{status}{reset} {message}")
        
        if not success:
            all_ok = False
    
    print("\n" + "="*50)
    
    if all_ok:
        print("\033[92m✓ Tous les services fonctionnent correctement\033[0m")
        print("="*50 + "\n")
        return 0
    else:
        print("\033[91m✗ Certains services ont des problèmes\033[0m")
        print("="*50 + "\n")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)