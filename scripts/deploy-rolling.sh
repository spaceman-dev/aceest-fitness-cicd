#!/usr/bin/env bash
# Rolling update. Kubernetes swaps pods one by one; if the rollout stalls
# (pods never get ready) or the new version fails its smoke tests, the
# deployment is undone to the previous revision.
STRATEGY=rolling-update
NAMESPACE=aceest-rolling
HOST=rolling.aceest.localhost
source "$(dirname "$0")/lib.sh"
require_release

previous=$(current_image aceest)
log "current: ${previous:-<none>} -> new: $IMAGE"

kc apply -f "$K8S_DIR/rolling/services.yaml"
apply_template "$K8S_DIR/rolling/deployment.yaml"

if ! rollout_ok aceest || ! smoke "$HOST"; then
  if [ -n "$previous" ]; then
    log "rolling back to the previous revision ($previous)"
    kc rollout undo deployment/aceest
    rollout_ok aceest
    probe "$HOST"
  fi
  fail "$APP_VERSION was not released"
fi

kc rollout history deployment/aceest | tail -n 5
log "done: $APP_VERSION is live on http://$HOST"
