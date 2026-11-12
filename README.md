# ACEest Fitness & Gym

Flask web application for ACEest Fitness & Gym, delivered through a Jenkins
CI/CD pipeline. This is the Assignment 2 continuation of
[aceest-fitness-devops](https://github.com/spaceman-dev/aceest-fitness-devops):
same code base, now rebuilt release by release from the original desktop
versions and shipped with Docker, SonarQube and Kubernetes.

## Run it locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

FLASK_ENV=development python ACEest_Fitness.py     # http://127.0.0.1:5000
pytest                                             # tests + coverage gate (90%)
flake8 .
```

## Container

```bash
docker build -t aceest-fitness .                   # runtime image
docker build --target test -t aceest-fitness-test . && docker run --rm aceest-fitness-test
docker run -p 5000:5000 aceest-fitness
```

## API

| Method | Path | |
| --- | --- | --- |
| GET | `/api/health` | status, version and deployment track |
| GET | `/api/programs` | program catalogue |
| GET | `/api/programs/<code>` | one program (`FL3`, `FL5`, `MG`, `BG`) |
| GET | `/api/stats` | clients by program, average calories, capacity used |
| GET | `/metrics` | Prometheus metrics for the pod |
| POST | `/api/calories` | `{"weight_kg", "program"}` -> daily calorie estimate |
| POST | `/api/bmi` | `{"weight_kg", "height_cm"}` -> BMI, band and risk note |
| GET, POST | `/api/clients` | client roster; POST adds one (409 on a duplicate name) |
| GET | `/api/clients/export.csv` | roster as CSV |
| GET, PUT | `/api/clients/<name>` | one client with progress; PUT updates and recomputes |
| GET, POST | `/api/clients/<name>/progress` | weekly adherence (`{"week": "2026-W46", "adherence": 80}`) |
| GET | `/api/clients/<name>/progress/chart.svg` | adherence chart |
| GET, POST | `/api/clients/<name>/workouts` | sessions with exercises |
| GET, POST | `/api/clients/<name>/metrics` | weight / waist / bodyfat entries |
| GET | `/api/clients/<name>/metrics/chart.svg` | weight trend chart |
| GET | `/api/clients/<name>/program?experience=beginner` | weekly program |
| GET | `/api/clients/<name>/report.pdf` | PDF client report |
| GET | `/api/membership/plans` | membership plans and payment methods |
| GET | `/api/clients/<name>/membership` | end date, status and payment history |
| POST | `/api/clients/<name>/membership/renew` | `{"plan": "quarterly", "method": "UPI"}` -> payment + new end date |
| GET | `/api/memberships/expiring` | memberships ending in the next 14 days |
| PUT | `/api/clients/<name>/template` | `{"template": "Full Body HIIT"}` -> assign a program template |
| GET, POST | `/api/users` | staff accounts (Admin only) |

Everything under `/api/clients`, `/api/memberships` and `/api/users` needs a
signed-in session or HTTP Basic credentials, e.g.
`curl -u admin:<password> .../api/clients`.

Every response carries `X-ACEest-Version` and `X-ACEest-Track` headers so it is
always clear which build answered.

## Pipeline

Jenkins runs a multibranch job that polls GitHub every two minutes:

```
Checkout -> Install -> Lint -> Unit Tests -> SonarQube Analysis* -> Quality Gate*
  -> Build Image -> Test in Container -> Package -> Publish Image** -> Deploy to Kubernetes*
```

`*` main only, `**` main and release tags. Feature branches stop after Package.
Every build archives a wheel, a source tarball and `release.json`; tag builds
push the release image `X.Y.Z`, main builds push `X.Y.Z-<commit>` and roll it out.

## Release strategies

Each strategy has its own namespace on a local minikube cluster and its own
URL through the ingress (port 8088 on the host):

| Strategy | URL | Release | Rollback |
| --- | --- | --- | --- |
| Rolling update | http://rolling.aceest.localhost:8088 | pods replaced one at a time, never below 3 ready | `kubectl rollout undo` |
| Blue-green | http://bluegreen.aceest.localhost:8088 | idle slot tested on `preview.bluegreen...`, then the live Service selector flips | flip the selector back |
| Canary | http://canary.aceest.localhost:8088 | 10% -> 30% -> 60% of requests, checked at every step, then promoted | weight back to 0 |
| A/B testing | http://ab.aceest.localhost:8088 | variant B only for `X-Variant: B` or cookie `ab_variant_b=always` | remove B's route |
| Shadow | http://shadow.aceest.localhost:8088 | new version receives a mirrored copy of live traffic first | stop the shadow |

`http://aceest.localhost:8088` follows the blue-green live slot and is the main
entry point. The scripts in `scripts/` do the work and revert automatically
when a rollout or its smoke tests fail; the `ACEest Rollback` Jenkins job
(`Jenkinsfile.rollback`) is the manual route back. A rollback drill is one
click: run main with `FAULT_INJECTION=unhealthy` or `errors`.

## Local toolchain

```bash
infra/cluster/bootstrap.sh   # registry, minikube profile, namespaces, RBAC, Jenkins kubeconfig
infra/up.sh                  # Jenkins on :8090, SonarQube on :9001
```

Secrets (Jenkins admin password, SonarQube token, kubeconfig) are read from
`~/.aceest-ci/secrets`; nothing sensitive is committed.

Images go to the local registry `192.168.89.10:5000/aceest-fitness`
(`localhost:5005` from the host). To publish to Docker Hub instead, put an
access token in `~/.aceest-ci/secrets/REGISTRY_PASSWORD` and restart Jenkins
with

```bash
REGISTRY_USER=<user> ACEEST_IMAGE_REPO=<user>/aceest-fitness \
ACEEST_REGISTRY_CREDENTIALS=registry infra/up.sh
```

Tags already in the local registry can be copied across with
`docker login && scripts/mirror-images.sh <user>/aceest-fitness`.

## Versioning

Semantic versions (`MAJOR.MINOR.PATCH`) live in `aceest/__init__.py`. Each
release is an annotated git tag `vX.Y.Z` and an image tag `X.Y.Z`; see
[CHANGELOG.md](CHANGELOG.md).
