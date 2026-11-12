#!/usr/bin/env bash
# A/B testing. Variant A keeps the current version, variant B gets the new one,
# and the ingress routes by user segment (X-Variant: B header or the
# ab_variant_b cookie). The pipeline then runs a short experiment - requests
# from both segments - and writes per-variant results to
# reports/ab-test.json. A failing variant B is taken out of the experiment
# by deleting its route; segment A users never notice.
STRATEGY=ab-testing
NAMESPACE=aceest-ab
HOST=ab.aceest.localhost
AB_SAMPLES=${AB_SAMPLES:-30}
source "$(dirname "$0")/lib.sh"
require_release

kc apply -f "$K8S_DIR/ab-testing/services.yaml"

# Last experiment's B becomes the new baseline A; on a first release both match.
current_b=$(current_image aceest-b)
if [ -z "$current_b" ]; then
  baseline=$IMAGE
elif [ "$current_b" = "$IMAGE" ]; then
  baseline=$(current_image aceest-a)
else
  baseline=$current_b
fi
log "variant A: $baseline"
log "variant B: $IMAGE"

(
  export IMAGE=$baseline VERSION=${baseline##*:} VARIANT=a
  apply_template "$K8S_DIR/ab-testing/deployment.yaml"
)
rollout_ok aceest-a || fail "variant A never became ready"

export VARIANT=b
apply_template "$K8S_DIR/ab-testing/deployment.yaml"
if ! rollout_ok aceest-b; then
  kc delete -f "$K8S_DIR/ab-testing/ingress-variant-b.yaml" --ignore-not-found
  fail "variant B never became ready; everyone stays on variant A"
fi

kc apply -f "$K8S_DIR/ab-testing/ingress-variant-b.yaml"
if ! smoke "$HOST" "X-Variant: B"; then
  kc delete -f "$K8S_DIR/ab-testing/ingress-variant-b.yaml" --ignore-not-found
  fail "variant B failed its smoke tests; route removed, everyone is on variant A"
fi
sleep 2

# The experiment: plain users, header users and cookie users.
run_segment() {   # run_segment <name> [curl args...]
  local name=$1
  shift
  local total=0 errors=0 on_a=0 on_b=0 seconds=0
  for _ in $(seq 1 "$AB_SAMPLES"); do
    read -r code track _ took < <(probe "$HOST" "$@") || true
    total=$((total + 1))
    [ "$code" = 200 ] || errors=$((errors + 1))
    case $track in
      variant-a) on_a=$((on_a + 1)) ;;
      variant-b) on_b=$((on_b + 1)) ;;
    esac
    seconds=$(awk -v a="$seconds" -v b="${took:-0}" 'BEGIN {print a + b}')
  done
  local avg_ms
  avg_ms=$(awk -v s="$seconds" -v n="$total" 'BEGIN {printf "%.1f", s * 1000 / n}')
  log "segment $name: $total requests -> A=$on_a B=$on_b errors=$errors avg=${avg_ms}ms"
  printf '"%s": {"requests": %d, "served_by_a": %d, "served_by_b": %d, "errors": %d, "avg_ms": %s}\n' \
    "$name" "$total" "$on_a" "$on_b" "$errors" "$avg_ms"
}

mkdir -p "$REPORT_DIR"
seg_default=$(run_segment default | tee /dev/stderr | tail -n 1)
seg_header=$(run_segment header_B -H "X-Variant: B" | tee /dev/stderr | tail -n 1)
seg_cookie=$(run_segment cookie_B -b "ab_variant_b=always" | tee /dev/stderr | tail -n 1)
cat > "$REPORT_DIR/ab-test.json" <<EOF
{"variant_a": "$baseline", "variant_b": "$IMAGE",
 $seg_default,
 $seg_header,
 $seg_cookie}
EOF

if ! python3 - "$REPORT_DIR/ab-test.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
assert r["default"]["served_by_a"] == r["default"]["requests"], "segment A leaked onto B"
for seg in ("header_B", "cookie_B"):
    assert r[seg]["served_by_b"] == r[seg]["requests"], f"{seg} was not routed to B"
for seg in ("default", "header_B", "cookie_B"):
    assert r[seg]["errors"] == 0, f"errors in {seg}"
print("A/B routing verified:", json.dumps(r))
PY
then
  kc delete -f "$K8S_DIR/ab-testing/ingress-variant-b.yaml" --ignore-not-found
  fail "experiment checks failed; variant B route removed, everyone is on variant A"
fi
log "done: experiment running - A on $baseline, B on $IMAGE"
