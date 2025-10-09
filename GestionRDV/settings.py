"""
Django settings for GestionRDV project.

Adaptation : lecture de variables d'environnement (.env), gestion safe de DEBUG,
contrôle de CELERY_TASK_ALWAYS_EAGER via variable d'environnement, et support
optionnel de django-celery-results via variable d'environnement.
"""

from pathlib import Path
import os
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------
# Sécurité / Configuration via .env
# ---------------------------------------------------------------------
# Lire la SECRET_KEY depuis l'environnement, sinon utiliser une valeur de dev
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-!7x30&4+0#i!tm@t%vl7f1k(vssc43+f2p7f0x!fuh0n!4&=m4"
)

# DEBUG (True si la variable d'environnement vaut "true", "1" ou "yes")
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

# ALLOWED_HOSTS depuis .env (virgule-separated)
_allowed = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()]

# ---------------------------------------------------------------------
# Applications / Middleware
# ---------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "users.apps.UsersConfig",
    "rdv",
    "django_celery_beat",  # présent dans ton projet
]

# Optionnel : activer django-celery-results si demandé via env
if os.getenv("ENABLE_DJANGO_CELERY_RESULTS", "False").lower() in ("true", "1", "yes"):
    INSTALLED_APPS.append("django_celery_results")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "users.middleware.SecurityMiddleware",
]

ROOT_URLCONF = "GestionRDV.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "GestionRDV.wsgi.application"

# ---------------------------------------------------------------------
# Base de données (DATABASE_URL ou fallback sqlite)
# ---------------------------------------------------------------------
database_url = os.environ.get("DATABASE_URL")
if database_url:
    url = urlparse(database_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": url.path[1:],  # retire le slash initial
            "USER": url.username,
            "PASSWORD": url.password,
            "HOST": url.hostname,
            "PORT": url.port or "5432",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------
# Auth / Password validators
# ---------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------
# Internationalisation / Timezone
# ---------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Ndjamena"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------
# Static / Media
# ---------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.Utilisateur"

LOGIN_URL = "/users/login"
LOGIN_REDIRECT_URL = "/users/dashboard/"
LOGOUT_REDIRECT_URL = "/users/connexion/"

# ---------------------------------------------------------------------
# Email / Notifications
# ---------------------------------------------------------------------
NOTIFY_SEND_EMAIL = os.getenv("NOTIFY_SEND_EMAIL", "False").lower() in ("true", "1", "yes")
if NOTIFY_SEND_EMAIL:
    # production-like : configure un vrai backend via env (ex: SMTP)
    EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@example.com")
else:
    # par défaut en dev : console backend
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@localhost")

# ---------------------------------------------------------------------
# Celery (broker / backend / options)
# ---------------------------------------------------------------------
# On lit les variables fournies dans .env (tu as CELERY_BROKER_URL & CELERY_RESULT_BACKEND)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://redis:6379/0"))
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://redis:6379/1"))

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Ndjamena"
CELERY_ENABLE_UTC = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Controler le mode eager via .env (utile pour tests locaux)
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "False").lower() in ("true", "1", "yes")
CELERY_TASK_EAGER_PROPAGATES_EXCEPTIONS = CELERY_TASK_ALWAYS_EAGER

# ---------------------------------------------------------------------
# Logging minimal
# ---------------------------------------------------------------------
LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {"level": LOG_LEVEL, "handlers": ["console"]},
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "formatters": {
        "simple": {"format": "%(levelname)s %(asctime)s %(name)s %(message)s"},
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# ---------------------------------------------------------------------
# Fin
# ---------------------------------------------------------------------
