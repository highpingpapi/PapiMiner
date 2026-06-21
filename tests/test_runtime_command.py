from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_papiminer():
    path = Path(__file__).resolve().parents[1] / "papiminer_core.py"
    spec = importlib.util.spec_from_file_location("papiminer_core", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_profiles_are_plain_only() -> None:
    app = load_papiminer()
    profiles = app.default_run_profiles()

    assert profiles
    assert all(profile["kind"] == "plain" for profile in profiles)
    assert all(profile["backend"] in {"akoya_plain", "custom"} for profile in profiles)


def test_plain_akoya_command_uses_pool_env(tmp_path: Path) -> None:
    app = load_papiminer()
    profile = {
        "id": "plain-test",
        "kind": "plain",
        "backend": "akoya_plain",
        "cwd": str(tmp_path),
        "path": str(tmp_path / "akoya-miner"),
        "gpu": "0",
        "akoya_gpu_indices": "0",
        "wallet_address": "{wallet_address}",
        "worker": "test-worker",
        "pool_host": "pool.example.com",
        "pool_port": "443",
        "pool_tls": True,
    }

    command, effective, error = app.build_runtime_command(profile, {})

    assert error is None
    assert command is not None
    assert effective["kind"] == "plain"
    assert "AKOYA_POOL_HOST=pool.example.com" in command[-1]
    assert "AKOYA_POOL_WORKER=test-worker" in command[-1]
    assert "mine-blocks" in command[-1]


def test_non_plain_profile_is_rejected(tmp_path: Path) -> None:
    app = load_papiminer()
    profile = {
        "id": "not-plain",
        "kind": "ai",
        "backend": "model_runner",
        "cwd": str(tmp_path),
    }

    command, _effective, error = app.build_runtime_command(profile, {})

    assert command is None
    assert error is not None
    assert "plain-only" in error
