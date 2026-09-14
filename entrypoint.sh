#!/bin/bash
set -e

echo "🔄 Waiting for PostgreSQL..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "db" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q' 2>/dev/null; do
  echo "⏳ PostgreSQL is unavailable - sleeping"
  sleep 1
done
echo "✅ PostgreSQL is up and running"

echo "🔄 Waiting for Redis..."
until python -c "import redis; r = redis.Redis(host='redis', port=6379, db=0); r.ping()" 2>/dev/null; do
  echo "⏳ Redis is unavailable - sleeping"
  sleep 1
done
echo "✅ Redis is up and running"

exec "$@"

