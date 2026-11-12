# Changelog

Versions follow the numbering of the original ACEest desktop builds
(`Aceestver-X.Y.Z.py`); each one is ported to the Flask app and tagged `vX.Y.Z`.

## 3.2.4

- Membership plans (Monthly 30 days / Rs 2500, Quarterly 90 / Rs 6500,
  Annual 365 / Rs 24000) paid by Cash, Card or UPI. A renewal starts the day
  after the current end date, or today if the membership has already
  lapsed, so renewing early keeps the remaining days.
- Payment history per client; payment and new end date are saved together.
- Dashboard list of memberships ending in the next 14 days, also at
  `GET /api/memberships/expiring`.
- Program templates from the desktop build (e.g. "Full Body HIIT" or
  "Circuit Training" for the fat-loss programs); one can be assigned per
  client.
- Canary releases sample 100 requests per step instead of 50.

## 3.1.2

- Staff sign-in with Admin and Coach roles; Admins manage accounts at
  `/users` and `POST /api/users`. No default password: the first Admin is
  created from `ACEEST_ADMIN_PASSWORD`.
- Client pages need a session; `/api/clients/*` needs a session or HTTP
  Basic credentials (401 otherwise). Health, programs, calculators, stats
  and metrics stay public.
- Membership end date with Active / Expiring soon / Expired status.
- Weekly program generator (beginner 3 days, intermediate 4, advanced 5),
  stable for a client within a week: `GET /api/clients/<name>/program`.
- PDF client report: `/clients/<name>/report.pdf`.

## 3.0.1

The desktop 3.0.1 build is the same code as 2.2.4. The web app uses the
major version for the platform changes needed to run it as many replicas.

- `GET /metrics` in Prometheus format: requests by route and status,
  latency, and a build-info gauge with version and track.
- `GET /api/stats`: clients by program, average calorie target, capacity
  used; the dashboard shows the same figures as overview cards.
- `/api/health` checks the database and returns 503 when it is unreachable.
- `ACEEST_FAULT=unhealthy|errors` for rollback drills (off by default).
- **Breaking:** `POST /api/profile` and `GET /api/site` are removed; use
  `POST /api/clients` and `GET /api/stats`.

## 2.2.4

- Four programs: Fat Loss 3-day (FL3, 22 kcal/kg), Fat Loss 5-day (FL5, 24),
  Muscle Gain PPL (MG, 35), Beginner (BG, 26). `FL` still resolves to FL3.
- Height, BMI band and risk note; target weight and target adherence.
- Workout logging with exercises (sets, reps, weight) and workout history.
- Body metrics (weight, waist, bodyfat) with a weight-trend chart.
- Client summary block as in the desktop build: program notes, goals,
  progress summary and last body metrics.
- Migration 3 is additive (and maps FL -> FL3), so data is carried over.

## 2.2.1

- Weekly adherence line chart on the client page, drawn server-side as SVG
  (`GET /api/clients/<name>/progress/chart.svg`).

## 2.1.2

The desktop 2.1.2 build is the same code as 2.0.1; on the web side this
release fixes what came up after 2.0.1 went live.

- Fixed: logging the same week twice created a second entry. Saving a week
  now replaces it; migration 2 keeps the latest of existing duplicates and
  adds a unique index on (client, week).
- Fixed: weekly progress came back in the order it was typed, not by week.
- SQLite runs in WAL mode so replicas sharing the file read while one writes.
- Pipeline: canary traffic is measured only after the new weight is live.

## 2.0.1

- Clients and weekly progress are stored in SQLite instead of process
  memory, so they survive restarts and every replica sees the same data.
- Numbered schema migrations (`schema_version`), applied at start-up under a
  single write lock so replicas starting together don't race.
- Client page ("Load Client") with the profile summary and weekly progress;
  `GET/PUT /api/clients/<name>`, `GET/POST /api/clients/<name>/progress`.
- "Save Client" on the dashboard creates or updates, like the desktop build.
- Runtime image keeps the database on the `/data` volume.
- Pipeline: smoke tests wait for the replaced pods to be gone first.

## 1.1.2

- Client roster: saved clients are listed on the dashboard with their coach
  notes, plus an adherence bar chart per client.
- CSV export (`/api/clients/export.csv`) with the desktop build's columns;
  formula-like text is quoted so spreadsheets don't execute it.
- `GET/POST /api/clients`.
- Fixed: a second client with the same name was silently added (now 409).
- Pipeline: each build uses its own test image tag.

## 1.1.0

- Client profile form (name, age, weight, program, weekly adherence) with the
  daily calorie estimate: weight x program factor (FL 22, MG 35, BG 26).
- Workout and nutrition plans updated to the 1.1 desktop build.
- `POST /api/calories` and `POST /api/profile` with field-level validation errors.
- CSRF protection on the dashboard form.
- Kubernetes delivery: rolling, blue-green, canary, A/B and shadow lanes with
  automatic rollback, plus a manual rollback job.

## 1.0.0

- Program catalogue: Fat Loss, Muscle Gain and Beginner plans with their weekly
  workout chart and Tamil Nadu nutrition plan.
- Dashboard with program selector and the site reference figures
  (150 users, 10,000 sq ft, 250 members break-even).
- JSON API: `/api/health`, `/api/programs`, `/api/programs/<code>`, `/api/site`.
- Release headers on every response (`X-ACEest-Version`, `X-ACEest-Track`).
- Multi-stage Dockerfile, Jenkins pipeline, SonarQube project settings.
