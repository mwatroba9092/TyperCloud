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
    bet_type = Column(String, nullable=False, default="score")
    predicted_score_a = Column(Integer, nullable=True)
    predicted_score_b = Column(Integer, nullable=True)
    predicted_outcome = Column(String, nullable=True)
    points_awarded = Column(Integer, nullable=True)


def _outcome(a: int, b: int) -> str:
    if a > b:
        return "home"
    if a < b:
        return "away"
    return "draw"


def score_bet(pred_a: int, pred_b: int, real_a: int, real_b: int) -> int:
    if pred_a == real_a and pred_b == real_b:
        return 3
    if _outcome(pred_a, pred_b) == _outcome(real_a, real_b):
        return 1
    return 0


def score_outcome(predicted_outcome: str, real_a: int, real_b: int) -> int:
    return 1 if predicted_outcome == _outcome(real_a, real_b) else 0


def points_for_prediction(pred: "Prediction", real_a: int, real_b: int) -> int:
    if pred.bet_type == "outcome":
        return score_outcome(pred.predicted_outcome, real_a, real_b)
    return score_bet(pred.predicted_score_a, pred.predicted_score_b, real_a, real_b)


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
            new_points = points_for_prediction(pred, match.score_a, match.score_b)
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
