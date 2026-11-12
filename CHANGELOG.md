# Changelog

Versions follow the numbering of the original ACEest desktop builds
(`Aceestver-X.Y.Z.py`); each one is ported to the Flask app and tagged `vX.Y.Z`.

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
