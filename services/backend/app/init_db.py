from sqlalchemy import text

from .database import Base, engine
from . import models

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
