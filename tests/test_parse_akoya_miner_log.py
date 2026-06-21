from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_parser():
    path = Path(__file__).resolve().parents[1] / "tools" / "parse_akoya_miner_log.py"
    spec = importlib.util.spec_from_file_location("parse_akoya_miner_log", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_akoya_log_handles_utf16_and_two_gpu_metrics(tmp_path: Path) -> None:
    parser = _load_parser()
    log = tmp_path / "akoya.log"
    log.write_text(
        "\n".join(
            [
                "benchmark[0]: 150 iters in 3.18s -> 47.17 iters/s, 103.74 TMADs/s, hashes/s=103.74 TH/s",
                "mine-profile: auto-selected ada-gpu",
                "worker[0]: starting on device ordinal=0 uuid=box:0:Generic CUDA GPU",
                "worker[0] [stats] iters/s=48.87 iter_ms=20.5 tiles/s=2.05E+008 tmads/s=107.47 hashes/s=107.47 TH/s triggers=1 shares=1",
                "metric cpuPct=100 rssMB=282 gpu0=11%/29C/39W gpu1=100%/62C/99W",
                "pearl-capi-timing seed=42 lcg_ms=0.2500 tensor_hash_ms=1.5000 commit_ms=0.0500 noise_a_ms=0.7500 noisy_gemm_ms=18.0000 total_ms=20.5500",
                "session: ✓ share on wire seq=5 tile=(3047,72448)",
                "share-result hash=abc accepted=True outcome=Accepted",
            ]
        ),
        encoding="utf-16",
    )

    summary = parser.parse_log(log)

    assert summary["benchmark_ths"]["avg"] == 103.74
    assert summary["steady_ths"]["avg"] == 107.47
    assert summary["shares"]["accepted"] == 1
    assert summary["shares"]["rejected"] == 0
    assert summary["gpu_metrics"]["gpu0"]["max_power_w"] == 39
    assert summary["gpu_metrics"]["gpu1"]["max_temp_c"] == 62
    assert summary["akoya_profiles"] == ["ada-gpu"]
    assert summary["worker_devices"][0]["name"] == "Generic CUDA GPU"
    assert summary["capi_timing"]["total_ms"]["avg"] == 20.55
    assert summary["capi_timing"]["noisy_gemm_ms"]["avg"] == 18.0
