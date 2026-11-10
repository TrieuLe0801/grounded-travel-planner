#!/usr/bin/env bash

set -Eeuo pipefail

fail() {
    printf 'Mac deployment failed: %s\n' "$1" >&2
    exit 1
}

mode="deploy"
workspace_arg="${GITHUB_WORKSPACE:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
if [[ "${1:-}" == "--check" ]]; then
    mode="--check"
    shift
fi
if [[ "$#" -gt 0 ]]; then
    workspace_arg="$1"
    shift
fi
[[ "$#" -eq 0 ]] || fail "usage: $0 [--check] [workspace]"

[[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]] || \
    fail "deployment runner must be Apple Silicon macOS."

workspace="$(cd "$workspace_arg" && pwd -P)"
config_file="${GTP_DEPLOY_CONFIG:-$HOME/.config/grounded-travel-planner/deploy.env}"

[[ -f "$workspace/compose.yaml" ]] || fail "compose.yaml is missing from workspace."
[[ -f "$workspace/Dockerfile" ]] || fail "Dockerfile is missing from workspace."
[[ -f "$config_file" ]] || fail "local deploy config is missing: $config_file"

config_mode="$(stat -f '%Lp' "$config_file")"
[[ "$config_mode" == "600" || "$config_mode" == "400" ]] || \
    fail "local deploy config must have mode 600 or 400."

# The local file contains only paths and is kept outside Git.
set -a
# shellcheck disable=SC1090
. "$config_file"
set +a

[[ -n "${GTP_DEPLOY_ENV_FILE:-}" ]] || fail "GTP_DEPLOY_ENV_FILE is not set."
[[ -n "${GTP_DATA_DIR:-}" ]] || fail "GTP_DATA_DIR is not set."
[[ "$GTP_DEPLOY_ENV_FILE" = /* ]] || fail "GTP_DEPLOY_ENV_FILE must be an absolute path."
[[ "$GTP_DATA_DIR" = /* ]] || fail "GTP_DATA_DIR must be an absolute path."
[[ -f "$GTP_DEPLOY_ENV_FILE" ]] || fail "deployment .env file is missing."
[[ -d "$GTP_DATA_DIR/postgres" ]] || fail "PostgreSQL data directory is missing."

env_mode="$(stat -f '%Lp' "$GTP_DEPLOY_ENV_FILE")"
[[ "$env_mode" == "600" || "$env_mode" == "400" ]] || \
    fail "deployment .env file must have mode 600 or 400."

workspace_prefix="${workspace%/}/"
case "$GTP_DATA_DIR/" in
    "$workspace_prefix"*) fail "GTP_DATA_DIR must stay outside the checkout." ;;
esac

export GTP_DATA_DIR
export GTP_DEPLOY_ENV_FILE
export DOCKER_BUILDKIT=1

created_env_link=false
if [[ -e "$workspace/.env" || -L "$workspace/.env" ]]; then
    env_real="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$workspace/.env")"
    deploy_env_real="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$GTP_DEPLOY_ENV_FILE")"
    [[ "$env_real" == "$deploy_env_real" ]] || fail "workspace already contains a different .env file."
else
    ln -s "$GTP_DEPLOY_ENV_FILE" "$workspace/.env"
    created_env_link=true
fi

cleanup() {
    if [[ "$created_env_link" == true ]]; then
        rm -f "$workspace/.env"
    fi
}
trap cleanup EXIT

compose() {
    docker compose \
        --project-name grounded-travel-planner \
        --project-directory "$workspace" \
        --env-file "$GTP_DEPLOY_ENV_FILE" \
        --file "$workspace/compose.yaml" \
        "$@"
}

docker info >/dev/null 2>&1 || fail "Docker Desktop engine is unavailable."
compose config --quiet || fail "Compose configuration is invalid."

db_id="$(compose ps --quiet db)"
[[ -n "$db_id" ]] || fail "PostgreSQL container is not running; deployment stopped."
db_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$db_id")"
[[ "$db_health" == "healthy" ]] || fail "PostgreSQL container is not healthy; deployment stopped."

if [[ "$mode" == "--check" ]]; then
    printf 'Mac deployment preflight passed. Database remains running.\n'
    exit 0
fi

old_container_id="$(compose ps --all --quiet app | head -n 1)"
old_image_id=""
if [[ -n "$old_container_id" ]]; then
    old_image_id="$(docker inspect --format '{{.Image}}' "$old_container_id")"
fi

compose build app
if ! compose up --detach --no-deps --wait --wait-timeout 180 app; then
    printf 'New app image failed health check.\n' >&2
    if [[ -n "$old_image_id" ]]; then
        docker image tag "$old_image_id" grounded-travel-planner:local
        if compose up --detach --no-deps --no-build --force-recreate --wait --wait-timeout 120 app; then
            printf 'Previous app image restored.\n' >&2
        else
            printf 'Previous app image could not be restored automatically.\n' >&2
        fi
    fi
    exit 1
fi

app_endpoint="$(compose port app 8000)"
[[ -n "$app_endpoint" ]] || fail "app port is not published."
if ! curl --fail --silent --show-error --retry 5 --retry-connrefused --retry-delay 2 \
    "http://${app_endpoint}/" >/dev/null; then
    printf 'New app did not return HTTP 200.\n' >&2
    if [[ -n "$old_image_id" ]]; then
        docker image tag "$old_image_id" grounded-travel-planner:local
        if compose up --detach --no-deps --no-build --force-recreate --wait --wait-timeout 120 app; then
            printf 'Previous app image restored.\n' >&2
        else
            printf 'Previous app image could not be restored automatically.\n' >&2
        fi
    fi
    exit 1
fi

printf 'Mac deployment succeeded for %s. PostgreSQL container was not recreated.\n' \
    "${GITHUB_SHA:-local checkout}"
