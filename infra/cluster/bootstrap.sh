#!/usr/bin/env bash
# Prepares the local Kubernetes target for the pipeline:
#   - docker network + private registry the cluster pulls from
#   - minikube profile with the ingress controller
#   - one namespace per release strategy, deployer RBAC, app secrets
#   - a kubeconfig for Jenkins, written to $SECRETS_DIR/kubeconfig
# Safe to re-run; every step checks before it creates.
set -euo pipefail

PROFILE=${PROFILE:-aceest}
NETWORK=${NETWORK:-aceest-net}
SUBNET=${SUBNET:-192.168.89.0/24}
NODE_IP=${NODE_IP:-192.168.89.2}
REGISTRY_IP=${REGISTRY_IP:-192.168.89.10}
INGRESS_PORT=${INGRESS_PORT:-8088}
SECRETS_DIR=${SECRETS_DIR:-$HOME/.aceest-ci/secrets}
HERE="$(cd "$(dirname "$0")" && pwd)"
KC=(kubectl --context "$PROFILE")
APP_NAMESPACES=(aceest-rolling aceest-bluegreen aceest-canary aceest-ab aceest-shadow)

mkdir -p "$SECRETS_DIR" && chmod 700 "$SECRETS_DIR"

if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
  docker network create --subnet "$SUBNET" --gateway "${SUBNET%.*}.1" "$NETWORK"
fi

if ! docker inspect aceest-registry >/dev/null 2>&1; then
  docker run -d --name aceest-registry --restart unless-stopped \
    --network "$NETWORK" --ip "$REGISTRY_IP" -p 5005:5000 \
    -v aceest-registry-data:/var/lib/registry \
    -e REGISTRY_STORAGE_DELETE_ENABLED=true \
    registry:2
fi

if ! minikube -p "$PROFILE" status >/dev/null 2>&1; then
  minikube start -p "$PROFILE" --driver=docker \
    --network="$NETWORK" --static-ip="$NODE_IP" \
    --cpus=4 --memory=5g \
    --insecure-registry="$REGISTRY_IP:5000" \
    --ports="$INGRESS_PORT:80" \
    --addons=ingress,metrics-server \
    --keep-context
fi

# Behind a TLS-inspecting proxy the node cannot pull from registry.k8s.io
# until it trusts the proxy's root CA (same files the Jenkins image uses).
shopt -s nullglob
for crt in "$HERE"/../jenkins/extra-ca/*.crt; do
  minikube -p "$PROFILE" cp "$crt" "/usr/local/share/ca-certificates/$(basename "$crt")"
  minikube -p "$PROFILE" ssh -- 'sudo update-ca-certificates && sudo systemctl restart containerd'
done
shopt -u nullglob

"${KC[@]}" apply -f "$HERE/namespaces.yaml" -f "$HERE/jenkins-rbac.yaml"

if [ ! -s "$SECRETS_DIR/ACEEST_ADMIN_PASSWORD" ]; then
  (umask 077 && openssl rand -base64 18 | tr -d '\n' > "$SECRETS_DIR/ACEEST_ADMIN_PASSWORD")
fi

for ns in "${APP_NAMESPACES[@]}"; do
  "${KC[@]}" -n "$ns" create rolebinding jenkins-deployer \
    --clusterrole=aceest-deployer --serviceaccount=aceest-ci:jenkins-deployer \
    --dry-run=client -o yaml | "${KC[@]}" apply -f -
  if ! "${KC[@]}" -n "$ns" get secret aceest-app >/dev/null 2>&1; then
    "${KC[@]}" -n "$ns" create secret generic aceest-app \
      --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
      --from-file=ACEEST_ADMIN_PASSWORD="$SECRETS_DIR/ACEEST_ADMIN_PASSWORD"
  fi
done

echo "waiting for the deployer token..."
for _ in $(seq 1 30); do
  token=$("${KC[@]}" -n aceest-ci get secret jenkins-deployer-token -o jsonpath='{.data.token}' 2>/dev/null | base64 -d || true)
  [ -n "$token" ] && break
  sleep 1
done
[ -n "$token" ] || { echo "token was never issued" >&2; exit 1; }

ca_data=$(base64 < "$HOME/.minikube/ca.crt" | tr -d '\n')
(umask 077 && cat > "$SECRETS_DIR/kubeconfig" <<EOF
apiVersion: v1
kind: Config
clusters:
  - name: $PROFILE
    cluster:
      server: https://$NODE_IP:8443
      certificate-authority-data: $ca_data
users:
  - name: jenkins-deployer
    user:
      token: $token
contexts:
  - name: $PROFILE
    context:
      cluster: $PROFILE
      user: jenkins-deployer
current-context: $PROFILE
EOF
)
echo "kubeconfig for Jenkins written to $SECRETS_DIR/kubeconfig"
