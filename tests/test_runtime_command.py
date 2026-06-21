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


def test_useful_multi_gpu_auto_sets_tensor_parallel_size(tmp_path: Path) -> None:
    app = load_papiminer()
    profile = {
        "id": "useful-test",
        "backend": "akoya_vllm",
        "cwd": str(tmp_path),
        "gpu": "0",
        "model": str(tmp_path),
        "wallet_address": "{wallet_address}",
        "worker": "test-worker",
        "tensor_parallel_size": 1,
    }
    command, effective, error = app.build_runtime_command(profile, {"gpu": "0,1"})

    assert error is None
    assert command is not None
    assert effective["tensor_parallel_size"] == "2"
    assert "--host 127.0.0.1 --port 8001 -- --tensor-parallel-size 2" in command[-1]
    assert "--tensor-parallel-size 2" in command[-1]


def test_useful_multi_gpu_keeps_explicit_tensor_parallel_size(tmp_path: Path) -> None:
    app = load_papiminer()
    profile = {
        "id": "useful-test",
        "backend": "akoya_vllm",
        "cwd": str(tmp_path),
        "gpu": "0",
        "model": str(tmp_path),
        "wallet_address": "{wallet_address}",
        "worker": "test-worker",
        "tensor_parallel_size": 1,
    }
    command, effective, error = app.build_runtime_command(profile, {"gpu": "0,1", "tensor_parallel_size": "1"})

    assert error is None
    assert command is not None
    assert effective["tensor_parallel_size"] == "1"
    assert "--tensor-parallel-size 1" in command[-1]


def test_stopped_runtime_with_log_error_is_not_plain_timeout() -> None:
    app = load_papiminer()
    record = {"running": False}
    lines = [
        "EngineCore failed to start.",
        "torch.OutOfMemoryError: CUDA out of memory.",
    ]

    diagnostic = app.runtime_stage_from_log(record, None, lines)

    assert diagnostic["code"] == "stopped_error"
    assert diagnostic["severity"] == "bad"
    assert "OutOfMemory" in diagnostic["recent_error"]
