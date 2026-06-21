from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_smoke_module():
    path = Path(__file__).with_name("smoke_papiminer.py")
    spec = importlib.util.spec_from_file_location("smoke_papiminer", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_papiminer_smoke_flow() -> None:
    smoke = _load_smoke_module()
    assert smoke.main() == 0
