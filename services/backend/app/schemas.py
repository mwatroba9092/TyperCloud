"""Modele Pydantic uzywane w request/response API."""
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MatchCreate(BaseModel):
    team_a: str
    team_b: str


class MatchResult(BaseModel):
    score_a: int
    score_b: int


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_a: str
    team_b: str
    score_a: Optional[int] = None
    score_b: Optional[int] = None
    status: str


class PredictionCreate(BaseModel):
    match_id: int
    # "score" = dokladny wynik, "outcome" = rezultat 1/X/2.
    bet_type: str = "score"
    predicted_score_a: Optional[int] = None
    predicted_score_b: Optional[int] = None
    # "home" / "draw" / "away" (tylko dla bet_type == "outcome").
    predicted_outcome: Optional[str] = None


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    bet_type: str
    predicted_score_a: Optional[int] = None
    predicted_score_b: Optional[int] = None
    predicted_outcome: Optional[str] = None
    points_awarded: Optional[int] = None


class RankingRow(BaseModel):
    username: str
    points: int
