#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, and pipeline failures
IFS=$'\n\t'       # Stricter word splitting

# 1. Extract Docker DNS info BEFORE any flushing
DOCKER_DNS_RULES=$(iptables-save -t nat | grep "127\.0\.0\.11" || true)

# Flush existing rules and delete existing ipsets
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
ipset destroy allowed-domains 2>/dev/null || true

# Reset policies to ACCEPT so this script can re-run after a previous lockdown.
# Without this, the meta fetch below is blocked by leftover DROP policy.
iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT
iptables -P OUTPUT ACCEPT


# 2. Selectively restore ONLY internal Docker DNS resolution
if [ -n "$DOCKER_DNS_RULES" ]; then
    echo "Restoring Docker DNS rules..."
    iptables -t nat -N DOCKER_OUTPUT 2>/dev/null || true
    iptables -t nat -N DOCKER_POSTROUTING 2>/dev/null || true
    echo "$DOCKER_DNS_RULES" | xargs -L 1 iptables -t nat
else
    echo "No Docker DNS rules to restore"
fi

# First allow DNS and localhost before any restrictions
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A INPUT -p udp --sport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --sport 22 -m state --state ESTABLISHED -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Allow DNS to all configured nameservers (covers host DNS, etc.)
for ns in $(grep '^nameserver' /etc/resolv.conf | awk '{print $2}'); do
    echo "Allowing DNS to nameserver $ns"
    iptables -A OUTPUT -d "$ns" -p udp --dport 53 -j ACCEPT
    iptables -A OUTPUT -d "$ns" -p tcp --dport 53 -j ACCEPT
    iptables -A INPUT -s "$ns" -p udp --sport 53 -j ACCEPT
    iptables -A INPUT -s "$ns" -p tcp --sport 53 -j ACCEPT
done


# Create ipset with CIDR support
ipset create allowed-domains hash:net

# Fetch GitHub meta information and aggregate + add their IP ranges
echo "Fetching GitHub IP ranges..."
gh_ranges=$(curl -s https://api.github.com/meta)
if [ -z "$gh_ranges" ]; then
    echo "ERROR: Failed to fetch GitHub IP ranges"
    exit 1
fi

if ! echo "$gh_ranges" | jq -e '.web and .api and .git' >/dev/null; then
    echo "ERROR: GitHub API response missing required fields"
    exit 1
fi

echo "Processing GitHub IPs..."
while read -r cidr; do
    if [[ ! "$cidr" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}$ ]]; then
        echo "ERROR: Invalid CIDR range from GitHub meta: $cidr"
        exit 1
    fi
    echo "Adding GitHub range $cidr"
    ipset add allowed-domains "$cidr"
done < <(echo "$gh_ranges" | jq -r '(.web + .api + .git)[] | select(test(":") | not)' | sort -u)


# ============================================================
# Allowed domains
# Stock:     npm, Anthropic, Sentry, Statsig, VS Code (partial; see REMOVED)
# ADDED:     Python (PyPI + uv via astral.sh)
# REMOVED:   vscode.blob.core.windows.net — opaque Azure CDN; the standard
#            VS Code Desktop + Reopen-in-Container flow tunnels the server
#            install via the client, so the container never needs direct
#            CDN access. Re-add if an extension fails to fetch assets at
#            runtime (symptom: silent extension load failure with denied
#            iptables hits to *.blob.core.windows.net).
# To extend: just add more domains to this list
# ============================================================
for domain in \
    "github.com" \
    "api.github.com" \
    "registry.npmjs.org" \
    "api.anthropic.com" \
    "sentry.io" \
    "statsig.anthropic.com" \
    "statsig.com" \
    "marketplace.visualstudio.com" \
    "update.code.visualstudio.com" \
    "pypi.org" \
    "files.pythonhosted.org" \
    "astral.sh" \
    ; do
    echo "Resolving $domain..."
    ips=$(dig +noall +answer A "$domain" | awk '$4 == "A" {print $5}')
    if [ -z "$ips" ]; then
        echo "WARNING: Failed to resolve $domain — skipping"
        continue
    fi

    while read -r ip; do
        if [[ ! "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
            echo "ERROR: Invalid IP from DNS for $domain: $ip"
            exit 1
        fi
        echo "Adding $ip for $domain"
        ipset add allowed-domains "$ip" 2>/dev/null || true
    done < <(echo "$ips")
done

# Get host gateway IP from default route — this is what host.docker.internal
# resolves to, and how the devcontainer reaches services on the host.
HOST_IP=$(ip route | grep default | cut -d" " -f3)
if [ -z "$HOST_IP" ]; then
    echo "ERROR: Failed to detect host gateway IP"
    exit 1
fi
echo "Host gateway detected as: $HOST_IP"

# Allow ONLY the host services the devcontainer actually needs:
#   - R2R API on the host:  7272
#   - Ollama on the host:  11434
# Responses return via the ESTABLISHED rule below. This replaces the prior
# whole-/24 carve-out; see .devcontainer/SecurityReview.md.
iptables -A OUTPUT -d "$HOST_IP" -p tcp -m multiport --dports 7272,11434 -j ACCEPT

# Docker Desktop (macOS/Windows): host.docker.internal is a dedicated host
# address (e.g. 192.168.65.254), NOT the default-route gateway detected above.
# Allow whatever host.docker.internal currently resolves to (IPv4), on the same
# host-service ports, so the MCP servers can reach R2R/Ollama on Docker Desktop.
HDI_IP=$(getent ahostsv4 host.docker.internal | awk '{print $1}' | head -1)
if [ -n "$HDI_IP" ] && [ "$HDI_IP" != "$HOST_IP" ]; then
    echo "Allowing host.docker.internal at $HDI_IP on 7272,11434 (Docker Desktop)"
    iptables -A OUTPUT -d "$HDI_IP" -p tcp -m multiport --dports 7272,11434 -j ACCEPT
fi

# Set default policies to DROP
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# Allow established connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow only approved destinations
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

# Reject everything else with immediate feedback
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

echo "Firewall configuration complete"
echo "Verifying firewall rules..."
if curl --connect-timeout 5 https://example.com >/dev/null 2>&1; then
    echo "ERROR: Firewall verification failed - was able to reach https://example.com"
    exit 1
else
    echo "Firewall verification passed - unable to reach https://example.com as expected"
fi

if ! curl --connect-timeout 5 https://api.github.com/zen >/dev/null 2>&1; then
    echo "ERROR: Firewall verification failed - unable to reach https://api.github.com"
    exit 1
else
    echo "Firewall verification passed - able to reach https://api.github.com as expected"
fi
