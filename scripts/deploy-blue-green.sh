#!/usr/bin/env bash
# Blue-green. The new version goes to the idle slot and is tested through the
# preview host while the live slot keeps serving everyone. Only then does the
# live Service selector move to it - one atomic switch. If the live check
# fails after the switch, the selector goes straight back.
STRATEGY=blue-green
NAMESPACE=aceest-bluegreen
HOST=bluegreen.aceest.localhost
PREVIEW_HOST=preview.bluegreen.aceest.localhost
source "$(dirname "$0")/lib.sh"
require_release

live=$(kc get service aceest -o jsonpath='{.spec.selector.slot}' 2>/dev/null || true)
if [ "$live" = blue ]; then idle=green; else idle=blue; fi
log "live slot: ${live:-<none>} -> deploying $APP_VERSION to the $idle slot"

kc apply -f "$K8S_DIR/blue-green/ingress.yaml"
export SLOT=$idle
apply_template "$K8S_DIR/blue-green/deployment.yaml"
if ! rollout_ok "aceest-$idle"; then
  fail "the $idle slot never became ready; live traffic is still on ${live:-nothing}"
fi
old_pods_gone "app=aceest,slot=$idle"

# preview -> idle slot; live keeps its current slot (on a first release both point at it)
export ACTIVE_SLOT=${live:-$idle} PREVIEW_SLOT=$idle
apply_template "$K8S_DIR/blue-green/services.yaml"
if ! smoke "$PREVIEW_HOST"; then
  fail "$APP_VERSION failed on the preview slot; live traffic is still on ${live:-nothing}"
fi

log "switching live traffic: ${live:-<none>} -> $idle"
export ACTIVE_SLOT=$idle PREVIEW_SLOT=${live:-$idle}
apply_template "$K8S_DIR/blue-green/services.yaml"

if ! smoke "$HOST"; then
  if [ -n "$live" ]; then
    log "switching back to $live"
    export ACTIVE_SLOT=$live PREVIEW_SLOT=$idle
    apply_template "$K8S_DIR/blue-green/services.yaml"
    probe "$HOST"
  fi
  fail "$APP_VERSION failed after the switch; traffic is back on ${live:-nothing}"
fi

kc get deployments -l app=aceest -o custom-columns='SLOT:.metadata.labels.slot,IMAGE:.spec.template.spec.containers[0].image,READY:.status.readyReplicas'
log "done: $idle is live with $APP_VERSION; ${live:-no} standby slot kept for instant rollback"
