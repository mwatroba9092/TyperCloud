# TyperCloud

**TyperCloud** to chmurowa (cloud-native) aplikacja do typowania wyników meczów piłkarskich,
zbudowana w architekturze mikroserwisowej. Projekt demonstruje praktyczne wykorzystanie
Kubernetes, CI/CD oraz zabezpieczeń **OAuth 2.0 (PKCE + JWT)**.

> Logika biznesowa jest celowo prosta — nacisk położono na **czystą architekturę chmurową**:
> izolację warstw, trwałość danych, asynchroniczne przetwarzanie i bezpieczeństwo.

---

## 1. Architektura

```
                          Ingress (NGINX)
                          /             \
                http://app...     http://auth...
                     |                   |
            +--------v--------+   +-------v--------+
            |  Frontend       |   |  Zitadel       |
            |  (Streamlit)    |   |  (OAuth2 / OIDC)|
            |  OAuth2 + PKCE  |   |  StatefulSet+PVC|
            +--------+--------+   +-------+--------+
                     | JWT (Bearer)       | dane w bazie
            +--------v--------+           |
            |  Backend (API)  |           |
            |  FastAPI        +-----------+
            |  weryfikacja JWT|        (Postgres)
            +----+-------+----+
        publish  |       | zapis/odczyt
       (match_id)|       |
            +----v--+  +-v-------------------+
            | Redis |  | PostgreSQL          |
            |(kolej-|  | StatefulSet + PVC   |
            | ka)   |  | users/matches/preds |
            +----+--+  +-^-------------------+
                 | subscribe | zapis punktow
            +----v-----------+----+
            |  Worker             |
            |  (async scoring)    |
            +---------------------+
```

**Przepływ asynchroniczny (dowód działania kolejki):** gdy ADMIN wpisuje wynik meczu,
Backend zapisuje go w Postgresie i **publikuje `match_id` na kanale Redis**. API natychmiast
odpowiada (nie blokuje się przeliczaniem). **Worker** nasłuchuje kanału, pobiera wynik i typy,
przelicza punkty użytkowników i aktualizuje ranking w bazie.

Szczegóły: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 2. Stos technologiczny

| Warstwa | Technologia |
|---|---|
| Frontend | **Streamlit** (czysty Python) |
| Backend API | **FastAPI** (Python) |
| Worker | **Python** (asynchroniczny konsument Redis) |
| Kolejka / Cache | **Redis** (pub/sub) |
| Baza danych | **PostgreSQL** |
| Serwer autoryzacji | **Zitadel** (OAuth 2.0 / OIDC) |
| Konteneryzacja | **Docker** (obrazy non-root) |
| Orkiestracja | **Kubernetes** + **Kustomize** (base / dev / prod) |
| CI/CD | **GitHub Actions** |

---

## 3. Punkty końcowe API (FastAPI)

| Metoda | Ścieżka | Zabezpieczenie |
|---|---|---|
| `GET` | `/health` | **brak** (health-check) |
| `GET` | `/metrics` | brak (metryki Prometheus) |
| `GET` | `/api/matches` | zalogowany użytkownik |
| `POST` | `/api/matches` | rola **ADMIN** |
| `PUT` | `/api/matches/{id}/result` | rola **ADMIN** (wysyła sygnał do Redis) |
| `POST` | `/api/predictions` | rola **USER** |
| `GET` | `/api/rankings` | zalogowany użytkownik |

---

## 4. Struktura repozytorium

```
TyperCloud/
├── services/              # Kod aplikacji
│   ├── backend/           # FastAPI (API + walidacja JWT + /metrics)
│   ├── frontend/          # Streamlit (UI + OAuth2 PKCE)
│   └── worker/            # Konsument Redis (przeliczanie punktów)
├── k8s/                   # Manifesty Kubernetes (Kustomize)
│   ├── base/              # Wspólna definicja zasobów
│   └── overlays/          # Nakładki: dev / prod
├── .github/workflows/     # CI/CD (deploy.yaml)
├── docker-compose.yaml    # Lokalne środowisko (WSL2)
├── README.md
├── CHECKLIST.md           # Mapa wymagań dla prowadzącego
└── docs/ARCHITECTURE.md
```

---

## 5. Uruchomienie lokalne (WSL2 / Ubuntu 24.04)

Wymagania: **Docker** + **Docker Compose** (`docker compose`).

```bash
# 1. Wejdz do katalogu projektu
cd TyperCloud

# 2. Zbuduj i uruchom caly stack (Postgres, Redis, Zitadel, Backend, Worker, Frontend)
docker compose up --build
```

Po uruchomieniu:

| Usługa | Adres |
|---|---|
| **Frontend (Streamlit)** | http://localhost:8501 |
| Backend API | http://localhost:8000 (np. `GET /health`) |
| Zitadel (logowanie) | http://localhost:8080 |

Szybki test, że API żyje:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### Konfiguracja Zitadel (pierwsze logowanie)
Zitadel przy pierwszym starcie tworzy konsolę administracyjną pod http://localhost:8080.
Aby logowanie OAuth zadziałało end-to-end, należy w konsoli Zitadel:
1. utworzyć **Projekt** i w nim **aplikację typu User Agent / PKCE** (klient publiczny, bez sekretu),
2. ustawić **Redirect URI** na `http://localhost:8501/`,
3. skopiować wygenerowany **Client ID** do `OIDC_CLIENT_ID` (frontend) i `OIDC_AUDIENCE` (backend) — w projekcie: `375085643967037445`,
4. zdefiniować role projektu **USER** oraz **ADMIN** i przypisać je użytkownikom.

> Logika aplikacji i walidacja tokenów są gotowe — powyższe to jednorazowa konfiguracja IdP.

---

## 6. Wdrożenie na Kubernetes

```bash
# Podglad wyrenderowanych manifestow
kubectl kustomize k8s/overlays/dev

# Wdrozenie srodowiska DEV
kubectl apply -k k8s/overlays/dev

# Wdrozenie srodowiska PROD
kubectl apply -k k8s/overlays/prod

# Weryfikacja rolloutu backendu
kubectl rollout status deployment/backend -n typercloud-dev --timeout=90s
```

> Przed realnym wdrożeniem skopiuj `k8s/base/secrets.example.yaml` i **podmień hasła**
> (wartości są w base64 jako DEMO).

---

## 7. CI/CD

Pipeline (`.github/workflows/deploy.yaml`) uruchamiany przy `push` na `main`:

1. **test** — `pytest` na backendzie,
2. **build-and-push** — Docker Buildx buduje obrazy `backend/frontend/worker` i publikuje do **GHCR**,
3. **deploy** — `kubectl apply -k k8s/overlays/dev` + `kubectl rollout status`.

Obrazy publikowane do `ghcr.io/mwatroba9092/typercloud/*` (zgodnie z `IMAGE_NAMESPACE` w workflow).
Do ręcznej konfiguracji w GitHubie pozostaje tylko sekret **`KUBE_CONFIG`** (kubeconfig w plain text lub base64), jeśli chcesz auto-deploy z Actions na klaster.

---

## 8. Testy

```bash
cd services/backend
pip install -r requirements.txt
pytest -v
```
