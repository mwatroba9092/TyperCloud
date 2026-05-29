"""Worker TyperCloud.

Nasluchuje kanalu Redis. Po otrzymaniu ID zakonczonego meczu:
  1. pobiera z PostgreSQL rzeczywisty wynik,
  2. pobiera wszystkie typy przypisane do tego meczu,
  3. przelicza punkty wg zasad:
       - 3 pkt: idealny wynik (typ == wynik),
       - 1 pkt: poprawny rezultat (zwyciezca/remis), ale niedokladny wynik,
       - 0 pkt: bledny rezultat,
  4. zapisuje punkty typu i aktualizuje sume punktow uzytkownika.

Worker jest samodzielnym serwisem - ma wlasne, minimalne modele ORM
odwzorowujace te same tabele co backend.
"""
import os

import redis
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://typer:typer@localhost:5432/typer"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
REDIS_CHANNEL = os.environ.get("REDIS_CHANNEL", "match_finished")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    username = Column(String, nullable=False)
    points = Column(Integer, nullable=False, default=0)


class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True)
    team_a = Column(String, nullable=False)
    team_b = Column(String, nullable=False)
    score_a = Column(Integer, nullable=True)
    score_b = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="scheduled")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("user_id", "match_id", name="uq_user_match"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    predicted_score_a = Column(Integer, nullable=False)
    predicted_score_b = Column(Integer, nullable=False)
    points_awarded = Column(Integer, nullable=True)


def _outcome(a: int, b: int) -> str:
    if a > b:
        return "home"
    if a < b:
        return "away"
    return "draw"


def calculate_points(pred_a: int, pred_b: int, real_a: int, real_b: int) -> int:
    if pred_a == real_a and pred_b == real_b:
        return 3
    if _outcome(pred_a, pred_b) == _outcome(real_a, real_b):
        return 1
    return 0


def process_match(match_id: int) -> None:
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        if match is None or match.score_a is None or match.score_b is None:
            print(f"[worker] Mecz {match_id} nie ma wyniku - pomijam.")
            return

        predictions = (
            db.query(Prediction).filter(Prediction.match_id == match_id).all()
        )
        for pred in predictions:
            new_points = calculate_points(
                pred.predicted_score_a,
                pred.predicted_score_b,
                match.score_a,
                match.score_b,
            )
            # Idempotencja: jesli juz przeliczono, korygujemy roznica.
            previous = pred.points_awarded or 0
            delta = new_points - previous
            pred.points_awarded = new_points

            user = db.get(User, pred.user_id)
            if user is not None:
                user.points = (user.points or 0) + delta

        db.commit()
        print(f"[worker] Przeliczono mecz {match_id}: {len(predictions)} typow.")
    finally:
        db.close()


def main() -> None:
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    pubsub.subscribe(REDIS_CHANNEL)
    print(f"[worker] Nasluchuje kanalu '{REDIS_CHANNEL}'...")

    for message in pubsub.listen():
        if message.get("type") != "message":
            continue
        try:
            match_id = int(message["data"])
        except (ValueError, TypeError):
            print(f"[worker] Zignorowano nieprawidlowa wiadomosc: {message['data']!r}")
            continue
        process_match(match_id)


if __name__ == "__main__":
    main()
