@echo off
echo Waiting for PostgreSQL...
:wait_postgres
pg_isready -h db -U postgres >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_postgres
)
echo PostgreSQL is ready

echo Running migrations...
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo Creating superuser...
python manage.py createsuperuser --noinput 2>nul

echo Collecting static files...
python manage.py collectstatic --noinput --clear

echo Initializing periodic tasks...
python manage.py init_periodic_tasks

echo Setup complete!