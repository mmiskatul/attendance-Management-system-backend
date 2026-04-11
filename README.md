# University Attendance Management Backend

Production-ready FastAPI backend for barcode-based student registration and facial-recognition attendance capture. The design is layered for maintainability, supports async MongoDB access, and is structured for future multi-campus, multi-device, and SaaS-style deployment.

## 1. System Architecture Overview

### Core architecture
- `FastAPI` provides the HTTP API, validation surface, and OpenAPI docs.
- `Pydantic` models separate request/response contracts from persistence models.
- `MongoDB` stores students, embeddings, attendance, users, audit logs, and migration history.
- `Service` and `Repository` layers keep HTTP concerns separate from business rules and persistence.
- `FaceEngine` is abstracted so the provider can move from `InsightFace` to another production model without rewriting the attendance flow.

### Registration flow
1. Admin calls `POST /api/v1/students/register` with barcode value and academic metadata.
2. The backend extracts `student_id` from the barcode using a configurable regex.
3. Admin calls `POST /api/v1/faces/enroll` with multiple base64 face samples.
4. The system detects a single face, checks image quality, optionally checks liveness, generates embeddings, prevents likely duplicate cross-student enrollment, and stores accepted embeddings as BSON binary float32 payloads.

### Attendance flow
1. Operator or terminal calls `POST /api/v1/attendance/recognize`.
2. The system validates image quality, detects a single live face, generates an embedding, loads active enrolled embeddings for the tenant and campus, and ranks by cosine similarity.
3. If confidence is below `FACE_MATCH_THRESHOLD`, the request is rejected as unknown.
4. If confidence is above threshold, the exact student is retrieved and attendance is marked unless the student already has attendance for the day and session.

### Scalability choices
- Async MongoDB driver and connection pooling.
- Embedding cache per tenant/campus to avoid repeated binary decoding on every recognition request.
- Redis-ready rate limiter with in-memory fallback.
- Multi-tenant and multi-campus fields on major collections.
- Pluggable face engine and liveness detector.
- Prometheus-ready middleware and `/metrics` endpoint.

## 2. Folder Structure

```text
app/
  api/
    v1/
      endpoints/
      router.py
      serializers.py
  core/
    config.py
    container.py
    exceptions.py
    logging.py
    rate_limiter.py
    security.py
  db/
    client.py
    dependencies.py
    indexes.py
    migrations.py
  middleware/
    metrics.py
    request_context.py
    security_headers.py
  models/
  repositories/
  schemas/
  services/
    face_engine/
  tests/
    integration/
    unit/
  utils/
  main.py
Dockerfile
docker-compose.yml
requirements.txt
.env.example
postman/university-attendance.postman_collection.json
```

## 3. Database Schema and Indexes

### Collections
- `students`
  - `tenant_id`, `campus_id`, `student_id`, `full_name`, `department`, `batch`, `semester`, `email`, `phone`, `status`, `barcode_value`, `face_embedding_count`, `created_at`, `updated_at`
- `face_embeddings`
  - `tenant_id`, `campus_id`, `student_id`, `embedding_binary`, `embedding_dim`, `pose`, `quality_score`, `model_name`, `is_active`, `created_at`
- `attendance_records`
  - `tenant_id`, `campus_id`, `student_id`, `attendance_date`, `attendance_session`, `check_in_time`, `device_id`, `confidence_score`, `attendance_status`, `matched_embedding_id`, `created_at`
- `users`
  - `tenant_id`, `username`, `hashed_password`, `role`, `is_active`, `created_at`
- `audit_logs`
  - `tenant_id`, `campus_id`, `actor_id`, `action`, `target_type`, `target_id`, `metadata`, `created_at`
- `schema_migrations`
  - `name`, `applied_at`

### Indexes
- `students`
  - unique: `(tenant_id, student_id)`
  - unique: `(tenant_id, barcode_value)`
- `face_embeddings`
  - `(tenant_id, campus_id, student_id, is_active)`
  - `(tenant_id, campus_id, created_at desc)`
- `attendance_records`
  - unique: `(tenant_id, student_id, attendance_date, attendance_session)`
  - `(tenant_id, campus_id, attendance_date desc)`
  - `(device_id, created_at desc)`
- `users`
  - unique: `(tenant_id, username)`
- `audit_logs`
  - `(tenant_id, created_at desc)`
  - `(actor_id, created_at desc)`
  - `(target_type, target_id)`

### Embedding storage
- Each embedding is L2-normalized.
- The normalized `float32` vector is converted to raw bytes and stored in MongoDB as `BSON Binary`.
- On retrieval, bytes are converted back to `numpy.float32` arrays for cosine similarity.

## 4. API Contract

### Required endpoints
- `POST /api/v1/auth/login`
- `POST /api/v1/students/register`
- `GET /api/v1/students/{student_id}`
- `POST /api/v1/faces/enroll`
- `POST /api/v1/attendance/recognize`
- `GET /api/v1/attendance/student/{student_id}`
- `GET /api/v1/attendance/daily`
- `GET /api/v1/health`
- `GET /api/v1/admin/audit-logs`

### Authentication
- Login returns a bearer token.
- `admin` can register students, enroll faces, and read audit logs.
- `operator` can recognize attendance and read student or attendance data.

### Matching contract
- Recognition returns:
  - `recognized`
  - `attendance_status`
  - `confidence_score`
  - matched `student`
  - `matched_embedding_id`
  - `attendance_record`
  - human-readable `message`

### OpenAPI and Postman
- Swagger UI: `/docs`
- ReDoc: `/redoc`
- Prometheus scrape endpoint: `/metrics`
- Postman collection: `postman/university-attendance.postman_collection.json`

## 5. Security and Scalability Decisions

- JWT bearer auth with hashed passwords.
- No hardcoded runtime secrets.
- Structured JSON logging with request IDs.
- Audit logging for registration, enrollment, login, attendance mark, duplicate detection, and rejected attendance attempts.
- Rate limiting on attendance recognition.
- Duplicate attendance blocked by service check and unique MongoDB index.
- Duplicate face enrollment reduced through cross-student similarity checks.
- CORS and secure response headers enabled.
- Multi-campus and multi-tenant fields included in core collections.
- Redis-backed rate limiting is preferred for horizontally scaled deployments.

## 6. Step-by-Step Implementation

1. Configuration, logging, security helpers, MongoDB client, indexes, and migrations.
2. Persistence models and repository layer.
3. Core services: barcode parsing, quality checks, liveness abstraction, embedding cache, matching.
4. Business services: auth, student registration, face enrollment, attendance recognition, health, audit.
5. FastAPI dependencies, middleware, routers, and app factory.
6. Docker, environment templates, Postman examples, and automated tests.

## 7. Full Code Files

All runnable code is in this repository. The main entry points are:
- [`app/main.py`](app/main.py)
- [`app/core/config.py`](app/core/config.py)
- [`app/core/container.py`](app/core/container.py)
- [`app/services/attendance.py`](app/services/attendance.py)
- [`app/services/enrollment.py`](app/services/enrollment.py)
- [`app/services/face_engine/insightface_engine.py`](app/services/face_engine/insightface_engine.py)
- [`app/db/migrations.py`](app/db/migrations.py)

## 8. Setup Instructions

### Local
```powershell
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

### Docker
```bash
docker compose up --build
```

### Production notes
- Replace `JWT_SECRET_KEY`.
- Set `FACE_ENGINE_PROVIDER=insightface`.
- Use managed MongoDB and Redis.
- Provision TLS and reverse proxy in front of the API.

## 9. Test Instructions

```bash
pytest app/tests -q
```

The included test suite covers:
- embedding serialization
- barcode parsing
- cosine matching
- health endpoint contract
- attendance recognition endpoint contract

## 10. Deployment Instructions

1. Build the container image.
2. Supply production secrets through environment variables or a secret manager.
3. Run MongoDB migrations automatically at startup through `app/db/migrations.py`.
4. Scale the API horizontally behind a reverse proxy.
5. Back the rate limiter with Redis for multi-instance consistency.
6. Point enrollment and recognition traffic to GPU-backed or CPU-sized nodes depending on the selected face engine provider.

## 11. Future Commercial Upgrade Recommendations

- Move attendance uniqueness from `daily` to timetable-aware session windows.
- Add a `devices` collection with mutual authentication for fixed attendance terminals.
- Add real anti-spoofing and challenge-response liveness.
- Replace application-side linear scan with vector search or ANN indexing for very large campuses.
- Add campus-specific timezone and timetable policies.
- Add S3-compatible object storage for optional raw evidence image retention with data-retention controls.
- Add background workers for model refresh, embedding reindex, and audit export.
- Add tenant isolation at auth, configuration, and reporting layers for SaaS operation.

## MongoDB Migration Strategy

MongoDB does not use Alembic-style schema migrations. This project uses an idempotent migration registry:
- migration names are stored in `schema_migrations`
- each migration is an async function in `app/db/migrations.py`
- startup applies any migration not yet recorded

This is sufficient for index creation and controlled data backfills. For larger production changes, add forward-only migration scripts and run them in CI/CD before traffic cutover.
