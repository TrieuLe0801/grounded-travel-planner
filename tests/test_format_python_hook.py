"""Behavior checks for the Codex Python formatting hook."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

HOOK_PATH = Path(__file__).resolve().parents[1] / ".codex/hooks/format_python.py"
SPEC = importlib.util.spec_from_file_location("format_python_hook", HOOK_PATH)
assert SPEC is not None and SPEC.loader is not None
hook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hook)


def test_only_existing_python_files_inside_repo_are_selected(tmp_path):
    inside = tmp_path / "module.py"
    inside.write_text("x=1\n")
    outside = tmp_path.parent / "outside.py"
    outside.write_text("x=2\n")
    patch = (
        "*** Begin Patch\n"
        "*** Update File: module.py\n"
        "*** Update File: module.py\n"
        "*** Add File: missing.py\n"
        "*** Update File: ../outside.py\n"
        "*** Delete File: deleted.py\n"
        "*** End Patch\n"
    )

    assert hook.edited_python_files(patch, tmp_path) == [inside]


def test_formatters_run_in_order_and_stop_on_failure(tmp_path, monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=1 if command[4] == "black" else 0,
            stderr="lint failure",
            stdout="",
        )

    monkeypatch.setattr(hook.subprocess, "run", fake_run)
    file_path = tmp_path / "module.py"
    error = hook.run_formatters([file_path], tmp_path)

    assert [command[4] for command, _ in calls] == ["isort", "black"]
    assert all(kwargs["cwd"] == tmp_path for _, kwargs in calls)
    assert error == "black failed (exit 1): lint failure"
