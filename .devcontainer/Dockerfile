FROM node:20

ARG TZ
ENV TZ="$TZ"

ARG CLAUDE_CODE_VERSION=latest

# ============================================================
# Base packages + firewall tools
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
  less \
  git \
  git-lfs \
  procps \
  sudo \
  fzf \
  zsh \
  man-db \
  unzip \
  gnupg2 \
  gh \
  iptables \
  ipset \
  iproute2 \
  dnsutils \
  aggregate \
  jq \
  nano \
  vim \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# ============================================================
# Extended toolchain
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  make \
  cmake \
  pkg-config \
  libssl-dev \
  curl \
  wget \
  zip \
  ca-certificates \
  lsb-release \
  openssh-client \
  ripgrep \
  htop \
  yq \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# --- Python + OCR backends ---
RUN apt-get update && apt-get install -y --no-install-recommends \
  python3 \
  python3-pip \
  python3-venv \
  python3-dev \
  tesseract-ocr \
  && ln -sf /usr/bin/python3 /usr/bin/python \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# MCP server runtime + test deps (single source of truth: requirements*.txt
# at the repo root, made reachable by `context: ".."` in devcontainer.json)
# plus uv for the PEP 723 inline scripts. Baked in for reliability and
# to keep image-build-time install cached across rebuilds.
COPY requirements.txt requirements-dev.txt /tmp/
RUN pip install --break-system-packages -r /tmp/requirements-dev.txt && \
  pip install --break-system-packages uv

# ============================================================
# Standard devcontainer plumbing
# ============================================================
RUN mkdir -p /usr/local/share/npm-global && \
  chown -R node:node /usr/local/share

ARG USERNAME=node

# Persist bash history
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
  && mkdir /commandhistory \
  && touch /commandhistory/.bash_history \
  && chown -R $USERNAME /commandhistory

ENV DEVCONTAINER=true

RUN mkdir -p /workspaces/R2R-ClaudeCode-integration /home/node/.claude && \
  chown -R node:node /workspaces /home/node/.claude

WORKDIR /workspaces/R2R-ClaudeCode-integration

# git-delta
ARG GIT_DELTA_VERSION=0.18.2
RUN ARCH=$(dpkg --print-architecture) && \
  wget "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
  sudo dpkg -i "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
  rm "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb"

USER node

ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin
ENV SHELL=/bin/bash
ENV EDITOR=nano
ENV VISUAL=nano

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# Firewall script (run from ENTRYPOINT as root; no sudoers rule needed)
COPY .devcontainer/init-firewall.sh /usr/local/bin/
USER root
RUN chmod +x /usr/local/bin/init-firewall.sh

# Entrypoint: runs as root (containerUser: "root" in devcontainer.json),
# initializes the egress firewall, then exec's the container CMD.
COPY .devcontainer/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sh", "-c", "while sleep 1 & wait $!; do :; done"]

# Informational: interactive shells attach as `node` via remoteUser.
# PID 1 is overridden by containerUser: "root" in devcontainer.json.
USER node
