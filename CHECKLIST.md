# Lista kontrolna wymagań — TyperCloud
**Dowody działania**.

---

## A. Stos technologiczny

| Wymóg | Status | Gdzie / jak |
|---|:---:|---|
| Frontend w 100% Python (Streamlit) | ✅ | `services/frontend/app.py` |
| Backend API (FastAPI) | ✅ | `services/backend/app/main.py` |
| Worker (asynchroniczny skrypt Python) | ✅ | `services/worker/worker.py` |
| Kolejka / Cache (Redis) | ✅ | `k8s/base/redis-deployment.yaml`, użycie w `main.py` + `worker.py` |
| Baza danych (PostgreSQL) | ✅ | `k8s/base/postgres-statefulset.yaml` |
| Serwer autoryzacji Zitadel (NIE Keycloak) | ✅ | `k8s/base/auth-statefulset.yaml` |
| Docker / Kubernetes / Kustomize / GitHub Actions | ✅ | `services/*/Dockerfile`, `k8s/`, `.github/workflows/deploy.yaml` |

---

## B. Architektura i logika biznesowa

| Wymóg | Status | Gdzie / jak |
|---|:---:|---|
| Tabele: Użytkownicy, Mecze, Typy | ✅ | `services/backend/app/models.py` (`User`, `Match`, `Prediction`) |
| Frontend obsługuje logowanie i odpytuje API | ✅ | `services/frontend/app.py` + `auth.py` |
| Backend weryfikuje tokeny i zapisuje dane | ✅ | `services/backend/app/security.py`, `main.py` |
| Redis odbiera sygnał o końcu meczu od API | ✅ | `main.py` → `redis_client.publish(...)` w `set_match_result` |
| Worker nasłuchuje Redis i przelicza punkty | ✅ | `worker.py` (`pubsub.listen()` + `calculate_points`) |

---

## C. Bezpieczeństwo (OAuth 2.0)

| Wymóg | Status | Gdzie / jak |
|---|:---:|---|
| OAuth 2.0 z PKCE na frontendzie (klient publiczny) | ✅ | `services/frontend/auth.py` (`generate_pkce`, S256, wymiana kodu **bez** `client_secret`) |
| Zewnętrzny Auth Server jako StatefulSet + własny PV | ✅ | `k8s/base/auth-statefulset.yaml` (`volumeClaimTemplates`) |
| API zabezpieczone JWT | ✅ | `security.py` (pobieranie JWKS, weryfikacja podpisu RS256, `iss`/`aud`) |
| `GET /health` — niezabezpieczony | ✅ | `main.py` → `health()` |
| `GET /api/matches` — zalogowany | ✅ | `main.py` → `Depends(get_current_user)` |
| `POST /api/predictions` — rola USER | ✅ | `main.py` → `Depends(require_role("USER"))` |
| `GET /api/rankings` — zalogowany | ✅ | `main.py` → `Depends(get_current_user)` |
| `POST /api/matches` — rola ADMIN | ✅ | `main.py` → `Depends(require_role("ADMIN"))` |

---

## D. Kubernetes i CI/CD

| Wymóg | Status | Gdzie / jak |
|---|:---:|---|
| Kustomize: base / dev / prod | ✅ | `k8s/base/`, `k8s/overlays/dev/`, `k8s/overlays/prod/` |
| Deployment Frontend | ✅ | `k8s/base/frontend-deployment.yaml` |
| Deployment Backend (≥2 repliki, RollingUpdate) | ✅ | `backend-deployment.yaml` (`replicas: 2`, `strategy.RollingUpdate`) |
| Deployment Worker (1 replika) | ✅ | `worker-deployment.yaml` (`replicas: 1`) |
| PostgreSQL jako StatefulSet + PVC | ✅ | `postgres-statefulset.yaml` (`volumeClaimTemplates: 1Gi`) |
| Auth Server jako StatefulSet + PVC | ✅ | `auth-statefulset.yaml` (`volumeClaimTemplates: 1Gi`) |
| Izolacja: wejście tylko przez Ingress | ✅ | `ingress.yaml` (tylko `frontend` + `zitadel`); reszta = ClusterIP |
| Komunikacja wewnętrzna przez Service | ✅ | każdy `*-deployment/statefulset.yaml` zawiera `Service` |
| NetworkPolicy: Postgres/Redis tylko od backend+worker | ✅ | `k8s/base/networking/networkpolicy.yaml` |
| ConfigMap (konfiguracja) | ✅ | `k8s/base/configmap.yaml` |
| Secret (poufne hasła, zero hardcode) | ✅ | `k8s/base/secrets.example.yaml`; w kodzie wszystko z ENV (`config.py`) |
| readinessProbe / livenessProbe | ✅ | wszystkie główne kontenery (HTTP `/health`, `pg_isready`, `redis-cli ping`, `pgrep`) |
| resources.requests / limits | ✅ | wszystkie główne kontenery |
| securityContext (run as non-root) | ✅ | `runAsNonRoot: true` + `runAsUser` w manifestach; `USER appuser` w Dockerfile'ach |
| InitContainer (migracje przed startem API) | ✅ | `backend-deployment.yaml` → init `db-migrate` (`python -m app.init_db`) |
| PodDisruptionBudget dla backendu | ✅ | `k8s/base/backend-pdb.yaml` (`minAvailable: 1`) |
| Obserwowalność: `/metrics` + adnotacje Prometheus | ✅ | `services/backend/app/metrics.py`; adnotacje w `backend-deployment.yaml` |
| CI/CD: build + pytest + push + deploy + rollout status | ✅ | `.github/workflows/deploy.yaml` |

---

## E. Dowody działania

### E.1. Endpoint `/health` (niezabezpieczony)

```bash
curl -i http://localhost:8000/health
# HTTP/1.1 200 OK
# {"status":"ok"}
```

Dla porównania endpoint zabezpieczony bez tokenu zwróci **401/403**:

```bash
curl -i http://localhost:8000/api/matches
# HTTP/1.1 403 Forbidden  (brak nagłówka Authorization: Bearer ...)
```

---

### E.2. Dowód trwałości bazy danych (PersistentVolume)

Cel: pokazać, że dane **przeżywają restart poda** dzięki `PersistentVolumeClaim`.

**Wariant Kubernetes:**

```bash
# 1. Dodaj mecz (jako ADMIN) - tu skrótowo przez API z tokenem:
curl -X POST http://localhost:8000/api/matches \
  -H "Authorization: Bearer <TOKEN_ADMINA>" \
  -H "Content-Type: application/json" \
  -d '{"team_a":"Polska","team_b":"Niemcy"}'

# 2. Sprawdz, ze mecz istnieje:
curl http://localhost:8000/api/matches -H "Authorization: Bearer <TOKEN>"

# 3. USUN poda bazy danych (Kubernetes odtworzy go ze StatefulSet):
kubectl delete pod postgres-0 -n typercloud-dev

# 4. Poczekaj, az pod wstanie ponownie:
kubectl rollout status statefulset/postgres -n typercloud-dev

# 5. Ponownie pobierz mecze - REKORD NADAL ISTNIEJE (dane na PVC przetrwaly):
curl http://localhost:8000/api/matches -H "Authorization: Bearer <TOKEN>"
```

**Wariant docker compose (lokalnie):**

```bash
docker compose restart postgres      # restart kontenera bazy
# wolumen 'pgdata' jest trwaly -> mecze dodane wczesniej nadal sa w bazie
```

---

### E.3. Dowód działania kolejki (Redis + Worker) — krok po kroku

Scenariusz pokazuje **asynchroniczne przeliczanie punktów** bez blokowania API:

1. **USER typuje wynik** meczu → `POST /api/predictions`
   (np. typ `2:1`). Rekord trafia do tabeli `predictions`.

2. **ADMIN wpisuje rzeczywisty wynik** → `PUT /api/matches/{id}/result`
   (np. `2:1`). Backend:
   - zapisuje wynik i ustawia `status = "finished"` w Postgresie,
   - **publikuje `match_id` na kanał Redis** (`redis_client.publish("match_finished", id)`),
   - **natychmiast** zwraca odpowiedź 200 (nie czeka na przeliczenie — API nieblokujące).

3. **Worker** (osobny proces) w pętli `pubsub.listen()`:
   - odbiera `match_id` z kanału Redis,
   - pobiera z Postgresa rzeczywisty wynik oraz wszystkie typy danego meczu,
   - przelicza punkty wg reguł:
     - **3 pkt** — idealny wynik (typ == wynik),
     - **1 pkt** — poprawny rezultat (ten sam zwycięzca/remis), inny wynik,
     - **0 pkt** — błędny rezultat,
   - zapisuje `points_awarded` przy typie i **aktualizuje sumę punktów** użytkownika.

4. **Ranking** (`GET /api/rankings`) pokazuje zaktualizowane punkty.

**Jak zaobserwować w praktyce:**

```bash
# Podglad logow workera (Kubernetes):
kubectl logs -f deployment/worker -n typercloud-dev
# spodziewany log po wpisaniu wyniku:
# [worker] Przeliczono mecz 1: 3 typow.

# Podglad logow workera (docker compose):
docker compose logs -f worker

# Reczne wstrzykniecie sygnalu do Redis (test samego przeplywu kolejki):
docker compose exec redis redis-cli PUBLISH match_finished 1
```

Punktacja jest funkcją czystą (`calculate_points` w `worker.py`) — łatwo zweryfikować:

| Typ | Wynik | Punkty | Powód |
|---|---|:---:|---|
| 2:1 | 2:1 | **3** | idealny wynik |
| 1:0 | 3:0 | **1** | poprawny zwycięzca, inny wynik |
| 0:0 | 1:2 | **0** | błędny rezultat |

---

### E.4. Metryki Prometheus

```bash
curl http://localhost:8000/metrics | grep typercloud
# typercloud_predictions_created_total ...
# typercloud_matches_finished_total ...
```

W Kubernetes pod backendu ma adnotacje `prometheus.io/scrape: "true"` (port `8000`, path `/metrics`).
