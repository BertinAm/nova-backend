# NOVA Backend API

Navigational Object and Voice Assistant

| Field | Value |
| --- | --- |
| **Framework** | FastAPI 0.111 (Python 3.11+) |
| **Database** | PostgreSQL 15 + SQLAlchemy 2.0 (async) + Alembic |
| **Auth** | JWT (python-jose) + bcrypt (passlib) |
| **ML Inference** | BLIP-2 (scene description) + InsightFace (face matching) |
| **Deployment** | Docker + Docker Compose |
| **License** | MIT |

---

## What This Repository Contains

This repository is the server-side component of NOVA. It exposes the REST API endpoints that the NOVA mobile app calls for tasks that cannot run on-device: cloud-assisted scene description, server-side face matching for large enrolled galleries, usage log synchronisation from offline devices, and over-the-air (OTA) TFLite model delivery to the mobile app.

It does not contain: the Flutter mobile application (see *nova-mobile*), or the ML training pipeline (see *nova-ml*).

## Architecture

```text
nova-backend/
├── app/
│   ├── main.py              # FastAPI app factory + lifespan
│   ├── config.py            # Pydantic Settings (environment variables)
│   ├── database.py          # Async SQLAlchemy engine + session
│   ├── dependencies.py      # Shared Depends() auth, DB session
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── routers/             # FastAPI routers (auth, scene, faces, logs, models)
│   ├── services/            # Business logic
│   ├── ml/                  # ML model wrappers (SceneDescriber, FaceMatcher)
│   └── security/            # JWT helpers, bcrypt hashing
├── alembic/                 # Database migrations
├── tests/                   # pytest test suite
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example

```

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | /auth/register | Register a new user account |
| POST | /auth/login | Login and receive JWT access + refresh tokens |
| POST | /auth/refresh | Exchange refresh token for new access token |
| POST | /scene/describe | Upload image, receive scene description (BLIP-2) |
| POST | /faces/enrol | Enrol a face crop with a contact name |
| POST | /faces/match | Match a probe embedding against enrolled gallery |
| DELETE | /faces/{face_id} | Delete an enrolled contact and their embedding |
| POST | /logs/sync | Batch-sync offline usage events from device |
| POST | /logs/feedback/sync | Batch-sync offline user feedback from device |
| GET | /models/latest/{module_id} | Get latest active model metadata for a module |
| GET | /models/download/{model_id} | Download TFLite model file |
| POST | /models/register | Register a new model version (admin only) |
| GET | /health | Service health check |

## Getting Started

### Prerequisites

* Python 3.11+
* Docker and Docker Compose
* PostgreSQL 15 (handled by Docker Compose)
* A HuggingFace account (for scene description model download on first run)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/nova-backend.git
cd nova-backend
cp .env.example .env
# Edit .env and fill in all required values (see .env.example for reference)

```

### 2. .env.example reference

```text
DATABASE_URL=postgresql+asyncpg://nova_user:yourpassword@db:5432/nova_db
REDIS_URL=redis://redis:6379
JWT_SECRET_KEY=your_very_long_random_secret_key_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=30
EMBEDDING_ENCRYPTION_KEY=your_32_byte_hex_key_here
USE_LOCAL_VLM=true
VLM_MODEL_NAME=Salesforce/blip2-opt-2.7b
OPENAI_API_KEY=                    # Only needed if USE_LOCAL_VLM=false
RATE_LIMIT_PER_MINUTE=60
MODEL_STORAGE_PATH=/app/models
POSTGRES_PASSWORD=yourpassword

```

### 3. Run with Docker Compose

```bash
docker compose up --build
# API will be available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
# ReDoc at http://localhost:8000/redoc

```

### 4. Apply database migrations

```bash
# In a new terminal, after containers are running:
docker compose exec api alembic upgrade head

```

### 5. Run tests

```bash
docker compose exec api pytest tests/ -v

```

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| DATABASE_URL | Yes | Async PostgreSQL connection string (asyncpg driver) |
| JWT_SECRET_KEY | Yes | Long random string for JWT signing. Generate with: `openssl rand -hex 32` |
| EMBEDDING_ENCRYPTION_KEY | Yes | 32-byte hex key for AES-256 face embedding encryption |
| USE_LOCAL_VLM | No | `true` = run BLIP-2 locally, `false` = use OpenAI GPT-4-Vision. Default: `true` |
| OPENAI_API_KEY | Conditional | Required only when `USE_LOCAL_VLM=false` |
| REDIS_URL | No | Redis connection string. Default: `redis://localhost:6379` |
| RATE_LIMIT_PER_MINUTE | No | API rate limit per user. Default: 60 |
| MODEL_STORAGE_PATH | No | Path where TFLite model files are stored. Default: `/app/models` |

## Security Notes

* All API communication uses HTTPS. Never deploy without TLS in production.
* Face embedding vectors are encrypted at rest using AES-256 (Fernet). Raw face images are never stored.
* Raw camera frames sent for scene description are processed in memory and never written to disk or database.
* JWT access tokens expire after 24 hours. Refresh tokens expire after 30 days.

## Related Repositories

* [nova-mobile](https://www.google.com/search?q=https://github.com/your-org/nova-mobile) Flutter Android application
* [nova-ml](https://www.google.com/search?q=https://github.com/your-org/nova-ml) ML training pipeline and HuggingFace publishing
* [huggingface.co/nova-assistive](https://www.google.com/search?q=https://huggingface.co/nova-assistive) Published TFLite models

---

**Licence**
MIT see LICENSE file

University of Buea, Faculty of Engineering and Technology, Department of Computer Engineering. Internet of Things and Video Processing Academic Year 2025/2026.
