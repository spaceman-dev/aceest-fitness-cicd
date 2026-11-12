#!/usr/bin/env bash
# Shared helpers for the deploy-*.sh and rollback.sh scripts.
#
# Deploy scripts expect:
#   IMAGE        image to roll out, e.g. 192.168.89.10:5000/aceest-fitness:3.2.4-1a2b3c4
#   APP_VERSION  version that image reports on /api/health
#   TEST_IMAGE   test-stage image built from the same commit (holds tests/smoke)
# Optional:
#   INGRESS         ingress controller URL as seen from here (default http://192.168.89.2)
#   DOCKER_NETWORK  network the smoke-test container joins   (default aceest-net)
#   FAULT           unhealthy | errors - injected into the new pods for rollback drills
#   BUILD_LABEL     recorded as the rollout's change-cause
set -euo pipefail

INGRESS=${INGRESS:-http://192.168.89.2}
DOCKER_NETWORK=${DOCKER_NETWORK:-aceest-net}
ROLLOUT_TIMEOUT=${ROLLOUT_TIMEOUT:-150s}
REPORT_DIR=${REPORT_DIR:-reports}
K8S_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../k8s" && pwd)"

export FAULT=${FAULT:-}

log()  { printf '[%s] %s\n' "${STRATEGY:-deploy}" "$*"; }
fail() { log "FAILED: $*"; exit 1; }

require_release() {
  : "${IMAGE:?IMAGE is required}"
  : "${APP_VERSION:?APP_VERSION is required}"
  : "${TEST_IMAGE:?TEST_IMAGE is required}"
  export IMAGE APP_VERSION
  export VERSION="${IMAGE##*:}"
  export CHANGE_CAUSE="${BUILD_LABEL:-manual}: ${IMAGE##*/}${FAULT:+ (fault: $FAULT)}"
}

kc() { kubectl -n "$NAMESPACE" "$@"; }

# Fill in only our own placeholders, so nginx variables such as $request_uri survive.
render() {
  envsubst '${IMAGE} ${VERSION} ${CHANGE_CAUSE} ${FAULT} ${SLOT} ${ACTIVE_SLOT} ${PREVIEW_SLOT} ${TRACK} ${REPLICAS} ${WEIGHT} ${VARIANT}' < "$1"
}

apply_template() { render "$1" | kc apply -f -; }

rollout_ok() { kc rollout status "deployment/$1" --timeout="$ROLLOUT_TIMEOUT"; }

# "rollout status" returns while replaced pods are still terminating, and they
# keep answering through their preStop pause. Wait for them to be gone before
# testing, or a check can land on the old version.
#   old_pods_gone <label selector>      e.g. old_pods_gone app=aceest,track=stable
old_pods_gone() {
  kc wait --for=delete pod -l "$1,version!=$VERSION" --timeout=90s >/dev/null 2>&1 || true
}

deployment_exists() { kc get deployment "$1" >/dev/null 2>&1; }

current_image() {
  kc get deployment "$1" -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true
}

# ReplicaSet behind the deployment's current revision
current_rs() {   # current_rs <deployment>
  local revision
  revision=$(kc get deployment "$1" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
  kc get rs -o jsonpath='{range .items[*]}{.metadata.ownerReferences[0].name}|{.metadata.annotations.deployment\.kubernetes\.io/revision}|{.metadata.name}{"\n"}{end}' |
    awk -F'|' -v d="$1" -v r="$revision" '$1 == d && $2 == r {print $3}'
}

# Pytest smoke suite from the test image, run in a container against the ingress.
#   smoke <host> [header]     e.g. smoke canary.aceest.localhost "X-Canary: always"
smoke() {
  local host=$1 header=${2:-}
  log "smoke tests on $host${header:+ ($header)} expecting $APP_VERSION"
  docker run --rm --network "$DOCKER_NETWORK" \
    -e ACEEST_BASE_URL="$INGRESS" \
    -e ACEEST_HOST="$host" \
    -e ACEEST_EXPECT_VERSION="$APP_VERSION" \
    -e ACEEST_EXTRA_HEADER="$header" \
    "$TEST_IMAGE" pytest -o addopts="" -q -p no:cacheprovider tests/smoke
}

# One request through the ingress; prints "<status> <track> <version> <seconds>".
#   probe <host> [curl args...]
probe() {
  local host=$1
  shift
  curl -s -o /dev/null -m 5 -H "Host: $host" "$@" \
    -w '%{http_code} %header{x-aceest-track} %header{x-aceest-version} %{time_total}\n' \
    "$INGRESS/api/health" || true
}
