import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "")
# Kept for local SQLite fallback reference (unused with PostgreSQL)
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/finanzas.db")

BRAIAN_TELEGRAM_ID = int(os.getenv("BRAIAN_TELEGRAM_ID") or "0")
CONSTANZA_TELEGRAM_ID = int(os.getenv("CONSTANZA_TELEGRAM_ID") or "0")

ALLOWED_IDS = {BRAIAN_TELEGRAM_ID, CONSTANZA_TELEGRAM_ID}

USER_NAMES = {
    BRAIAN_TELEGRAM_ID: "Braian",
    CONSTANZA_TELEGRAM_ID: "Constanza",
}

# Categorías por tipo
CATEGORIES = {
    "income": [
        ("sueldo", "Sueldo"),
        ("freelance", "Freelance"),
        ("otro_ingreso", "Otro"),
    ],
    "expense_personal": [
        ("gustos", "Gustos / Innecesarios"),
        ("salud", "Salud"),
        ("ropa", "Ropa"),
        ("educacion", "Educacion"),
        ("otro_personal", "Otro Personal"),
    ],
    "expense_shared": [
        ("comida", "Comida / Super"),
        ("impuestos", "Impuestos / Servicios"),
        ("streaming", "Streaming / Plataformas"),
        ("alquiler", "Alquiler / Vivienda"),
        ("transporte", "Transporte"),
        ("otro_compartido", "Otro Compartido"),
    ],
    "saving": [
        ("viaje", "Viaje"),
        ("casamiento", "Casamiento"),
        ("fondo_emergencia", "Fondo Emergencia"),
        ("otro_ahorro", "Otro Ahorro"),
    ],
}

CURRENCIES = ["ARS", "USD", "USDT"]
