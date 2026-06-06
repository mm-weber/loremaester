#!/bin/sh
# Devcontainer entrypoint.
#
# Runs as root (containerUser: "root" in devcontainer.json) so it can
# initialize the egress firewall (iptables needs NET_ADMIN) without a
# sudoers rule, then hands off to the container CMD.
#
# R2R runs on the HOST (reached via host.docker.internal) — there is no
# Docker-in-Docker in this container. See .devcontainer/SecurityReview.md.

set -e

/usr/local/bin/init-firewall.sh

exec "$@"
