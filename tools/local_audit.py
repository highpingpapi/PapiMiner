from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1]
LOCAL_DIR = APP_DIR / "local"
TEST_RUN_DIR = LOCAL_DIR / "test-runs"
DEFAULT_CONSOLE = "http://127.0.0.1:8788"
PRIVATE_PATTERNS = {
    "pearl_address_shape": re.compile(r"prl1[0-9a-z]{10,}", re.IGNORECASE),
    "private_lan_ip": re.compile(r"192\.168\."),
    "windows_user_path": re.compile(r"C:\\Users", re.IGNORECASE),
    "windows_profile_data_dir": re.compile("App" + "Data", re.IGNORECASE),
    "codex_workspace_path": re.compile(r"Documents\\Codex", re.IGNORECASE),
    "exchange_name": re.compile("Safe" + "Trade", re.IGNORECASE),
    "wallet_app_name": re.compile("Pearl " + "Wallet", re.IGNORECASE),
}
LOCAL_PRIVATE_TERMS = LOCAL_DIR / "private_terms.local.txt"
TEXT_SUFFIXES = {
    ".c",
    ".cmd",
    ".cpp",
    ".css",
    ".cu",
    ".cuh",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".txt",
    ".yml",
    ".yaml",
}

LOCAL_ONLY_GLOBS = {
    "docs/*.private.md",
    "docs/*candidate*.md",
    "docs/papiminer-akoya-*.md",
    "references/**/*.pdf",
    "references/papers/*.pdf",
}


def request_json(url: str, timeout: float = 5.0) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}, None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, str(exc)


def load_json(path: Path) -> tuple[Any, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def should_scan(path: Path) -> bool:
    rel = path.relative_to(APP_DIR)
    if rel.parts and rel.parts[0] == "local":
        return False
    if "__pycache__" in rel.parts:
        return False
    if ".pytest_cache" in rel.parts:
        return False
    rel_posix = rel.as_posix()
    if any(Path(rel_posix).match(pattern) for pattern in LOCAL_ONLY_GLOBS):
        return False
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    return True


def privacy_scan() -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    patterns = dict(PRIVATE_PATTERNS)
    if LOCAL_PRIVATE_TERMS.exists():
        for index, raw_term in enumerate(LOCAL_PRIVATE_TERMS.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            term = raw_term.strip()
            if term and not term.startswith("#"):
                patterns[f"local_private_term_{index}"] = re.compile(re.escape(term), re.IGNORECASE)
    for path in APP_DIR.rglob("*"):
        if not path.is_file() or not should_scan(path):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            hits.append({"file": str(path.relative_to(APP_DIR)), "error": str(exc)})
            continue
        for line_no, line in enumerate(lines, start=1):
            for name, pattern in patterns.items():
                if pattern.search(line):
                    hits.append({
                        "file": str(path.relative_to(APP_DIR)),
                        "line": line_no,
                        "pattern": name,
                    })
    return hits


def model_rows(registry: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in (registry or {}).get("models", []):
        integrity = item.get("integrity") or {}
        rows.append({
            "id": item.get("id"),
            "exists": item.get("exists"),
            "complete": integrity.get("complete"),
            "reason": integrity.get("reason"),
            "weight_files": integrity.get("weight_files"),
            "weight_bytes": integrity.get("weight_bytes"),
        })
    return rows


def latest_artifacts(limit: int = 20) -> list[dict[str, Any]]:
    if not TEST_RUN_DIR.exists():
        return []
    files = sorted(
        [path for path in TEST_RUN_DIR.iterdir() if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    rows = []
    for path in files[:limit]:
        stat = path.stat()
        rows.append({
            "name": path.name,
            "bytes": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    return rows


def artifact_coverage(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    names = [item["name"] for item in artifacts]
    return {
        "smoke_latest": next((name for name in names if name.startswith("smoke-")), None),
        "plain_pool_test": next((name for name in names if name.startswith("plain-pool-test-")), None),
        "llama31_useful": next((name for name in names if "llama31-8b" in name), None),
        "gemma31_attempt": next((name for name in names if "gemma31b" in name), None),
        "tinyllama_windows_path": next((name for name in names if "tinyllama-windows-path" in name), None),
        "tinyllama_short_id": next((name for name in names if "tinyllama-short-id" in name), None),
        "large_model_attempts": next((name for name in names if name.startswith("large-model-attempts-")), None),
        "matrix": next((name for name in names if name.startswith("papiminer-test-matrix-")), None),
    }


def build_report(console_base: str) -> dict[str, Any]:
    console_base = console_base.rstrip("/")
    status, status_error = request_json(f"{console_base}/api/status")
    runtime, runtime_error = request_json(f"{console_base}/api/runtime/status")
    registry, registry_error = load_json(LOCAL_DIR / "models.local.json")
    profiles, profiles_error = load_json(LOCAL_DIR / "run-profiles.local.json")
    artifacts = latest_artifacts()
    privacy_hits = privacy_scan()

    complete_models = [row for row in model_rows(registry) if row.get("complete") is True]
    incomplete_models = [row for row in model_rows(registry) if row.get("complete") is not True]
    running = [
        {
            "profile_id": item.get("profile_id"),
            "kind": item.get("kind"),
            "backend": item.get("backend"),
            "gpu": item.get("gpu"),
            "status": item.get("status"),
            "running": item.get("running"),
        }
        for item in (runtime or {}).get("processes", [])
    ]

    return {
        "ok": not privacy_hits and status_error is None,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "console_base": console_base,
        "status_error": status_error,
        "runtime_error": runtime_error,
        "registry_error": registry_error,
        "profiles_error": profiles_error,
        "control_online": status_error is None,
        "vllm_online": bool((status or {}).get("health", {}).get("online")),
        "served_models": (status or {}).get("models", []),
        "gpu": (status or {}).get("gpu", []),
        "runtime_processes": running,
        "model_registry": {
            "complete_count": len(complete_models),
            "incomplete_count": len(incomplete_models),
            "models": model_rows(registry),
        },
        "run_profiles_count": len((profiles or {}).get("profiles", [])) if isinstance(profiles, dict) else 0,
        "latest_artifacts": artifacts,
        "artifact_coverage": artifact_coverage(artifacts),
        "privacy_scan": {
            "excluded": "local/, ignored raw lab notes, downloaded references, cache/artifacts",
            "hits": privacy_hits,
        },
        "remaining_gaps": [
            "Qwen3 30B and Gemma 31B still need successful runtime/chat evidence",
            "Llama 3.3 70B download is incomplete",
            "Actual PRL/day requires a longer pool-connected payout/share window",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a local PapiMiner audit report.")
    parser.add_argument("--console-base", default=DEFAULT_CONSOLE)
    parser.add_argument("--output", help="Output JSON path. Defaults to local/test-runs with a timestamp.")
    args = parser.parse_args()

    report = build_report(args.console_base)
    TEST_RUN_DIR.mkdir(parents=True, exist_ok=True)
    output = Path(args.output) if args.output else TEST_RUN_DIR / f"papiminer-local-audit-{datetime.now():%Y%m%d-%H%M%S}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": report["ok"],
        "output": str(output),
        "control_online": report["control_online"],
        "vllm_online": report["vllm_online"],
        "served_models": report["served_models"],
        "privacy_hits": len(report["privacy_scan"]["hits"]),
        "complete_models": report["model_registry"]["complete_count"],
        "incomplete_models": report["model_registry"]["incomplete_count"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
