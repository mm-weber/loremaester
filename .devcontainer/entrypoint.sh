#!/bin/sh
# Devcontainer entrypoint.
#
# Runs as root (containerUser: "root" in devcontainer.json). Performs
# privileged initialization that previously required either the deleted
# sudoers rule (for init-firewall.sh) or unprivileged sudo (for
# /usr/local/share/docker-init.sh — which would have prompted for a
# password the user does not have).
#
# Order matters:
#   1. Firewall first — locks down egress before any network-using process
#      can talk to the wider internet.
#   2. DinD wrapper second — spawns dockerd as root, then we fall through
#      to exec "$@" which becomes the container's CMD (a wait loop).
#
# Replaces:
#   - postStartCommand `sudo /usr/local/bin/init-firewall.sh ...` (H-3)
#   - The broken sudo path inside docker-init.sh (no sudoers rule for it)

set -e

/usr/local/bin/init-firewall.sh

# docker-init.sh's tail is `exec "$@"` — passing through whatever CMD
# devcontainer.json / Dockerfile set. With overrideCommand: false in
# devcontainer.json, that CMD is the wait loop from our Dockerfile.
exec /usr/local/share/docker-init.sh "$@"
