#!/usr/bin/env python3
"""Summarize Akoya miner logs into a benchmark evidence JSON.

The parser intentionally avoids emitting wallet addresses or worker labels.
It only extracts performance, share, and GPU telemetry evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any


BENCH_RE = re.compile(
    r"benchmark\[(?P<gpu>\d+)\]: .*?hashes/s=(?P<ths>[0-9.]+)\s+TH/s"
)
STATS_RE = re.compile(
    r"worker\[(?P<gpu>\d+)\].*?\[stats\].*?"
    r"iters/s=(?P<iters>[0-9.]+).*?"
    r"iter_ms=(?P<iter_ms>[0-9.]+).*?"
    r"tmads/s=(?P<tmads>[0-9.]+).*?"
    r"hashes/s=(?P<ths>[0-9.]+)\s+TH/s.*?"
    r"triggers=(?P<triggers>\d+)\s+shares=(?P<shares>\d+)"
)
SHARE_RESULT_RE = re.compile(
    r"share-result .*?accepted=(?P<accepted>True|False).*?outcome=(?P<outcome>\w+)"
)
SHARE_WIRE_RE = re.compile(r"session: . share on wire")
GPU_METRIC_RE = re.compile(
    r"(?P<gpu>gpu\d+)=(?P<util>\d+)%/(?P<temp>\d+)(?:[^\d/])?C/(?P<power>\d+)W"
)
AUTO_PROFILE_RE = re.compile(r"mine-profile: auto-selected (?P<profile>[\w-]+)")
WORKER_DEVICE_RE = re.compile(
    r"worker\[(?P<worker_gpu>\d+)\]: starting on device ordinal=(?P<ordinal>\d+) "
    r"uuid=.*?:(?P<cuda_gpu>\d+):(?P<name>.+)$"
)
ERROR_RE = re.compile(r"\b(error|exception)\b", re.IGNORECASE)
TIMING_RE = re.compile(
    r"pearl-capi-timing .*?"
    r"lcg_ms=(?P<lcg>[0-9.]+)\s+"
    r"tensor_hash_ms=(?P<tensor_hash>[0-9.]+)\s+"
    r"commit_ms=(?P<commit>[0-9.]+)\s+"
    r"noise_a_ms=(?P<noise_a>[0-9.]+)\s+"
    r"noisy_gemm_ms=(?P<noisy_gemm>[0-9.]+).*?"
    r"total_ms=(?P<total>[0-9.]+)"
)


def _read_log_lines(path: Path) -> list[str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")

    # PowerShell-captured WSL diagnostics can contain embedded NUL bytes.
    # Removing them keeps normal Akoya log lines parseable without touching
    # semantic text such as hashes, shares, or GPU metrics.
    lines = [line.replace("\x00", "") for line in text.splitlines()]
    logical: list[str] = []
    pending_timing: str | None = None
    for line in lines:
        stripped = line.strip()
        if pending_timing is not None:
            pending_timing += stripped
            if "otal_ms=" in pending_timing:
                logical.append(pending_timing)
                pending_timing = None
            continue

        if "pearl-capi-timing" in stripped and "otal_ms=" not in stripped:
            pending_timing = stripped
            continue

        logical.append(line)

    if pending_timing is not None:
        logical.append(pending_timing)

    return logical


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return round(ordered[idx], 4)


def _float_stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "p50": None, "p95": None, "max": None, "avg": None, "last": None}
    return {
        "min": round(min(values), 4),
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "max": round(max(values), 4),
        "avg": round(statistics.fmean(values), 4),
        "last": round(values[-1], 4),
    }


def parse_log(path: Path) -> dict[str, Any]:
    benchmark_ths: list[float] = []
    steady_ths: list[float] = []
    iter_ms: list[float] = []
    iters_s: list[float] = []
    shares_on_wire = 0
    accepted = 0
    rejected = 0
    outcomes: dict[str, int] = {}
    gpu_metrics: dict[str, dict[str, Any]] = {}
    profiles: list[str] = []
    devices: list[dict[str, str | int]] = []
    error_lines: list[str] = []
    capi_timing: dict[str, list[float]] = {
        "lcg_ms": [],
        "tensor_hash_ms": [],
        "commit_ms": [],
        "noise_a_ms": [],
        "noisy_gemm_ms": [],
        "total_ms": [],
    }

    for raw_line in _read_log_lines(path):
        line = raw_line.strip()

        bench = BENCH_RE.search(line)
        if bench:
            benchmark_ths.append(float(bench.group("ths")))

        stats = STATS_RE.search(line)
        if stats:
            steady_ths.append(float(stats.group("ths")))
            iter_ms.append(float(stats.group("iter_ms")))
            iters_s.append(float(stats.group("iters")))

        if SHARE_WIRE_RE.search(line):
            shares_on_wire += 1

        share = SHARE_RESULT_RE.search(line)
        if share:
            outcome = share.group("outcome")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            if share.group("accepted") == "True":
                accepted += 1
            else:
                rejected += 1

        for metric in GPU_METRIC_RE.finditer(line):
            gpu = metric.group("gpu")
            item = gpu_metrics.setdefault(
                gpu,
                {"samples": 0, "max_temp_c": None, "max_power_w": None, "max_util_pct": None},
            )
            item["samples"] += 1
            for key, value in (
                ("max_temp_c", int(metric.group("temp"))),
                ("max_power_w", int(metric.group("power"))),
                ("max_util_pct", int(metric.group("util"))),
            ):
                item[key] = value if item[key] is None else max(item[key], value)

        profile = AUTO_PROFILE_RE.search(line)
        if profile:
            name = profile.group("profile")
            if name not in profiles:
                profiles.append(name)

        device = WORKER_DEVICE_RE.search(line)
        if device:
            devices.append(
                {
                    "worker_gpu": int(device.group("worker_gpu")),
                    "device_ordinal": int(device.group("ordinal")),
                    "cuda_gpu": int(device.group("cuda_gpu")),
                    "name": device.group("name").strip(),
                }
            )

        timing = TIMING_RE.search(line)
        if timing:
            capi_timing["lcg_ms"].append(float(timing.group("lcg")))
            capi_timing["tensor_hash_ms"].append(float(timing.group("tensor_hash")))
            capi_timing["commit_ms"].append(float(timing.group("commit")))
            capi_timing["noise_a_ms"].append(float(timing.group("noise_a")))
            capi_timing["noisy_gemm_ms"].append(float(timing.group("noisy_gemm")))
            capi_timing["total_ms"].append(float(timing.group("total")))

        if ERROR_RE.search(line) and len(error_lines) < 8:
            error_lines.append(line)

    return {
        "source_log": str(path),
        "benchmark_ths": _float_stats(benchmark_ths),
        "steady_ths": _float_stats(steady_ths),
        "iter_ms": _float_stats(iter_ms),
        "iters_s": _float_stats(iters_s),
        "shares": {
            "on_wire": shares_on_wire,
            "accepted": accepted,
            "rejected": rejected,
            "outcomes": outcomes,
        },
        "gpu_metrics": gpu_metrics,
        "akoya_profiles": profiles,
        "worker_devices": devices,
        "capi_timing": {key: _float_stats(values) for key, values in capi_timing.items()},
        "errors_sample": error_lines,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize an Akoya miner log.")
    parser.add_argument("log", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    summary = parse_log(args.log)
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
