#!/usr/bin/env bash
# Starts Jenkins + SonarQube. Secrets are copied from $SECRETS_DIR into a
# docker volume owned by the jenkins user (uid 1000), so the host files can
# stay 0600 and never end up inside the image or the repository.
#
# Expected files in $SECRETS_DIR:
#   JENKINS_ADMIN_PASSWORD  SONAR_TOKEN  kubeconfig
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SECRETS_DIR=${SECRETS_DIR:-$HOME/.aceest-ci/secrets}

for f in JENKINS_ADMIN_PASSWORD SONAR_TOKEN kubeconfig; do
  [ -s "$SECRETS_DIR/$f" ] || { echo "missing $SECRETS_DIR/$f" >&2; exit 1; }
done

docker volume create aceest-ci_jenkins_secrets >/dev/null
docker run --rm \
  -v aceest-ci_jenkins_secrets:/target \
  -v "$SECRETS_DIR":/source:ro \
  alpine:3.20 sh -c 'cp /source/JENKINS_ADMIN_PASSWORD /source/SONAR_TOKEN /source/kubeconfig /target/ \
    && chown -R 1000:1000 /target && chmod 0400 /target/*'

docker compose -f "$HERE/docker-compose.yml" up -d --build "$@"
echo "Jenkins   http://localhost:8090"
echo "SonarQube http://localhost:9001"
