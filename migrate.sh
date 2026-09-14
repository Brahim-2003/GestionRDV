#!/bin/bash
set -e

echo "🔎 Checking for unmigrated model changes..."
if ! python manage.py makemigrations --check --dry-run; then
  echo "❌ Des modifications de modèles sans migration correspondante ont été détectées." >&2
  echo "   Générez la migration en local avec 'python manage.py makemigrations' et committez-la dans le repo." >&2
  exit 1
fi

echo "📦 Running database migrations..."
python manage.py migrate --noinput

echo "👤 Creating superuser if needed..."
python manage.py createsuperuser --noinput 2>/dev/null || echo "ℹ️  Superuser already exists or skipped"

echo "📊 Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "🎯 Initializing periodic tasks..."
python manage.py init_periodic_tasks || echo "⚠️  Periodic tasks initialization failed or already done"

echo "✨ Migrate/init service complete."
