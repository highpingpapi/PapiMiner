from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "kernel_lab" / "candidates.json"


def test_kernel_lab_manifest_has_next_candidate() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert data["scope"] == "Pearl PlainProof mining backend only"
    assert data["target"]["stretch_ths"] == 140.0
    assert data["baselines"]
    assert any(item["status"] == "next" for item in data["candidates"])


def test_kernel_lab_manifest_is_public_safe() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    forbidden = [
        r"prl1[a-z0-9]+",
        r"C:\\Users\\",
        r"192\.168\.",
        r"pool-routed",
        r"useful-work",
        r"seed phrase",
        r"private key",
    ]

    for pattern in forbidden:
        assert not re.search(pattern, text, flags=re.IGNORECASE), pattern
