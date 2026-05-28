#!/usr/bin/env bash
# build.sh — run by Render during deploy
set -o errexit

echo "==> Installing Python dependencies..."
pip install -r requirements.txt
# On Render/PostgreSQL we need psycopg2-binary
pip install psycopg2-binary==2.9.9

echo "==> Building React frontend..."
cd ../frontend
npm install
npm run build
cd ../backend

echo "==> Collecting static files..."
python manage.py collectstatic --no-input

echo "==> Running database migrations..."
python manage.py migrate

echo "==> Seeding demo data (idempotent)..."
python manage.py seed_demo

echo "==> Build complete ✅"
