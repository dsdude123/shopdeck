#!/bin/bash
set -e

echo "Waiting for database..."
python << 'EOF'
import time, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shopdeck.settings')
for i in range(30):
    try:
        import django
        django.setup()
        from django.db import connection
        connection.ensure_connection()
        print("Database ready!")
        break
    except Exception as e:
        print(f"Database not ready ({e}), retrying in 2s...")
        time.sleep(2)
else:
    print("Could not connect to database after 60s")
    sys.exit(1)
EOF

if [ "${RUN_MIGRATIONS}" = "true" ]; then
    echo "Running migrations..."
    python manage.py migrate --noinput

    echo "Collecting static files..."
    python manage.py collectstatic --noinput

    if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
        echo "Creating superuser..."
        python manage.py createsuperuser --noinput 2>/dev/null || echo "Superuser already exists."
    fi
fi

exec "$@"
