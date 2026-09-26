"""Codex PostToolUse hook for Python files changed by apply_patch."""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update) File: (.+)$", re.MULTILINE)
TOOLS = ("isort", "black", "flake8")


def edited_python_files(command: str, repo_root: Path) -> list[Path]:
    """Return existing Python files from a patch, confined to this repository."""
    root = repo_root.resolve()
    files: list[Path] = []
    for raw_path in PATCH_FILE.findall(command):
        path = (root / raw_path.strip()).resolve()
        if path.suffix != ".py" or not path.is_file():
            continue
        if not path.is_relative_to(root):
            continue
        if path not in files:
            files.append(path)
    return files


def run_formatters(files: list[Path], repo_root: Path) -> Optional[str]:
    """Run formatters in order, then lint; return an error if any tool fails."""
    for tool in TOOLS:
        result = subprocess.run(
            ["uv", "run", "--group", "dev", tool, *map(str, files)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()[-1200:]
            return f"{tool} failed (exit {result.returncode}): {detail}"
    return None


def main() -> int:
    event = json.load(sys.stdin)
    if event.get("tool_name") != "apply_patch":
        return 0

    command = event.get("tool_input", {}).get("command", "")
    if not isinstance(command, str):
        return 0

    repo_root = Path(__file__).resolve().parents[2]
    files = edited_python_files(command, repo_root)
    if not files:
        return 0

    error = run_formatters(files, repo_root)
    if error:
        print(json.dumps({"systemMessage": error}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
