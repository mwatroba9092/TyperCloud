# Architektura TyperCloud

Dokument opisuje przepływ danych, kontrakty między serwisami oraz model danych.

## 1. Komponenty

| Serwis | Rola | Widoczność |
|---|---|---|
| **Frontend** (Streamlit) | UI, logowanie OAuth2 PKCE, wywołania API | publiczny (Ingress) |
| **Zitadel** | serwer autoryzacji OIDC, wystawia tokeny JWT | publiczny (Ingress) |
| **Backend** (FastAPI) | API, walidacja JWT, zapis danych, publikacja zdarzeń | wewnętrzny (Service) |
| **Worker** | konsument Redis, przeliczanie punktów | wewnętrzny (brak Service) |
| **Redis** | kolejka pub/sub zdarzeń o zakończonych meczach | wewnętrzny (Service) |
| **PostgreSQL** | trwałe przechowywanie danych | wewnętrzny (headless Service) |

## 2. Przepływ uwierzytelnienia (OAuth 2.0 + PKCE)

```
Frontend                         Zitadel                        Backend
   |  1. generate code_verifier      |                              |
   |     + code_challenge (S256)     |                              |
   |  2. redirect /authorize ------->|                              |
   |     (code_challenge)            |                              |
   |  3. login uzytkownika           |                              |
   |<------ 4. redirect z 'code' ----|                              |
   |  5. POST /token                 |                              |
   |     (code + code_verifier,      |                              |
   |      BEZ client_secret) ------->|                              |
   |<------ 6. access_token (JWT) ---|                              |
   |  7. GET /api/... (Bearer JWT) ----------------------------->   |
   |                                 |   8. pobierz JWKS  <---------|
   |                                 |------ klucze publiczne ----->|
   |                                 |   9. weryfikacja podpisu,    |
   |                                 |      iss, aud, roli          |
   |<---------------- 10. odpowiedz JSON --------------------------|
```

Klient publiczny **nie posiada sekretu** — bezpieczeństwo zapewnia PKCE
(`code_verifier` znany tylko frontendowi). Backend jest *resource serverem*:
weryfikuje token kluczami publicznymi (JWKS), nie przechowuje żadnego sekretu.

## 3. Przepływ asynchroniczny (kolejka)

```
ADMIN ---PUT /api/matches/{id}/result---> Backend
                                             | zapis wyniku (Postgres)
                                             | status = finished
                                             | PUBLISH match_id -> Redis
                                             | return 200 (NIE blokuje!)
                                             v
                          Redis (kanal "match_finished")
                                             |
                                             v
Worker  --SUBSCRIBE--> odbiera match_id
        --SELECT-----> wynik meczu + typy (Postgres)
        --oblicz------> calculate_points()  (3 / 1 / 0 pkt)
        --UPDATE-----> points_awarded + users.points (Postgres)
```

Dzięki rozdzieleniu API od Workera, dodanie wyniku meczu jest natychmiastowe,
a kosztowne przeliczanie odbywa się w tle.

## 4. Model danych

```
users                  matches                   predictions
-----                  -------                   -----------
id (PK, =sub JWT)      id (PK)                    id (PK)
username               team_a                     user_id  (FK -> users.id)
points                 team_b                     match_id (FK -> matches.id)
                       score_a (nullable)         predicted_score_a
                       score_b (nullable)         predicted_score_b
                       status                     points_awarded (nullable)
                                                  UNIQUE(user_id, match_id)
```

- `users.id` to claim `sub` z tokenu Zitadel — użytkownik jest tworzony przy
  pierwszym typowaniu (`_ensure_user` w `main.py`).
- `predictions` ma ograniczenie unikalności, więc jeden użytkownik typuje dany
  mecz tylko raz.

## 5. Reguły punktacji

Funkcja czysta `calculate_points(pred_a, pred_b, real_a, real_b)` w `worker.py`:

| Warunek | Punkty |
|---|:---:|
| Dokładny wynik (`pred == real`) | 3 |
| Ten sam rezultat (zwycięzca/remis), inny wynik | 1 |
| Błędny rezultat | 0 |

Aktualizacja punktów użytkownika jest **idempotentna** — przy ponownym
przeliczeniu meczu korygowana jest różnica (`new - previous`).

## 6. Mapowanie konfiguracji (ENV)

| Zmienna | Źródło w K8s | Opis |
|---|---|---|
| `DATABASE_URL` | Secret | połączenie do Postgresa (z hasłem) |
| `REDIS_URL`, `REDIS_CHANNEL` | ConfigMap | kolejka |
| `OIDC_ISSUER`, `OIDC_JWKS_URL`, `OIDC_AUDIENCE`, `OIDC_ROLES_CLAIM` | ConfigMap | weryfikacja JWT |
| `API_URL`, `OIDC_CLIENT_ID`, `OIDC_REDIRECT_URI`, `OIDC_SCOPE` | ConfigMap | frontend |
| `ZITADEL_MASTERKEY`, `POSTGRES_*` | Secret | dane wrażliwe |
```
