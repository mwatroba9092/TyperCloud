"""TyperCloud API (FastAPI).

Endpointy:
  GET  /health            -> publiczny health-check
  GET  /metrics           -> metryki Prometheus
  GET  /api/matches       -> lista meczow (wymaga zalogowania)
  POST /api/matches       -> dodanie meczu (rola ADMIN)
  PUT  /api/matches/{id}/result -> wpisanie wyniku + sygnal do Redis (ADMIN)
  POST /api/predictions   -> typowanie (rola USER)
  GET  /api/rankings      -> tabela rankingowa (wymaga zalogowania)
"""
import redis
from fastapi import Depends, FastAPI, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.orm import Session

from . import models, schemas
from .config import get_settings
from .database import get_db
from .metrics import MATCHES_FINISHED, PREDICTIONS_CREATED
from .security import CurrentUser, get_current_user, require_role

settings = get_settings()
app = FastAPI(title=settings.app_name)

# Klient Redis (pub/sub) - polaczenie leniwe, wspoldzielone.
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def _ensure_user(db: Session, user: CurrentUser) -> models.User:
    """Tworzy rekord usera przy pierwszym kontakcie (na podstawie tokenu)."""
    db_user = db.get(models.User, user.sub)
    if db_user is None:
        db_user = models.User(id=user.sub, username=user.username, points=0)
        db.add(db_user)
        db.commit()
    return db_user


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/matches", response_model=list[schemas.MatchOut])
def list_matches(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
):
    return db.query(models.Match).order_by(models.Match.id).all()


@app.post(
    "/api/matches",
    response_model=schemas.MatchOut,
    status_code=status.HTTP_201_CREATED,
)
def create_match(
    payload: schemas.MatchCreate,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_role("ADMIN")),
):
    match = models.Match(
        team_a=payload.team_a, team_b=payload.team_b, status="scheduled"
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@app.put("/api/matches/{match_id}/result", response_model=schemas.MatchOut)
def set_match_result(
    match_id: int,
    payload: schemas.MatchResult,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_role("ADMIN")),
):
    match = db.get(models.Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Mecz nie istnieje")

    match.score_a = payload.score_a
    match.score_b = payload.score_b
    match.status = "finished"
    db.commit()

    # Sygnal do kolejki: worker przeliczy punkty asynchronicznie.
    redis_client.publish(settings.redis_channel, str(match.id))
    MATCHES_FINISHED.inc()
    return match


@app.post(
    "/api/predictions",
    response_model=schemas.PredictionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_prediction(
    payload: schemas.PredictionCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("USER")),
):
    _ensure_user(db, user)

    match = db.get(models.Match, payload.match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Mecz nie istnieje")
    if match.status != "scheduled":
        raise HTTPException(status_code=400, detail="Mecz juz sie rozpoczal/zakonczyl")

    existing = (
        db.query(models.Prediction)
        .filter_by(user_id=user.sub, match_id=payload.match_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Typ na ten mecz juz istnieje")

    prediction = models.Prediction(
        user_id=user.sub,
        match_id=payload.match_id,
        predicted_score_a=payload.predicted_score_a,
        predicted_score_b=payload.predicted_score_b,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    PREDICTIONS_CREATED.inc()
    return prediction


@app.get("/api/rankings", response_model=list[schemas.RankingRow])
def rankings(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
):
    users = db.query(models.User).order_by(models.User.points.desc()).all()
    return [schemas.RankingRow(username=u.username, points=u.points) for u in users]
