#!/bin/bash
set -e

echo "==> Installing dependencies..."
pip install -r requirements.txt

echo "==> Collecting static files..."
python manage.py collectstatic --no-input

echo "==> Running migrations..."
python manage.py migrate --no-input

echo "==> Setting up groups and users..."
python manage.py setup_groups
python manage.py create_test_users

echo "==> Build complete!"
