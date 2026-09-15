# Dockerfile
FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Créer le répertoire de travail
WORKDIR /app

# Copier les requirements et installer les dépendances Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copier le code de l'application
COPY . .

# Créer les dossiers nécessaires
RUN mkdir -p logs staticfiles media

RUN chmod +x /app/entrypoint.sh /app/migrate.sh

# Utilisateur non-root pour l'exécution (l'installation des dépendances
# ci-dessus reste en root). Droits accordés uniquement sur les
# répertoires où l'application écrit réellement à l'exécution.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app/logs /app/staticfiles /app/media
USER appuser

# Exposer le port
EXPOSE 8000

# Commande par défaut (sera surchargée par docker-compose)
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "GestionRDV.wsgi:application", "--bind", "0.0.0.0:8000"]
