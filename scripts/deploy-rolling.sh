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

if ! rollout_ok aceest || ! old_pods_gone app=aceest || ! smoke "$HOST"; then
  if [ -n "$previous" ]; then
    # mark the failed revision so a later manual rollback never picks it
    for rs in $(current_rs aceest); do
      kc annotate rs "$rs" aceest/failed="${BUILD_LABEL:-manual}" --overwrite >/dev/null || true
    done
    log "rolling back to the previous revision ($previous)"
    kc rollout undo deployment/aceest
    rollout_ok aceest
    probe "$HOST"
  fi
  fail "$APP_VERSION was not released"
fi

# a re-released template reuses its old ReplicaSet; drop any earlier failure mark
for rs in $(current_rs aceest); do
  kc annotate rs "$rs" aceest/failed- >/dev/null 2>&1 || true
done
kc rollout history deployment/aceest | tail -n 5
log "done: $APP_VERSION is live on http://$HOST"
