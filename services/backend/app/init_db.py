"""Tworzenie tabel w bazie danych + lekka migracja kolumn.

Uruchamiany jako initContainer w K8s PRZED startem API - dzieki temu
schemat jest gotowy zanim FastAPI zacznie przyjmowac ruch.
"""
from sqlalchemy import text

from .database import Base, engine
from . import models  # noqa: F401  (rejestruje modele w metadata)

# Idempotentne migracje dla istniejacych baz (create_all nie zmienia tabel,
# ktore juz istnieja, wiec nowe kolumny dokladamy recznie - Postgres).
_MIGRATIONS = [
    "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS bet_type VARCHAR NOT NULL DEFAULT 'score'",
    "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS predicted_outcome VARCHAR",
    "ALTER TABLE predictions ALTER COLUMN predicted_score_a DROP NOT NULL",
    "ALTER TABLE predictions ALTER COLUMN predicted_score_b DROP NOT NULL",
]


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for stmt in _MIGRATIONS:
            conn.execute(text(stmt))
    print("Tabele utworzone i zmigrowane (lub juz aktualne).")


if __name__ == "__main__":
    init_db()
