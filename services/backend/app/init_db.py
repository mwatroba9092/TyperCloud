"""Tworzenie tabel w bazie danych.

Uruchamiany jako initContainer w K8s PRZED startem API - dzieki temu
schemat jest gotowy zanim FastAPI zacznie przyjmowac ruch.
"""
from .database import Base, engine
from . import models  # noqa: F401  (rejestruje modele w metadata)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    print("Tabele utworzone (lub juz istnialy).")


if __name__ == "__main__":
    init_db()
