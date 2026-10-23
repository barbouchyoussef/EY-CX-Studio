#!/bin/bash
# Runs on every boot of the CX Studio VM (Container-Optimized OS, Docker preinstalled).
#
# Replaces the discontinued "create-with-container" agent: it does the same three things
# explicitly — authenticate to Artifact Registry, fetch the env file from instance metadata,
# and run the container. Because it runs on every boot, `gcloud compute instances start`
# brings the app back with no manual step.
set -euo pipefail

IMAGE="$(curl -sf -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/app-image)"

# Container-Optimized OS ships its own iptables firewall with INPUT policy DROP, allowing
# only SSH. That is SEPARATE from the VPC firewall rule: GCP delivers the packet to the VM
# and the OS then drops it. Both layers must permit the port. Re-applied on every boot
# because COS does not persist iptables rules.
iptables -w -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null \
  || iptables -w -A INPUT -p tcp --dport 80 -j ACCEPT

# Container-Optimized OS mounts / read-only, so the default docker config path
# (/root/.docker) cannot be created. /var/lib is one of the few writable paths, so point
# HOME and DOCKER_CONFIG there before touching docker.
export HOME=/var/lib/cx-home
export DOCKER_CONFIG="$HOME/.docker"
mkdir -p "$DOCKER_CONFIG"

# Let Docker authenticate to Artifact Registry using the VM's own service account.
docker-credential-gcr configure-docker --registries=europe-west1-docker.pkg.dev

# The environment file lives in instance metadata, never in the image, so rotating a key
# is a metadata update plus a restart rather than a 3 GB rebuild.
curl -sf -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/app-env \
  > /var/lib/app.env
chmod 600 /var/lib/app.env

docker pull "$IMAGE"

# --network host: the app binds PORT=80 directly on the VM's interface, so no port mapping.
# --restart always: Docker restarts the container if it crashes.
docker rm -f cx >/dev/null 2>&1 || true
docker run -d \
  --name cx \
  --restart always \
  --network host \
  --env-file /var/lib/app.env \
  "$IMAGE"
