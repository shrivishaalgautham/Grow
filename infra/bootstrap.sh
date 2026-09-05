#!/usr/bin/env bash
set -euo pipefail

readonly DOCKER_GPG_URL="https://download.docker.com/linux/ubuntu/gpg"
readonly DOCKER_KEYRING="/etc/apt/keyrings/docker.asc"
readonly DOCKER_LIST="/etc/apt/sources.list.d/docker.list"
readonly AUTOMATION_USER="automation"

_ts() { date '+%H:%M:%S'; }
log_info()  { printf '[%s] \033[1;34m==>\033[0m %s\n' "$(_ts)" "$*"; }
log_ok()    { printf '[%s] \033[1;32m ok\033[0m %s\n'  "$(_ts)" "$*"; }
log_warn()  { printf '[%s] \033[1;33mwarn\033[0m %s\n' "$(_ts)" "$*" >&2; }
log_fatal() { printf '[%s] \033[1;31mFATAL\033[0m %s\n' "$(_ts)" "$*" >&2; exit 1; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command_exists sudo; then
        SUDO="sudo"
    else
        log_fatal "Not running as root and 'sudo' is not available. Re-run as root or install sudo."
    fi
fi

run_root() { $SUDO "$@"; }

APT_UPDATED=0
apt_update_once() {
    if [ "$APT_UPDATED" -eq 0 ]; then
        run_root apt-get update -qq
        APT_UPDATED=1
    fi
}

apt_install() {
    local missing=()
    local pkg
    for pkg in "$@"; do
        if ! dpkg -s "$pkg" >/dev/null 2>&1; then
            missing+=("$pkg")
        fi
    done
    if [ "${#missing[@]}" -eq 0 ]; then
        log_ok "package(s) already installed: $*"
        return 0
    fi
    apt_update_once
    log_info "installing missing package(s): ${missing[*]}"
    if ! run_root apt-get install -y -qq "${missing[@]}"; then
        log_fatal "apt-get failed to install: ${missing[*]}"
    fi
    log_ok "installed: ${missing[*]}"
}

log_info "Detecting operating system..."

if [ ! -r /etc/os-release ]; then
    log_fatal "/etc/os-release not found — cannot verify this is Ubuntu."
fi

# shellcheck disable=SC1091
. /etc/os-release

if [ "${ID:-}" != "ubuntu" ]; then
    log_fatal "Unsupported OS (ID='${ID:-unknown}'). This script only supports Ubuntu."
fi

log_ok "Ubuntu ${VERSION_ID:-unknown} detected."

if ! command_exists apt-get; then
    log_fatal "apt-get not found — cannot proceed on an Ubuntu system without it."
fi

apt_install git curl ca-certificates

log_info "Checking for Docker..."

if command_exists docker; then
    log_ok "Docker is already installed: $(docker --version)"
else
    log_info "Docker not found. Installing Docker Engine from the official repo..."

    run_root install -m 0755 -d /etc/apt/keyrings
    if [ ! -f "$DOCKER_KEYRING" ]; then
        log_info "Adding Docker's GPG key..."
        if ! curl -fsSL "$DOCKER_GPG_URL" | run_root tee "$DOCKER_KEYRING" >/dev/null; then
            log_fatal "Failed to fetch Docker's GPG key from $DOCKER_GPG_URL"
        fi
        run_root chmod a+r "$DOCKER_KEYRING"
    else
        log_ok "Docker GPG key already present."
    fi

    if [ ! -f "$DOCKER_LIST" ]; then
        log_info "Adding Docker's apt repository..."
        # shellcheck disable=SC1091
        ARCH="$(dpkg --print-architecture)"
        echo "deb [arch=${ARCH} signed-by=${DOCKER_KEYRING}] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
            | run_root tee "$DOCKER_LIST" >/dev/null
        APT_UPDATED=0
    else
        log_ok "Docker apt repository already present."
    fi

    apt_install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    if ! command_exists docker; then
        log_fatal "Docker installation completed but 'docker' still isn't on PATH."
    fi
    log_ok "Docker installed: $(docker --version)"
fi

log_info "Enabling and starting the Docker service..."
run_root systemctl enable --now docker
if ! run_root systemctl is-active --quiet docker; then
    log_fatal "Docker service failed to start. Check 'systemctl status docker' for details."
fi
log_ok "Docker service is active."

if ! run_root docker info >/dev/null 2>&1; then
    log_fatal "Docker daemon is running but not responding to 'docker info'. Check 'journalctl -u docker'."
fi

log_info "Checking Docker Compose v2 functionality..."

if docker compose version >/dev/null 2>&1; then
    log_ok "Docker Compose is available: $(docker compose version --short 2>/dev/null || docker compose version)"
else
    log_info "'docker compose' not working. Installing the compose plugin..."
    apt_install docker-compose-plugin
    if ! docker compose version >/dev/null 2>&1; then
        log_fatal "docker-compose-plugin installed but 'docker compose version' still fails."
    fi
    log_ok "Docker Compose is now available: $(docker compose version --short 2>/dev/null || docker compose version)"
fi

log_info "Checking for the '${AUTOMATION_USER}' user..."

if id "$AUTOMATION_USER" >/dev/null 2>&1; then
    log_ok "User '${AUTOMATION_USER}' already exists."
else
    log_info "Creating user '${AUTOMATION_USER}'..."
    run_root useradd --create-home --shell /bin/bash "$AUTOMATION_USER"
    log_ok "User '${AUTOMATION_USER}' created."
fi

if ! getent group docker >/dev/null; then
    log_warn "No 'docker' group found even after install — skipping group membership setup."
elif id -nG "$AUTOMATION_USER" 2>/dev/null | grep -qw docker; then
    log_ok "User '${AUTOMATION_USER}' is already in the 'docker' group."
else
    log_info "Adding '${AUTOMATION_USER}' to the 'docker' group..."
    run_root usermod -aG docker "$AUTOMATION_USER"
    log_ok "'${AUTOMATION_USER}' added to 'docker' group."
fi

cat <<EOF

============================================================
 Bootstrap complete. Docker, Compose, git, curl, and the
 '${AUTOMATION_USER}' user are ready. Nothing has been started yet —
 that's the rest of infra/README.md's runbook:

   sudo -iu ${AUTOMATION_USER}
   git clone <this repo's URL> ~/grow
   cd ~/grow/infra
   docker network create grow-data
   docker network create grow-edge
   cd stacks/postgres-redis && cp .env.example .env   # fill in real values
   docker compose up -d
   cd ../../nginx && mkdir -p active
   for f in active/*.example; do cp "\$f" "active/\$(basename "\$f" .example)"; done
   docker compose up -d
   cd ../stacks/portainer && docker compose up -d

 Then create the 'grow' stack in Portainer over an SSH tunnel
 (\`ssh -L 9443:127.0.0.1:9443 ${AUTOMATION_USER}@<vm>\`,
 then https://localhost:9443). Full details, including domains/TLS
 and how to redeploy: infra/README.md.

 If '${AUTOMATION_USER}' was just added to the 'docker' group, it
 takes effect on that user's next login (or 'newgrp docker').
============================================================
EOF
