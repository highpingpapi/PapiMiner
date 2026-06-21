from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "kernel_lab" / "akoya_capi_contract.json"
STUB_H = ROOT / "kernel_lab" / "minimal_capi" / "pearl_gemm_capi_stub.h"
STUB_CPP = ROOT / "kernel_lab" / "minimal_capi" / "pearl_gemm_capi_stub.cpp"


def test_minimal_capi_stub_exports_required_symbols() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    stub_text = STUB_H.read_text(encoding="utf-8") + "\n" + STUB_CPP.read_text(encoding="utf-8")

    for symbol in contract["required_symbols"]:
        assert re.search(rf"\b{re.escape(symbol)}\b", stub_text), symbol


def test_contract_stays_plain_only() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert contract["library"] == "libpearl_gemm_capi"
    assert contract["abi_version"] == 2
    assert "AI inference scheduling" in contract["non_goals"]
    assert "wallet handling" in contract["non_goals"]


def test_akoya_candidate_matrix_has_next_hot_path_candidate() -> None:
    manifest = json.loads((ROOT / "kernel_lab" / "candidates.json").read_text(encoding="utf-8"))
    hot = [
        item for item in manifest["candidates"]
        if item.get("kind") == "akoya_hot_path_candidate"
    ]

    assert hot
    assert any(item["status"] == "next" for item in hot)
    for item in hot:
        assert item["build_env"]["PEARL_GEMM_ARCH"] == "ada"
        assert "same-window" in " ".join(item["gates"])
