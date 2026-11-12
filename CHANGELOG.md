# Changelog

Versions follow the numbering of the original ACEest desktop builds
(`Aceestver-X.Y.Z.py`); each one is ported to the Flask app and tagged `vX.Y.Z`.

## 1.0.0

- Program catalogue: Fat Loss, Muscle Gain and Beginner plans with their weekly
  workout chart and Tamil Nadu nutrition plan.
- Dashboard with program selector and the site reference figures
  (150 users, 10,000 sq ft, 250 members break-even).
- JSON API: `/api/health`, `/api/programs`, `/api/programs/<code>`, `/api/site`.
- Release headers on every response (`X-ACEest-Version`, `X-ACEest-Track`).
- Multi-stage Dockerfile, Jenkins pipeline, SonarQube project settings.
