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
    predicted_score_a: int
    predicted_score_b: int


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    predicted_score_a: int
    predicted_score_b: int
    points_awarded: Optional[int] = None


class RankingRow(BaseModel):
    username: str
    points: int
