from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, nullable=False)
    points = Column(Integer, nullable=False, default=0)

    predictions = relationship("Prediction", back_populates="user")


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    team_a = Column(String, nullable=False)
    team_b = Column(String, nullable=False)
    score_a = Column(Integer, nullable=True)
    score_b = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="scheduled")

    predictions = relationship("Prediction", back_populates="match")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("user_id", "match_id", name="uq_user_match"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    bet_type = Column(String, nullable=False, default="score")
    predicted_score_a = Column(Integer, nullable=True)
    predicted_score_b = Column(Integer, nullable=True)
    predicted_outcome = Column(String, nullable=True)
    points_awarded = Column(Integer, nullable=True)

    user = relationship("User", back_populates="predictions")
    match = relationship("Match", back_populates="predictions")
