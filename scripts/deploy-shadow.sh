#!/usr/bin/env bash
# Shadow deployment. The new version runs as "aceest-shadow" and receives a
# mirrored copy of every request that reaches live; nginx discards its
# answers, so users only ever see the live version. The pipeline sends
# tagged traffic to live, then reads the shadow's access log to confirm it
# handled the same requests without server errors. Only then is the live
# deployment upgraded (rolling, with undo on failure).
STRATEGY=shadow
NAMESPACE=aceest-shadow
HOST=shadow.aceest.localhost
SHADOW_SAMPLES=${SHADOW_SAMPLES:-25}
source "$(dirname "$0")/lib.sh"
require_release

kc apply -f "$K8S_DIR/shadow/services.yaml"

if ! deployment_exists aceest-live; then
  log "first release: $APP_VERSION becomes the live version"
  apply_template "$K8S_DIR/shadow/deployment-live.yaml"
  rollout_ok aceest-live || fail "live deployment never became ready"
fi
live_image=$(current_image aceest-live)
log "live: $live_image, shadow: $IMAGE"

apply_template "$K8S_DIR/shadow/deployment-shadow.yaml"
if ! rollout_ok aceest-shadow; then
  kc scale deployment/aceest-shadow --replicas=0
  fail "shadow never became ready (users were not affected)"
fi
old_pods_gone app=aceest,role=shadow
sleep 3

marker="mirror-check-${BUILD_LABEL:-manual}-$$"
marker=${marker//[^A-Za-z0-9-]/-}
live_errors=0
for i in $(seq 1 "$SHADOW_SAMPLES"); do
  code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' -H "Host: $HOST" "$INGRESS/api/programs?probe=$marker-$i" || true)
  [ "$code" = 200 ] || live_errors=$((live_errors + 1))
done
sleep 3

# gunicorn access log: ... "GET /api/programs?probe=<marker>-n HTTP/1.1" <status> ...
mirrored=$(kc logs deployment/aceest-shadow --since=10m | grep -c "probe=$marker-" || true)
shadow_5xx=$(kc logs deployment/aceest-shadow --since=10m | grep "probe=$marker-" | awk '$9 >= 500' | wc -l | tr -d ' ')
log "live answered $((SHADOW_SAMPLES - live_errors))/$SHADOW_SAMPLES; shadow received $mirrored mirrored copies, $shadow_5xx server errors"

if [ "$live_errors" -ne 0 ]; then
  fail "live returned errors during the check - investigate before releasing"
fi
if [ "$mirrored" -lt $((SHADOW_SAMPLES * 9 / 10)) ] || [ "$shadow_5xx" -ne 0 ]; then
  kc scale deployment/aceest-shadow --replicas=0
  fail "$APP_VERSION misbehaved in shadow; users were never exposed to it"
fi

if [ "$live_image" != "$IMAGE" ]; then
  log "shadow run clean - promoting $APP_VERSION to live"
  apply_template "$K8S_DIR/shadow/deployment-live.yaml"
  if ! rollout_ok aceest-live || ! old_pods_gone app=aceest,role=live || ! smoke "$HOST"; then
    kc rollout undo deployment/aceest-live
    rollout_ok aceest-live
    fail "promotion failed; live rolled back to $live_image"
  fi
else
  smoke "$HOST" || fail "live failed its smoke tests"
fi
log "done: live and shadow both on $APP_VERSION; the next release will shadow behind it"
