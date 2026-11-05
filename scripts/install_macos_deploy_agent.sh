#!/usr/bin/env bash

set -Eeuo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
config_file="${GTP_DEPLOY_CONFIG:-$HOME/.config/grounded-travel-planner/deploy.env}"
[[ -f "$config_file" ]] || {
    printf 'Local deploy config is missing: %s\n' "$config_file" >&2
    exit 1
}

install_dir="$HOME/.local/share/grounded-travel-planner"
launch_agents_dir="$HOME/Library/LaunchAgents"
logs_dir="$HOME/Library/Logs"
script_path="$install_dir/poll_and_deploy_macos.sh"
plist_path="$launch_agents_dir/com.groundedtravelplanner.deploy.plist"
label="com.groundedtravelplanner.deploy"

mkdir -p "$install_dir" "$launch_agents_dir" "$logs_dir"
cp "$project_root/scripts/poll_and_deploy_macos.sh" "$script_path"
chmod 700 "$script_path"

python3 - "$plist_path" "$script_path" "$config_file" "$HOME" "$label" <<'PY'
import plistlib
import sys
from pathlib import Path

plist_path, script_path, config_path, home, label = sys.argv[1:]
log_path = Path(home) / "Library/Logs/grounded-travel-planner-deploy.log"
plist = {
    "Label": label,
    "ProgramArguments": ["/bin/bash", script_path],
    "WorkingDirectory": home,
    "RunAtLoad": True,
    "StartInterval": 300,
    "StandardOutPath": str(log_path),
    "StandardErrorPath": str(log_path),
    "EnvironmentVariables": {
        "HOME": home,
        "GTP_DEPLOY_CONFIG": config_path,
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    },
}
with Path(plist_path).open("wb") as stream:
    plistlib.dump(plist, stream)
PY

plutil -lint "$plist_path"
user_domain="gui/$(id -u)"
if launchctl print "$user_domain/$label" >/dev/null 2>&1; then
    launchctl bootout "$user_domain" "$plist_path"
fi
launchctl bootstrap "$user_domain" "$plist_path"
launchctl kickstart -k "$user_domain/$label"
printf 'Installed Mac deployment poller. Checks GitHub Actions every 5 minutes.\n'
