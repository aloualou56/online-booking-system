#!/bin/bash

# Deployment script for Contabo VPS server
# Path: /var/www/Project_online

set -e

PROJECT_DIR="/var/www/Project_online"

echo "Starting deployment..."

cd "$PROJECT_DIR"

# Activate virtual environment
source "$PROJECT_DIR/.venv/bin/activate"
echo "Virtual environment activated."

# Pull latest changes from git
git fetch origin main
git checkout origin/main -- .
git restore --staged deploy.sh deploy_server.sh 2>/dev/null || true
git restore deploy.sh deploy_server.sh 2>/dev/null || true

# Remove stale untracked migration artifacts that can break Django graph loading.
rm -f businesses/migrations/0007_business_deletion_request.py
find businesses/migrations -name "*.pyc" -delete
echo "Latest code pulled from git."

# Install/update dependencies
pip install -r requirements.txt --quiet
echo "Python dependencies installed."

# Re-align the django_migrations primary key sequence before applying migrations.
# This fixes PostgreSQL duplicate-key errors when the sequence is behind existing rows.
python manage.py shell <<'PY'
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute(
        "SELECT setval("
        "pg_get_serial_sequence('django_migrations', 'id'), "
        "COALESCE((SELECT MAX(id) FROM django_migrations), 1), "
        "EXISTS(SELECT 1 FROM django_migrations)"
        ")"
    )
PY
echo "django_migrations sequence realigned."

# Run database migrations
python manage.py migrate
echo "Database migrations applied."

# Collect static files
python manage.py collectstatic --noinput
echo "Static files collected."

# Reload gunicorn (graceful restart)
GUNICORN_PID=$(pgrep -f "gunicorn.*erantevou" | head -1)
if [ -n "$GUNICORN_PID" ]; then
    kill -HUP "$GUNICORN_PID"
    echo "Gunicorn reloaded (PID: $GUNICORN_PID)."
else
    echo "Warning: Gunicorn process not found. Manual restart may be required."
fi

echo "Deployment finished successfully."
