#!/usr/bin/env bash
# Manual rollback for one release lane.
#
#   scripts/rollback.sh <strategy> [image]
#
#   rolling     back to the last stable revision, or to the given image
#   blue-green  move live traffic back to the standby slot
#   canary      weight 0 + retire the canary; with an image, also reset stable
#   ab-testing  end the experiment: remove variant B's route
#   shadow      stop the shadow; with an image, also reset live
set -euo pipefail
STRATEGY=${1:?usage: rollback.sh <rolling|blue-green|canary|ab-testing|shadow> [image]}
TARGET=${2:-}
source "$(dirname "$0")/lib.sh"

set_image() {   # set_image <deployment>
  kc set image "deployment/$1" "web=$TARGET"
  kc annotate "deployment/$1" kubernetes.io/change-cause="rollback to ${TARGET##*/}" --overwrite
  rollout_ok "$1"
}

answers() {     # answers <host> <path>: HTTP 200 within a few tries
  for _ in 1 2 3 4 5; do
    [ "$(curl -s -o /dev/null -m 5 -w '%{http_code}' -H "Host: $1" "$INGRESS$2" || true)" = 200 ] && return 0
    sleep 1
  done
  return 1
}

version_of() {  # .../aceest-fitness:3.2.4-926e56a -> 3.2.4
  local tag=${1##*:}
  echo "${tag%%-*}"
}

# "rollout undo" goes to the previous revision, and after an automatic rollback
# that is the build that just failed. Take the newest revision that runs a
# different image, has no drill fault and was not marked failed by a release.
last_stable_revision() {   # last_stable_revision <deployment> -> "<revision> <image>"
  local jp='{range .items[?(@.metadata.ownerReferences[0].name=="DEPLOY")]}{.metadata.annotations.deployment\.kubernetes\.io/revision}|{.spec.template.spec.containers[0].image}|{.spec.template.spec.containers[0].env[?(@.name=="ACEEST_FAULT")].value}|{.metadata.annotations.aceest/failed}{"\n"}{end}'
  kc get rs -o jsonpath="${jp//DEPLOY/$1}" | sort -t'|' -k1,1rn |
    awk -F'|' -v current="$(current_image "$1")" '$2 != current && $3 == "" && $4 == "" {print $1, $2; exit}'
}

# ingress-nginx applies selector and endpoint changes a few seconds later, so
# wait until the host really serves what the rollback asked for.
verify() {      # verify <host> <expected version or track> [curl args...]
  local host=$1 expect=$2 code track version
  shift 2
  for _ in $(seq 1 30); do
    read -r code track version _ < <(probe "$host" "$@") || true
    if [ "$code" = 200 ] && { [ "$expect" = "$version" ] || [ "$expect" = "$track" ]; }; then
      log "now serving: $code $track $version"
      return 0
    fi
    sleep 1
  done
  fail "$host answers '${code:-} ${track:-} ${version:-}', expected $expect"
}

case "$STRATEGY" in
  rolling)
    NAMESPACE=aceest-rolling
    if [ -z "$TARGET" ]; then
      read -r revision TARGET < <(last_stable_revision aceest) || true
      [ -n "$TARGET" ] || fail "no earlier revision with a different, healthy image"
      log "going back to revision $revision (${TARGET##*/})"
      kc rollout undo deployment/aceest --to-revision="$revision"
      kc annotate deployment/aceest kubernetes.io/change-cause="rollback to ${TARGET##*/}" --overwrite
      rollout_ok aceest
    else
      set_image aceest
    fi
    verify rolling.aceest.localhost "$(version_of "$TARGET")"
    ;;
  blue-green)
    NAMESPACE=aceest-bluegreen
    live=$(kc get service aceest -o jsonpath='{.spec.selector.slot}')
    if [ "$live" = blue ]; then standby=green; else standby=blue; fi
    deployment_exists "aceest-$standby" || fail "no standby slot to go back to"
    rollout_ok "aceest-$standby"
    # a ready pod only proves /api/health; check real requests through the preview host first
    export ACTIVE_SLOT=$live PREVIEW_SLOT=$standby
    apply_template "$K8S_DIR/blue-green/services.yaml"
    for path in /api/health /api/programs; do
      answers preview.bluegreen.aceest.localhost "$path" ||
        fail "standby slot $standby does not answer $path - live stays on $live"
    done
    export ACTIVE_SLOT=$standby PREVIEW_SLOT=$live
    apply_template "$K8S_DIR/blue-green/services.yaml"
    log "live traffic moved $live -> $standby ($(current_image "aceest-$standby"))"
    verify bluegreen.aceest.localhost "$standby"
    ;;
  canary)
    NAMESPACE=aceest-canary
    export WEIGHT=0
    apply_template "$K8S_DIR/canary/ingress-canary.yaml"
    kc scale deployment/aceest-canary --replicas=0
    if [ -n "$TARGET" ]; then
      set_image aceest-stable
      verify canary.aceest.localhost "$(version_of "$TARGET")" -H "X-Canary: always"
    else
      verify canary.aceest.localhost stable -H "X-Canary: always"
    fi
    ;;
  ab-testing)
    NAMESPACE=aceest-ab
    kc delete -f "$K8S_DIR/ab-testing/ingress-variant-b.yaml" --ignore-not-found
    kc annotate deployment/aceest-b aceest/experiment=failed --overwrite >/dev/null
    verify ab.aceest.localhost variant-a -H "X-Variant: B"
    ;;
  shadow)
    NAMESPACE=aceest-shadow
    kc scale deployment/aceest-shadow --replicas=0
    if [ -n "$TARGET" ]; then
      set_image aceest-live
      verify shadow.aceest.localhost "$(version_of "$TARGET")"
    else
      verify shadow.aceest.localhost live
    fi
    ;;
  *)
    fail "unknown strategy '$STRATEGY'"
    ;;
esac
