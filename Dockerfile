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

RUN chmod +x /app/entrypoint.sh

# Exposer le port
EXPOSE 8000

# Commande par défaut (sera surchargée par docker-compose)
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "GestionRDV.wsgi:application", "--bind", "0.0.0.0:8000"]
