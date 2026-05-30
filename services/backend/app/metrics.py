from prometheus_client import Counter

PREDICTIONS_CREATED = Counter(
    "typercloud_predictions_created_total",
    "Liczba zapisanych typow uzytkownikow",
)

MATCHES_FINISHED = Counter(
    "typercloud_matches_finished_total",
    "Liczba meczow zakonczonych i wyslanych do przeliczenia",
)
