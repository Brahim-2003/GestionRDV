from .celery import app as celery_app

__all__ = ['celery_app',]
# Cela garantira que l'application est toujours importée lorsque
# Django démarre afin que shared_task utilise cette application.