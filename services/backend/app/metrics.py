"""Liczniki Prometheus eksponowane na /metrics."""
from prometheus_client import Counter

# Licznik utworzonych typow przez uzytkownikow.
PREDICTIONS_CREATED = Counter(
    "typercloud_predictions_created_total",
    "Liczba zapisanych typow uzytkownikow",
)

# Licznik meczow oznaczonych jako zakonczone (i wyslanych do kolejki Redis).
MATCHES_FINISHED = Counter(
    "typercloud_matches_finished_total",
    "Liczba meczow zakonczonych i wyslanych do przeliczenia",
)
