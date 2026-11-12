#!/usr/bin/env bash
# Manual rollback for one release lane.
#
#   scripts/rollback.sh <strategy> [image]
#
#   rolling     undo to the previous revision, or set the given image
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

case "$STRATEGY" in
  rolling)
    NAMESPACE=aceest-rolling
    if [ -n "$TARGET" ]; then set_image aceest; else kc rollout undo deployment/aceest; rollout_ok aceest; fi
    host=rolling.aceest.localhost
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
    host=bluegreen.aceest.localhost
    ;;
  canary)
    NAMESPACE=aceest-canary
    export WEIGHT=0
    apply_template "$K8S_DIR/canary/ingress-canary.yaml"
    kc scale deployment/aceest-canary --replicas=0
    [ -z "$TARGET" ] || set_image aceest-stable
    host=canary.aceest.localhost
    ;;
  ab-testing)
    NAMESPACE=aceest-ab
    kc delete -f "$K8S_DIR/ab-testing/ingress-variant-b.yaml" --ignore-not-found
    host=ab.aceest.localhost
    ;;
  shadow)
    NAMESPACE=aceest-shadow
    kc scale deployment/aceest-shadow --replicas=0
    [ -z "$TARGET" ] || set_image aceest-live
    host=shadow.aceest.localhost
    ;;
  *)
    fail "unknown strategy '$STRATEGY'"
    ;;
esac

sleep 2
log "now serving: $(probe "$host")"
