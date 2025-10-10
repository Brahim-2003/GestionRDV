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
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] || [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  echo "=> Creating superuser (if not exists) with dynamic USERNAME_FIELD (via manage.py shell)..."
  python manage.py shell -c "
from django.contrib.auth import get_user_model
import os, sys
User = get_user_model()
username_field = getattr(User, 'USERNAME_FIELD', 'username')
email = os.getenv('DJANGO_SUPERUSER_EMAIL', '')
username = os.getenv('DJANGO_SUPERUSER_USERNAME', '')
password = os.getenv('DJANGO_SUPERUSER_PASSWORD', '')

# build lookup key/value
if username_field == 'email':
    lookup = {'email': email}
else:
    lookup = {username_field: username}

# ensure env present
if not lookup.get(list(lookup.keys())[0]):
    print('Superuser env variables not set (missing username/email). Skipping creation.')
    sys.exit(0)

# create if not exists
if not User.objects.filter(**lookup).exists():
    create_kwargs = {}
    if username_field == 'email':
        create_kwargs['email'] = lookup['email']
    else:
        create_kwargs[username_field] = lookup[username_field]
        if email:
            create_kwargs['email'] = email
    try:
        User.objects.create_superuser(**create_kwargs, password=password)
        print('Superuser created.')
    except TypeError:
        # fallback: try positional args
        try:
            if username_field == 'email':
                User.objects.create_superuser(lookup['email'], password)
            else:
                User.objects.create_superuser(lookup[username_field], email, password)
            print('Superuser created (fallback).')
        except Exception as e:
            print('Failed to create superuser (fallback):', e)
else:
    print('Superuser already exists.')
"
fi


# Execute passed command (gunicorn in docker-compose)
exec "$@"
