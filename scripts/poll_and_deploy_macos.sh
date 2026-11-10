#!/usr/bin/env bash

set -Eeuo pipefail

fail() {
    printf 'Mac deployment poll failed: %s\n' "$1" >&2
    exit 1
}

mode="${1:-poll}"
[[ "$#" -le 1 && ( "$mode" == "poll" || "$mode" == "--check" ) ]] || \
    fail "usage: $0 [--check]"

config_file="${GTP_DEPLOY_CONFIG:-$HOME/.config/grounded-travel-planner/deploy.env}"
[[ -f "$config_file" ]] || fail "local deploy config is missing."
config_mode="$(stat -f '%Lp' "$config_file")"
[[ "$config_mode" == "600" || "$config_mode" == "400" ]] || \
    fail "local deploy config must have mode 600 or 400."

set -a
# shellcheck disable=SC1090
. "$config_file"
set +a

[[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]] || \
    fail "deployment host must be Apple Silicon macOS."
[[ "${GTP_DEPLOY_ENABLED:-false}" == "true" || "${GTP_DEPLOY_ENABLED:-false}" == "false" ]] || \
    fail "GTP_DEPLOY_ENABLED must be true or false."
[[ -n "${GTP_DEPLOY_BRANCH:-}" ]] || fail "GTP_DEPLOY_BRANCH is not set."
[[ -n "${GTP_DEPLOY_SOURCE:-}" && -d "$GTP_DEPLOY_SOURCE" ]] || \
    fail "GTP_DEPLOY_SOURCE must point to the local project checkout."
[[ -n "${GTP_DEPLOY_CHECKOUT:-}" && "$GTP_DEPLOY_CHECKOUT" = /* ]] || \
    fail "GTP_DEPLOY_CHECKOUT must be an absolute path."
[[ "$GTP_DEPLOY_CHECKOUT" != "$GTP_DEPLOY_SOURCE" ]] || \
    fail "deployment checkout must be separate from the development checkout."

repo_prefix="${GTP_DEPLOY_SOURCE%/}/"
case "$GTP_DEPLOY_CHECKOUT/" in
    "$repo_prefix"*) fail "deployment checkout must stay outside the development checkout." ;;
esac

if [[ "$mode" == "--check" ]]; then
    bash "$GTP_DEPLOY_SOURCE/scripts/deploy_macos.sh" --check "$GTP_DEPLOY_SOURCE"
    exit 0
fi

if [[ "$GTP_DEPLOY_ENABLED" != "true" ]]; then
    exit 0
fi

state_dir="$HOME/.local/state/grounded-travel-planner"
mkdir -p "$state_dir"
chmod 700 "$state_dir"
lock_dir="$state_dir/poll.lock"
if ! mkdir "$lock_dir" 2>/dev/null; then
    printf 'Another Mac deployment poll is already running.\n'
    exit 0
fi
trap 'rmdir "$lock_dir" 2>/dev/null || true' EXIT

repository_url="https://github.com/TrieuLe0801/grounded-travel-planner.git"
latest_sha="$(git ls-remote "$repository_url" "refs/heads/$GTP_DEPLOY_BRANCH" | awk 'NR == 1 {print $1}')"
[[ "$latest_sha" =~ ^[0-9a-f]{40}$ ]] || fail "could not read deployment branch head."

processed_file="$state_dir/last-processed-sha"
attempted_file="$state_dir/last-attempted-sha"
processed_sha=""
attempted_sha=""
[[ ! -f "$processed_file" ]] || processed_sha="$(cat "$processed_file")"
[[ ! -f "$attempted_file" ]] || attempted_sha="$(cat "$attempted_file")"
if [[ "$latest_sha" == "$processed_sha" || "$latest_sha" == "$attempted_sha" ]]; then
    printf 'Deployment branch head %s was already processed.\n' "$latest_sha"
    exit 0
fi

ci_status=0
if python3 - "$latest_sha" "$GTP_DEPLOY_BRANCH" <<'PY'
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

sha, branch = sys.argv[1:]
query = urllib.parse.urlencode(
    {"head_sha": sha, "branch": branch, "event": "push", "per_page": 20}
)
url = (
    "https://api.github.com/repos/TrieuLe0801/grounded-travel-planner"
    f"/actions/workflows/ci-cd.yml/runs?{query}"
)
request = urllib.request.Request(
    url,
    headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "grounded-travel-planner-mac-deploy",
    },
)
try:
    with urllib.request.urlopen(request, timeout=15) as response:
        runs = json.load(response).get("workflow_runs", [])
except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as error:
    print(f"Could not read GitHub Actions status: {type(error).__name__}.")
    raise SystemExit(3)

matching = [
    run for run in runs if run.get("head_sha") == sha and run.get("event") == "push"
]
if not matching:
    print(f"CI run for {sha} is pending.")
    raise SystemExit(3)
run = max(matching, key=lambda item: item.get("run_number", 0))
if run.get("status") != "completed":
    print(f"CI run for {sha} is {run.get('status', 'pending')}.")
    raise SystemExit(3)
if run.get("conclusion") != "success":
    print(f"CI run for {sha} concluded {run.get('conclusion', 'unknown')}; app stays unchanged.")
    raise SystemExit(4)
print(f"CI passed for {sha}.")
PY
then
    :
else
    ci_status=$?
fi
if [[ "$ci_status" -eq 3 || "$ci_status" -eq 4 ]]; then
    exit 0
fi
[[ "$ci_status" -eq 0 ]] || fail "GitHub Actions status check failed."

mkdir -p "$(dirname "$GTP_DEPLOY_CHECKOUT")"
if [[ -d "$GTP_DEPLOY_CHECKOUT/.git" ]]; then
    remote_url="$(git -C "$GTP_DEPLOY_CHECKOUT" remote get-url origin)"
    [[ "$remote_url" == "$repository_url" || "$remote_url" == "${repository_url%.git}" ]] || \
        fail "deployment checkout origin does not match the project repository."
else
    if [[ -e "$GTP_DEPLOY_CHECKOUT" ]] && [[ -n "$(find "$GTP_DEPLOY_CHECKOUT" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
        fail "deployment checkout path exists and is not empty."
    fi
    git clone --filter=blob:none --single-branch --branch "$GTP_DEPLOY_BRANCH" \
        "$repository_url" "$GTP_DEPLOY_CHECKOUT" >/dev/null
fi

git -C "$GTP_DEPLOY_CHECKOUT" fetch --no-tags origin "$GTP_DEPLOY_BRANCH" --quiet
git -C "$GTP_DEPLOY_CHECKOUT" cat-file -e "${latest_sha}^{commit}" || \
    fail "deployment commit is missing from the local checkout."
git -C "$GTP_DEPLOY_CHECKOUT" reset --hard "$latest_sha" >/dev/null

runtime_change=true
if [[ -n "$processed_sha" ]] && git -C "$GTP_DEPLOY_CHECKOUT" cat-file -e "${processed_sha}^{commit}" 2>/dev/null; then
    changed_files="$(git -C "$GTP_DEPLOY_CHECKOUT" diff --name-only "$processed_sha" "$latest_sha")"
    if ! grep -Eq '^(src/|frontend/|data/|scripts/migrate_saved_tours_(index|to_postgres|account_ownership)\.py$|Dockerfile$|compose\.yaml$|pyproject\.toml$|uv\.lock$|\.python-version$)' <<<"$changed_files"; then
        runtime_change=false
    fi
fi

if [[ "$runtime_change" == false ]]; then
    printf '%s\n' "$latest_sha" > "$processed_file"
    chmod 600 "$processed_file"
    printf 'No app files changed in %s; app stays unchanged.\n' "$latest_sha"
    exit 0
fi

bash "$GTP_DEPLOY_CHECKOUT/scripts/deploy_macos.sh" --check "$GTP_DEPLOY_CHECKOUT"
printf '%s\n' "$latest_sha" > "$attempted_file"
chmod 600 "$attempted_file"
if bash "$GTP_DEPLOY_CHECKOUT/scripts/deploy_macos.sh" "$GTP_DEPLOY_CHECKOUT"; then
    printf '%s\n' "$latest_sha" > "$processed_file"
    chmod 600 "$processed_file"
    printf 'Mac deployment completed for %s.\n' "$latest_sha"
else
    printf '%s\n' "$latest_sha" > "$processed_file"
    chmod 600 "$processed_file"
    printf 'Deployment failed for %s; previous app image remains active when rollback succeeded.\n' "$latest_sha" >&2
    exit 1
fi
