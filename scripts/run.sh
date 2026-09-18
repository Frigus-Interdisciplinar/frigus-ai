#!/usr/bin/env bash
# `just run` chama esse script. Só o mode "local" mexe em Docker — "tui"/"api" rodam a
# aplicação direto, assumindo que a infra (local ou remota) já está no ar. Sem stop automático:
# os containers podem estar compartilhados com outra execução local (ver CLAUDE.md).
set -euo pipefail

MODE="${1:-tui}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$REPO_ROOT/.venv/Scripts/python.exe"
COMPOSE_FILE="$REPO_ROOT/docker-compose.yml"
DOCKER_DESKTOP="/c/Program Files/Docker/Docker/Docker Desktop.exe"

docker_daemon_up() {
    docker info > /dev/null 2>&1
}

start_local_stack() {
    if ! docker_daemon_up; then
        echo "Subindo Docker Desktop..."
        "$DOCKER_DESKTOP" &

        local pronto=0
        for _ in $(seq 1 30); do
            sleep 3
            if docker_daemon_up; then
                pronto=1
                break
            fi
        done

        if [ "$pronto" -eq 0 ]; then
            echo "Docker Desktop não respondeu após 90 segundos." >&2
            exit 1
        fi

        echo "Docker Desktop pronto."
    fi

    echo "Subindo serviços via docker compose (postgres, mongo, redis, qdrant)..."
    docker compose -f "$COMPOSE_FILE" up -d
}

if [ "$MODE" = "local" ]; then
    start_local_stack
    exit 0
fi

exec "$PYTHON" "$REPO_ROOT/main.py" "$MODE"
