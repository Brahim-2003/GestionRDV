#!/bin/sh
set -e

: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"

echo "=> Waiting for postgres ${DB_HOST}:${DB_PORT}..."
# pg_isready vient du package postgresql-client (tu l'installes déjà dans Dockerfile)
until pg_isready -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1; do
  printf '.'
  sleep 1
done

echo
echo "=> Postgres is ready."

# Run Django management tasks
echo "=> Running migrations..."
python manage.py makemigrations --noinput || true
python manage.py migrate --noinput

echo "=> Collectstatic..."
python manage.py collectstatic --noinput

# Optionnel : créer un superuser non-interactif si variables définies
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  echo "=> Creating superuser (if not exists)..."
  python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); \
  User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists() or \
  User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME','$DJANGO_SUPERUSER_EMAIL','$DJANGO_SUPERUSER_PASSWORD')"
fi

# Execute passed command (gunicorn in docker-compose)
exec "$@"
