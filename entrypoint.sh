#!/bin/sh
set -e

echo "==> Running database migrations..."
uv run python migrate.py

echo "==> Starting bot..."
exec uv run python main.py
