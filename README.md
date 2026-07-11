# NOVA Backend

FastAPI backend for **NOVA — Navigational Object and Voice Assistant**. Handles
authentication, cloud scene description, server-side face matching, usage-log
sync, and OTA TFLite model distribution for the NOVA Flutter mobile app.

See `D:\nova\docs` for the full SRS, database design, and mobile implementation
guides this backend implements.

## Stack

- FastAPI 0.111 (async) + Uvicorn/Gunicorn
- SQLAlchemy 2.0 (async) + Alembic migrations
- PostgreSQL 15 (production), SQLite/aiosqlite (tests)
- Redis 7 (rate limiting)
- InsightFace (server-side face matching), BLIP-2 or GPT-4V (scene description)
- JWT auth (python-jose) + bcrypt (passlib)
- AES-256/Fernet encryption for biometric embeddings and PII at rest

## Project layout

```
app/
  main.py            FastAPI app factory + lifespan (loads ML models on startup)
  config.py          Pydantic Settings (all config via env vars)
  database.py        Async engine/session factory
  logging_config.py  Structured JSON logging + audit_log() for security events
  middleware.py       Request logging + security headers
  rate_limit.py        Shared slowapi Limiter instance
  dependencies.py      get_current_user (JWT bearer auth)
  exceptions.py         Global exception handlers (consistent JSON error envelope)
  models/             SQLAlchemy ORM models
  schemas/            Pydantic request/response models
  routers/            HTTP endpoints (auth, scene, faces, logs, model_registry, emergency_contact)
  services/           Business logic (DB + audit logging, no HTTP concerns)
  ml/                  SceneDescriber (BLIP-2/cloud VLM), FaceMatcher (InsightFace)
  security/             jwt.py, hashing.py, crypto.py (Fernet)
alembic/                Migrations (0001_initial_schema, 0002_add_user_is_operator)
tests/                   pytest + httpx async test suite (SQLite by default, Postgres via TEST_DATABASE_URL, ML mocked)
.github/workflows/ci.yml  Lint + tests (SQLite + Postgres) + coverage gate (NFR-42)
```

## Local setup

```bash
cp .env.example .env
# Generate real secrets:
python -c "import secrets; print(secrets.token_hex(32))"   # JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"   # EMBEDDING_ENCRYPTION_KEY

python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Start Postgres + Redis only, run the API locally for fast iteration:
docker compose up -d db redis
alembic upgrade head
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for interactive OpenAPI/Swagger docs.

## Running with Docker Compose (full stack)

```bash
docker compose up --build
```

## Tests

```bash
pytest -v
# With coverage (CI enforces a 70% floor per NFR-42):
pytest -v --cov=app --cov-report=term-missing --cov-fail-under=70
```

Tests run against an in-memory SQLite database by default and mock the ML
wrappers (`SceneDescriber`, `FaceMatcher`) — no GPU, model weights, or
network access required.

To run the exact same suite against a real Postgres instance (this is what
CI does, to catch Postgres-specific behaviour SQLite can mask):

```bash
docker compose up -d db
export TEST_DATABASE_URL=postgresql+asyncpg://nova_user:changeme@localhost:5432/nova_db
pytest -v
```

`app/ml/*` is excluded from the coverage gate (see `pyproject.toml`) because
exercising it for real requires `torch`/`insightface` weights — those code
paths are covered by mocked unit tests instead, not raw line coverage.

## Database migrations

```bash
# After changing a model in app/models/:
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Security notes

- Raw camera frames and face images are **never persisted** — only encrypted
  embeddings (faces) or transient in-memory bytes (scene description).
- All biometric data and emergency-contact phone numbers are encrypted at
  rest with AES-256 (Fernet); the key is read from `EMBEDDING_ENCRYPTION_KEY`
  and must never be committed to source control.
- Passwords are hashed with bcrypt (cost factor 12).
- JWT access tokens expire in 24h; refresh tokens in 30 days.
- `nova.audit` logger emits structured (JSON) security events — auth
  attempts, face enrolment/deletion, model registration, emergency contact
  changes — without ever including secrets, raw images, or embedding vectors.
- `/models/register` requires `User.is_operator = true` (see migration
  `0002_add_user_is_operator`). Regular BVI user accounts get a 403. There
  is no self-service way to become an operator — set the flag directly in
  the database for trusted accounts.
- Rate limiting (`app/rate_limit.py`) is backed by `RATE_LIMIT_STORAGE_URI`.
  It defaults to `memory://` for local dev/tests; set it to the same value
  as `REDIS_URL` in any deployment running more than one Gunicorn worker or
  instance, otherwise each worker enforces its own independent quota.
- All error responses (4xx/5xx) share one JSON envelope —
  `{"error": {"code", "message", "request_id", "details"?}}` — produced by
  `app/exceptions.py`. `request_id` matches the `X-Request-ID` response
  header for log correlation.
- `/health` actually queries the database (`SELECT 1`) and returns 503 with
  `status: "degraded"` if it's unreachable, instead of always reporting ok.

## API summary

| Method | Endpoint                     | Auth | Description                          |
|--------|-------------------------------|------|---------------------------------------|
| POST   | `/auth/register`              | None | Register new user                    |
| POST   | `/auth/login`                 | None | Login, receive JWT tokens            |
| POST   | `/auth/refresh`                | None | Refresh access token                |
| POST   | `/scene/describe`              | JWT  | Upload image, get scene description |
| POST   | `/faces/enrol`                 | JWT  | Enrol a face crop with contact name |
| POST   | `/faces/match`                  | JWT  | Match probe embedding vs. gallery   |
| GET    | `/faces/`                       | JWT  | List enrolled contacts (names only) |
| DELETE | `/faces/{face_id}`              | JWT  | Delete an enrolled face              |
| POST   | `/logs/sync`                    | JWT  | Batch-sync offline usage events     |
| POST   | `/logs/feedback/sync`           | JWT  | Batch-sync feedback records          |
| GET    | `/models/latest/{module_id}`    | JWT  | Get latest active model metadata    |
| GET    | `/models/download/{model_id}`   | JWT  | Download TFLite model file           |
| POST   | `/models/register`              | JWT + operator | Register a new model version |
| GET    | `/emergency-contact/`            | JWT  | Get the user's emergency contact     |
| PUT    | `/emergency-contact/`            | JWT  | Create/replace the emergency contact |
| DELETE | `/emergency-contact/`            | JWT  | Delete the emergency contact         |
| GET    | `/health`                       | None | Liveness/readiness probe (checks DB) |

## CI

`.github/workflows/ci.yml` runs on every push/PR: `ruff check`, an Alembic
migration smoke test against a real Postgres service container, the test
suite against SQLite with a coverage gate (`--cov-fail-under=70`, NFR-42),
and the same suite again against Postgres. Heavy ML dependencies (`torch`,
`insightface`, `onnxruntime`, `transformers`) are intentionally excluded
from the CI install — see the note in the workflow file.
