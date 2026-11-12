#!/usr/bin/env bash
# Canary release. One canary pod gets a growing share of real traffic
# (CANARY_STEPS, percent). At every step the pipeline samples requests, counts
# who served them and checks for errors/restarts. Any problem sends the weight
# back to 0 - the stable track never stopped serving. When every step passes
# the stable track is upgraded and the canary is retired.
STRATEGY=canary
NAMESPACE=aceest-canary
HOST=canary.aceest.localhost
CANARY_STEPS=${CANARY_STEPS:-"10 30 60"}
CANARY_SAMPLES=${CANARY_SAMPLES:-100}
source "$(dirname "$0")/lib.sh"
require_release

kc apply -f "$K8S_DIR/canary/services.yaml"

if ! deployment_exists aceest-stable; then
  log "first release: $APP_VERSION goes straight to the stable track"
  export TRACK=stable REPLICAS=3
  apply_template "$K8S_DIR/canary/deployment.yaml"
  rollout_ok aceest-stable || fail "stable track never became ready"
  old_pods_gone app=aceest,track=stable
  export WEIGHT=0
  apply_template "$K8S_DIR/canary/ingress-canary.yaml"
  smoke "$HOST" || fail "$APP_VERSION failed its smoke tests"
  log "done: stable track running $APP_VERSION"
  exit 0
fi

stable_image=$(current_image aceest-stable)

abort() {
  log "aborting: $*"
  export WEIGHT=0
  apply_template "$K8S_DIR/canary/ingress-canary.yaml"
  kc scale deployment/aceest-canary --replicas=0 || true
  probe "$HOST"
  fail "$* - 100% of traffic is back on the stable track ($stable_image)"
}

log "stable: $stable_image, canary: $IMAGE"
export TRACK=canary REPLICAS=1
apply_template "$K8S_DIR/canary/deployment.yaml"
rollout_ok aceest-canary || abort "canary pod never became ready"
old_pods_gone app=aceest,track=canary

export WEIGHT=0
apply_template "$K8S_DIR/canary/ingress-canary.yaml"
smoke "$HOST" "X-Canary: always" || abort "canary failed its smoke tests"

for weight in $CANARY_STEPS; do
  export WEIGHT=$weight
  apply_template "$K8S_DIR/canary/ingress-canary.yaml"
  # ingress-nginx applies weight changes on its next sync, which is rate
  # limited and shared with every other ingress being changed at the same
  # time - give it a moment, then make sure the canary is really in rotation
  # before measuring anything.
  sleep 5
  for _ in $(seq 1 40); do
    read -r _ track _ _ < <(probe "$HOST") || true
    [ "$track" = canary ] && break
    sleep 0.5
  done
  served=0
  errors=0
  for _ in $(seq 1 "$CANARY_SAMPLES"); do
    read -r code track _ _ < <(probe "$HOST") || true
    [ "$code" = 200 ] || errors=$((errors + 1))
    [ "$track" = canary ] && served=$((served + 1))
  done
  restarts=$(kc get pods -l track=canary \
    -o jsonpath='{range .items[*]}{.status.containerStatuses[0].restartCount}{"\n"}{end}' \
    | awk '{n += $1} END {print n + 0}')
  log "weight ${weight}%: canary served $served/$CANARY_SAMPLES requests ($((served * 100 / CANARY_SAMPLES))%), errors=$errors, restarts=$restarts"
  [ "$errors" -eq 0 ] || abort "errors at ${weight}% traffic"
  [ "$restarts" -eq 0 ] || abort "canary pod restarted"
done

log "canary looks good - promoting $APP_VERSION to the stable track"
export TRACK=stable REPLICAS=3
apply_template "$K8S_DIR/canary/deployment.yaml"
if ! rollout_ok aceest-stable; then
  kc rollout undo deployment/aceest-stable
  abort "stable track failed to roll forward"
fi
old_pods_gone app=aceest,track=stable

export WEIGHT=0
apply_template "$K8S_DIR/canary/ingress-canary.yaml"
kc scale deployment/aceest-canary --replicas=0
smoke "$HOST" || fail "stable track failed its smoke tests after promotion"
log "done: stable track running $APP_VERSION, canary retired"
