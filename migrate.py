"""
Migration runner: applies pending SQL migrations in order and seeds base users.
Run before starting the bot: python migrate.py
"""
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
BRAIAN_TELEGRAM_ID = int(os.getenv("BRAIAN_TELEGRAM_ID") or "0")
CONSTANZA_TELEGRAM_ID = int(os.getenv("CONSTANZA_TELEGRAM_ID") or "0")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set.", file=sys.stderr)
        sys.exit(1)

    print("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # Tabla de control de migraciones
    cur.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # Migraciones ya aplicadas
    cur.execute("SELECT name FROM _migrations ORDER BY name")
    applied = {row[0] for row in cur.fetchall()}

    # Aplicar las pendientes en orden
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print("No migration files found.")
    for mf in migration_files:
        if mf.name in applied:
            print(f"  [skip]  {mf.name}")
            continue
        print(f"  [apply] {mf.name}")
        cur.execute(mf.read_text())
        cur.execute("INSERT INTO _migrations (name) VALUES (%s)", (mf.name,))
        conn.commit()

    # Seed de usuarios (idempotente)
    if BRAIAN_TELEGRAM_ID:
        cur.execute(
            "INSERT INTO users (telegram_id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (BRAIAN_TELEGRAM_ID, "Braian"),
        )
    if CONSTANZA_TELEGRAM_ID:
        cur.execute(
            "INSERT INTO users (telegram_id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (CONSTANZA_TELEGRAM_ID, "Constanza"),
        )
    conn.commit()

    cur.close()
    conn.close()
    print("Migrations complete.")


if __name__ == "__main__":
    run_migrations()
