#!/usr/bin/env bash
# Copy every image tag from the local registry to another repository, e.g.
# Docker Hub, so the public repo carries the same version history:
#
#   docker login
#   scripts/mirror-images.sh <dockerhub-user>/aceest-fitness
#
# SOURCE_REPO is the repo as the Docker daemon sees it; REGISTRY_URL is the
# same registry as seen from this machine (used to list the tags).
set -euo pipefail

TARGET=${1:?usage: mirror-images.sh <target-repo>, e.g. myuser/aceest-fitness}
SOURCE_REPO=${SOURCE_REPO:-192.168.89.10:5000/aceest-fitness}
REGISTRY_URL=${REGISTRY_URL:-http://localhost:5005}

tags=$(curl -fsS "$REGISTRY_URL/v2/${SOURCE_REPO#*/}/tags/list" |
       python3 -c 'import json, sys; print("\n".join(sorted(json.load(sys.stdin)["tags"] or [])))')
[ -n "$tags" ] || { echo "no tags found in $SOURCE_REPO"; exit 1; }

for tag in $tags; do
  echo "== $tag"
  docker pull -q "$SOURCE_REPO:$tag"
  docker tag "$SOURCE_REPO:$tag" "$TARGET:$tag"
  docker push -q "$TARGET:$tag"
done
echo "mirrored $(echo "$tags" | wc -l | tr -d ' ') tags to $TARGET"
