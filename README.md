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
| GET | `/api/programs/<code>` | one program (`FL`, `MG`, `BG`) |
| GET | `/api/site` | capacity / area / break-even figures |

Every response carries `X-ACEest-Version` and `X-ACEest-Track` headers so it is
always clear which build answered.

## Versioning

Semantic versions (`MAJOR.MINOR.PATCH`) live in `aceest/__init__.py`. Each
release is an annotated git tag `vX.Y.Z` and an image tag `X.Y.Z`; see
[CHANGELOG.md](CHANGELOG.md).
