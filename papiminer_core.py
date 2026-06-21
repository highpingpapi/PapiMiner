#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import mimetypes
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from typing import Any


DEFAULT_API_BASE = (
    os.environ.get("PAPIMINER_API_BASE")
    or os.environ.get("PapiMiner_API_BASE")
    or "http://127.0.0.1:8001"
).rstrip("/")
USER_AGENT = "PapiMiner/0.1 local-cli"
APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"
LOCAL_DIR = APP_DIR / "local"
MODEL_REGISTRY_PATH = Path(
    os.environ.get("PAPIMINER_MODEL_REGISTRY")
    or LOCAL_DIR / "models.local.json"
)
SETTINGS_PATH = Path(
    os.environ.get("PAPIMINER_SETTINGS")
    or LOCAL_DIR / "settings.local.json"
)
RUN_PROFILES_PATH = Path(
    os.environ.get("PAPIMINER_RUN_PROFILES")
    or LOCAL_DIR / "run-profiles.local.json"
)
RUNTIME_STATE_PATH = Path(
    os.environ.get("PAPIMINER_RUNTIME_STATE")
    or LOCAL_DIR / "runtime.local.json"
)
RUN_LOG_DIR = LOCAL_DIR / "run-logs"
BACKGROUND_DIR = LOCAL_DIR / "backgrounds"
MONITOR_SCRIPT_PATH = APP_DIR / "tools" / "monitor_runtime.ps1"
MODEL_FILE_PATTERNS = ("*.safetensors", "*.gguf", "*.bin", "*.pt", "*.pth", "*.onnx")
MAX_BACKGROUND_BYTES = 80 * 1024 * 1024


@dataclass
class HttpResult:
    ok: bool
    status: int | None
    text: str
    error: str | None = None


def request_text(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 4.0) -> HttpResult:
    data = None
    headers = {"User-Agent": USER_AGENT}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            return HttpResult(ok=200 <= resp.status < 300, status=resp.status, text=text)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return HttpResult(ok=False, status=exc.code, text=body, error=f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        return HttpResult(ok=False, status=None, text="", error=str(exc.reason))
    except TimeoutError:
        return HttpResult(ok=False, status=None, text="", error="timeout")


def get_json(base: str, path: str, timeout: float = 4.0) -> tuple[dict[str, Any] | None, HttpResult]:
    result = request_text("GET", f"{base}{path}", timeout=timeout)
    if not result.ok:
        return None, result
    try:
        return json.loads(result.text), result
    except json.JSONDecodeError:
        return None, HttpResult(False, result.status, result.text, "not json")


def get_text(base: str, path: str, timeout: float = 4.0) -> HttpResult:
    return request_text("GET", f"{base}{path}", timeout=timeout)


def post_json(base: str, path: str, payload: dict[str, Any], timeout: float = 60.0) -> tuple[dict[str, Any] | None, HttpResult]:
    result = request_text("POST", f"{base}{path}", payload=payload, timeout=timeout)
    if not result.ok:
        return None, result
    try:
        return json.loads(result.text), result
    except json.JSONDecodeError:
        return None, HttpResult(False, result.status, result.text, "not json")


def parse_labels(raw: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    if not raw:
        return labels
    # Prometheus labels are simple key="value" pairs. This parser handles the
    # normal vLLM/Akoya output without adding another dependency.
    for match in re.finditer(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"', raw):
        labels[match.group(1)] = match.group(2).replace(r"\"", '"').replace(r"\\", "\\")
    return labels


def parse_prometheus(text: str) -> dict[str, list[dict[str, Any]]]:
    metrics: dict[str, list[dict[str, Any]]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue
        series, value_raw = parts
        try:
            value = float(value_raw)
        except ValueError:
            continue
        if "{" in series and series.endswith("}"):
            name, label_raw = series.split("{", 1)
            labels = parse_labels(label_raw[:-1])
        else:
            name, labels = series, {}
        metrics.setdefault(name, []).append({"labels": labels, "value": value})
    return metrics


def first_metric(metrics: dict[str, list[dict[str, Any]]], name: str) -> float | None:
    samples = metrics.get(name)
    if not samples:
        return None
    return float(samples[0]["value"])


def sum_metric(metrics: dict[str, list[dict[str, Any]]], name: str) -> float | None:
    samples = metrics.get(name)
    if not samples:
        return None
    return sum(float(sample["value"]) for sample in samples)


def fmt_number(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "-"
    if abs(value) >= 1_000_000:
        return f"{value:,.0f}"
    if abs(value) >= 100:
        return f"{value:,.1f}"
    return f"{value:,.{digits}f}"


def fmt_hashrate(value: float | None) -> str:
    if value is None:
        return "-"
    units = [("EH/s", 1e18), ("PH/s", 1e15), ("TH/s", 1e12), ("GH/s", 1e9), ("MH/s", 1e6), ("H/s", 1.0)]
    for unit, scale in units:
        if abs(value) >= scale:
            return f"{value / scale:,.2f} {unit}"
    return f"{value:,.2f} H/s"


def section(title: str) -> None:
    print(f"\n== {title} ==")


def kv(label: str, value: str) -> None:
    print(f"{label:<28} {value}")


def get_models(base: str, timeout: float = 4.0) -> tuple[list[str], str | None]:
    data, result = get_json(base, "/v1/models", timeout=timeout)
    if not data:
        return [], result.error
    models = []
    for item in data.get("data", []):
        model_id = item.get("id")
        if model_id:
            models.append(str(model_id))
    return models, None


def get_metrics(base: str, timeout: float = 5.0) -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    result = get_text(base, "/metrics", timeout=timeout)
    if not result.ok:
        return {}, result.error or f"HTTP {result.status}"
    return parse_prometheus(result.text), None


def load_model_registry() -> tuple[dict[str, Any], str | None]:
    if not MODEL_REGISTRY_PATH.exists():
        return {"models": []}, None
    try:
        with MODEL_REGISTRY_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return {"models": []}, "registry root is not an object"
        models = data.get("models", [])
        if not isinstance(models, list):
            data["models"] = []
        return data, None
    except Exception as exc:
        return {"models": []}, str(exc)


def save_model_registry(registry: dict[str, Any]) -> None:
    MODEL_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    registry["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with MODEL_REGISTRY_PATH.open("w", encoding="utf-8") as handle:
        json.dump(registry, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(settings: dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with SETTINGS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def now_local() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def load_json_file(path: Path, default: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return dict(default), None
    try:
        # Accept UTF-8 with or without BOM because Windows PowerShell's
        # built-in JSON edits may emit a BOM.
        with path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return dict(default), "json root is not an object"
        return data, None
    except Exception as exc:
        return dict(default), str(exc)


def save_json_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = now_local()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def has_value(value: Any) -> bool:
    return value is not None and value != ""


def redact_wallet(value: str) -> str:
    text = str(value or "")
    match = re.search(r"prl1[0-9a-z]{16,}", text, re.IGNORECASE)
    if not match:
        return text
    wallet = match.group(0)
    redacted = wallet[:10] + "..." + wallet[-8:]
    return text.replace(wallet, redacted)


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_sensitive(val) for key, val in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return redact_wallet(value)
    return value


def privacy_hits(entry: dict[str, Any]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    sensitive_keys = ("wallet", "worker", "path", "cwd", "log", "host", "machine", "account")
    for key, value in entry.items():
        key_l = str(key).lower()
        if key_l.endswith("_exists"):
            continue
        if any(marker in key_l for marker in sensitive_keys):
            hits.append({
                "field": str(key),
                "policy": "local-only",
                "reason": "wallet/worker/path/machine style field",
            })
            continue
        if isinstance(value, str) and re.search(r"prl1[0-9a-z]{16,}", value, re.IGNORECASE):
            hits.append({"field": str(key), "policy": "local-only", "reason": "Pearl address detected"})
    return hits


def windows_to_wsl_path(path_text: str) -> str:
    raw = str(path_text or "").strip()
    if raw.startswith("/"):
        return raw
    text = str(Path(path_text).expanduser())
    match = re.match(r"^([a-zA-Z]):[\\/](.*)$", text)
    if not match:
        return text.replace("\\", "/")
    drive = match.group(1).lower()
    rest = match.group(2).replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def default_run_profiles() -> list[dict[str, Any]]:
    plain_cwd = APP_DIR.parent / "upstream-akoya-miner" / "out"
    vllm_cwd = APP_DIR.parent / "upstream-akoya-vllm-miner"
    vllm_run_dir = APP_DIR.parent / "akoya-vllm-run"
    return [
        {
            "id": "akoya-plain-default",
            "label": "Akoya Plain Miner",
            "label_zh": "Akoya Plain 挖矿",
            "kind": "plain",
            "backend": "akoya_plain",
            "source": "builtin",
            "audit": "open-source upstream",
            "path": str(plain_cwd / "akoya-miner"),
            "cwd": str(plain_cwd),
            "gpu": "1",
            "akoya_gpu_indices": "0",
            "pool_host": "pool-v2.akoyapool.com",
            "pool_port": "443",
            "pool_tls": True,
            "wallet_address": "",
            "worker": "PapiMiner-plain",
            "log_dir": str(RUN_LOG_DIR / "akoya-plain-default"),
            "notes": "Open-source Akoya plain miner. Edit the local profile to match your own GPU ordinals and pool settings.",
        },
        {
            "id": "akoya-vllm-local",
            "label": "Akoya vLLM Useful Work",
            "label_zh": "Akoya vLLM 有用工作",
            "kind": "useful",
            "backend": "akoya_vllm",
            "source": "builtin",
            "audit": "open-source upstream",
            "path": str(vllm_cwd / "run.py"),
            "cwd": str(vllm_cwd),
            "run_dir": str(vllm_run_dir),
            "gpu": "0",
            "model": "",
            "wallet_address": "",
            "worker": "PapiMiner-useful",
            "connect_pool": True,
            "pool_routed": False,
            "api_host": "127.0.0.1",
            "api_port": 8001,
            "max_model_len": 1024,
            "max_num_batched_tokens": 1024,
            "tensor_parallel_size": 1,
            "gpu_memory_utilization": 0.82,
            "vllm_args": ["--enforce-eager"],
            "log_dir": str(RUN_LOG_DIR / "akoya-vllm-local"),
            "notes": "Useful-work miner. Pool-routed inference is optional and disabled by default. Defaults favor fast local WSL startup; edit local profile for full benchmark runs.",
        },
    ]


def normalize_profile(entry: dict[str, Any], origin: str = "local") -> dict[str, Any]:
    profile = dict(entry)
    profile.setdefault("id", f"profile-{len(str(profile))}")
    profile.setdefault("label", profile["id"])
    profile.setdefault("label_zh", profile.get("label", profile["id"]))
    profile.setdefault("kind", "custom")
    profile.setdefault("backend", "custom")
    profile.setdefault("source", origin)
    profile.setdefault("gpu", "")
    profile.setdefault("log_dir", str(RUN_LOG_DIR / str(profile["id"])))
    path_text = str(profile.get("path", "")).strip()
    cwd_text = str(profile.get("cwd", "")).strip()
    run_dir_text = str(profile.get("run_dir", "")).strip()
    profile["path_exists"] = bool(path_text and Path(path_text).expanduser().exists())
    profile["cwd_exists"] = bool(cwd_text and Path(cwd_text).expanduser().exists())
    profile["run_dir_exists"] = bool(run_dir_text and Path(run_dir_text).expanduser().exists())
    profile["privacy"] = privacy_hits(profile)
    profile["redacted"] = redact_sensitive(profile)
    return profile


def local_profile_has_runtime(entry: dict[str, Any]) -> bool:
    if not isinstance(entry, dict):
        return False
    runtime_fields = ("path", "command", "command_template")
    if any(str(entry.get(field) or "").strip() for field in runtime_fields):
        return True
    backend = str(entry.get("backend") or "").strip()
    return backend in {"akoya_plain", "akoya_vllm"}


def load_run_profile_store() -> tuple[dict[str, Any], str | None]:
    data, error = load_json_file(RUN_PROFILES_PATH, {"profiles": []})
    if not isinstance(data.get("profiles"), list):
        data["profiles"] = []
    return data, error


def run_profiles_payload() -> dict[str, Any]:
    local_store, error = load_run_profile_store()
    by_id: dict[str, dict[str, Any]] = {}
    for profile in default_run_profiles():
        by_id[str(profile["id"])] = normalize_profile(profile, "builtin")
    for profile in local_store.get("profiles", []):
        if isinstance(profile, dict) and local_profile_has_runtime(profile):
            by_id[str(profile.get("id") or profile.get("label") or "custom")] = normalize_profile(profile, "local")
    return {
        "profiles_path": str(RUN_PROFILES_PATH),
        "profiles": list(by_id.values()),
        "error": error,
    }


def upsert_run_profile(profile: dict[str, Any]) -> dict[str, Any]:
    store, _ = load_run_profile_store()
    profile = dict(profile)
    profile.setdefault("source", "local")
    normalized = normalize_profile(profile, "local")
    existing = [item for item in store.get("profiles", []) if isinstance(item, dict)]
    by_id = {str(item.get("id")): item for item in existing}
    by_id[str(normalized["id"])] = {key: value for key, value in profile.items() if key not in {"redacted", "privacy"}}
    store["profiles"] = list(by_id.values())
    save_json_file(RUN_PROFILES_PATH, store)
    return normalized


def profile_by_id(profile_id: str) -> dict[str, Any] | None:
    for profile in run_profiles_payload()["profiles"]:
        if profile.get("id") == profile_id:
            return profile
    return None


def import_summary_payload() -> dict[str, Any]:
    registry, registry_error = load_model_registry()
    profiles = run_profiles_payload()
    return {
        "model_registry_path": str(MODEL_REGISTRY_PATH),
        "settings_path": str(SETTINGS_PATH),
        "run_profiles_path": str(RUN_PROFILES_PATH),
        "runtime_state_path": str(RUNTIME_STATE_PATH),
        "run_log_dir": str(RUN_LOG_DIR),
        "models": registry_models(registry),
        "model_registry_error": registry_error,
        "profiles": profiles["profiles"],
        "profiles_error": profiles.get("error"),
        "privacy_rules": [
            "wallet addresses are local-only",
            "worker names are local-only",
            "machine names, private IPs, and local paths are local-only",
            "seed phrases, private keys, and exchange passwords are never stored",
        ],
    }


def load_runtime_state() -> tuple[dict[str, Any], str | None]:
    data, error = load_json_file(RUNTIME_STATE_PATH, {"processes": {}})
    if not isinstance(data.get("processes"), dict):
        data["processes"] = {}
    return data, error


def save_runtime_state(state: dict[str, Any]) -> None:
    save_json_file(RUNTIME_STATE_PATH, state)


def pid_running(pid: int | str | None) -> bool:
    if not pid:
        return False
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid_int}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and f'"{pid_int}"' in result.stdout
    try:
        os.kill(pid_int, 0)
        return True
    except OSError:
        return False


def subprocess_message(result: subprocess.CompletedProcess[Any], fallback: str) -> str:
    stderr = result.stderr if isinstance(result.stderr, str) else ""
    stdout = result.stdout if isinstance(result.stdout, str) else ""
    return stderr.strip() or stdout.strip() or fallback


def stop_pid(pid: int | str) -> tuple[bool, str | None]:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False, "bad pid"
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid_int), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
        )
        if result.returncode != 0:
            return False, subprocess_message(result, "taskkill failed")
        return True, None
    try:
        os.kill(pid_int, 15)
        return True, None
    except OSError as exc:
        return False, str(exc)


def runtime_api_base(effective: dict[str, Any]) -> str:
    host = str(effective.get("api_host") or "127.0.0.1").strip()
    port = str(effective.get("api_port") or "8001").strip()
    if host in {"0.0.0.0", "::", "[::]"}:
        host = "127.0.0.1"
    if not host or not port:
        return ""
    return f"http://{host}:{port}"


def start_monitor_window(profile_id: str, backend: str, effective: dict[str, Any], log_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if os.name != "nt":
        return None, "monitor window is only implemented on Windows"
    if not MONITOR_SCRIPT_PATH.exists():
        return None, f"monitor script missing: {MONITOR_SCRIPT_PATH}"
    api_base = runtime_api_base(effective) if backend == "akoya_vllm" else ""
    monitor_title = f"PapiMiner Monitor - {profile_id}"
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-NoExit",
        "-File",
        str(MONITOR_SCRIPT_PATH),
        "-Title",
        monitor_title,
        "-LogPath",
        str(log_path),
        "-ApiBase",
        api_base,
        "-IntervalSec",
        "2",
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=str(APP_DIR),
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
    except OSError as exc:
        return None, str(exc)
    return {
        "pid": process.pid,
        "title": monitor_title,
        "api_base": api_base,
        "command_preview": command,
    }, None


def stop_profile_children(record: dict[str, Any]) -> tuple[bool, str | None]:
    backend = str(record.get("backend") or "")
    effective = record.get("effective") if isinstance(record.get("effective"), dict) else {}
    if backend == "akoya_plain":
        script = (
            "pkill -TERM -x akoya-miner 2>/dev/null || true; "
            "sleep 2; "
            "pkill -KILL -x akoya-miner 2>/dev/null || true"
        )
        try:
            result = subprocess.run(
                ["wsl", "-e", "bash", "-lc", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return False, str(exc)
        if result.returncode != 0:
            return False, subprocess_message(result, "wsl cleanup failed")
        return True, None
    if backend != "akoya_vllm":
        return True, None
    worker = str(effective.get("worker") or record.get("worker") or "").strip()
    port = str(effective.get("api_port") or "").strip()
    if not worker and not port:
        return True, None
    parts = [r"[a]koya_vllm_miner.runtime.openai_server"]
    if worker:
        parts.append(r"--worker[ =]" + re.escape(worker))
    if port:
        parts.append(r"--port[ =]" + re.escape(port))
    pattern = ".*".join(parts)
    script = (
        f"pkill -TERM -f {shlex.quote(pattern)} 2>/dev/null || true; "
        "sleep 2; "
        f"pkill -KILL -f {shlex.quote(pattern)} 2>/dev/null || true"
    )
    try:
        result = subprocess.run(
            ["wsl", "-e", "bash", "-lc", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if result.returncode != 0:
        return False, subprocess_message(result, "wsl cleanup failed")
    return True, None


def refresh_runtime_state() -> dict[str, Any]:
    state, error = load_runtime_state()
    changed = False
    for key, record in list(state.get("processes", {}).items()):
        if not isinstance(record, dict):
            continue
        running = pid_running(record.get("pid"))
        old_status = record.get("status")
        record["running"] = running
        record["status"] = "running" if running else "stopped"
        if old_status != record["status"]:
            record["stopped_at"] = now_local()
            changed = True
    state["state_error"] = error
    if changed:
        save_runtime_state(state)
    return state


def parse_local_time(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return time.mktime(time.strptime(text, fmt))
        except ValueError:
            continue
    return None


def tail_text(path_text: Any, max_bytes: int = 24_000) -> tuple[list[str], str | None]:
    path = Path(str(path_text or ""))
    if not path.exists() or not path.is_file():
        return [], "missing"
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            raw = handle.read()
        text = raw.decode("utf-8", errors="replace")
        return text.splitlines()[-80:], None
    except OSError as exc:
        return [], str(exc)


def runtime_stage_from_log(record: dict[str, Any], health: HttpResult | None, lines: list[str]) -> dict[str, Any]:
    joined = "\n".join(lines)
    lower = joined.lower()
    running = bool(record.get("running"))
    health_online = bool(health and health.ok)
    started_ts = parse_local_time(record.get("started_at"))
    age_seconds = int(max(0, time.time() - started_ts)) if started_ts else None
    has_job = "akoya job received" in lower
    has_coordinator = "pool coordinator started" in lower or "registered akoya vllm instance" in lower
    has_reserved = "inference stream reserved" in lower
    has_vllm_loading = (
        "vllm" in lower
        or "model_executor" in lower
        or "enginecore" in lower
        or "openai_server" in lower
    )
    def is_error_line(line: str) -> bool:
        lower_line = line.lower()
        if "resume failed" in lower_line and "falling back to register" in lower_line:
            return False
        return bool(re.search(
            r"\b(error|traceback|exception|failed|cannot allocate memory|out of memory|OutOfMemory|does not support gpu)\b",
            line,
            re.IGNORECASE,
        ))

    error_lines = [line for line in lines if is_error_line(line)]
    recent_lines = [redact_sensitive(line) for line in lines[-12:]]
    recent_error = redact_sensitive(error_lines[-1]) if error_lines else None

    if not running and recent_error:
        code = "stopped_error"
        title_zh = "运行已因错误停止"
        title_en = "Stopped with error"
        detail_zh = "后台进程已经退出，日志里留下了失败原因。"
        detail_en = "The background process exited and left an error in the log."
        action_zh = "按日志原因换模型、GPU 或参数后再启动。"
        action_en = "Change the model, GPU, or arguments based on the log before starting again."
        severity = "bad"
    elif not running:
        code = "stopped"
        title_zh = "已停止"
        title_en = "Stopped"
        detail_zh = "进程不在运行。"
        detail_en = "The process is not running."
        action_zh = "需要时重新启动。"
        action_en = "Start it again if needed."
        severity = "muted"
    elif recent_error:
        code = "error"
        title_zh = "启动/运行报错"
        title_en = "Runtime error"
        detail_zh = "日志里出现错误，需要先看最近错误。"
        detail_en = "The log contains an error. Check the latest error first."
        action_zh = "建议停止后按错误原因换 GPU、模型或参数再启动。"
        action_en = "Stop it, then adjust GPU/model/arguments based on the error."
        severity = "bad"
    elif health_online:
        code = "online"
        title_zh = "vLLM 已在线"
        title_en = "vLLM online"
        detail_zh = "模型服务已经能响应健康检查，可以开始本地对话。"
        detail_en = "The model server responds to health checks. You can chat now."
        action_zh = "发一个稍长的问题，然后观察 useful 证据卡和矿池侧 worker。"
        action_en = "Send a moderately long prompt, then watch the evidence card and pool worker."
        severity = "good"
    elif has_job and has_reserved:
        code = "pool_job_waiting_vllm"
        title_zh = "矿池 job 已到，等待 vLLM online"
        title_en = "Pool job received, waiting for vLLM"
        detail_zh = "Akoya 已给 mining job，本地推理流是 reserved，但 OpenAI/vLLM 端口还没起来。"
        detail_en = "Akoya has sent a mining job and local inference is reserved, but the OpenAI/vLLM port is not ready."
        action_zh = "先不要对话。若超过 2-3 分钟仍未 online，建议停掉并用单 GPU 重试小模型。"
        action_en = "Do not chat yet. If it stays offline for 2-3 minutes, stop and retry the small model on one GPU."
        severity = "warn"
    elif has_coordinator:
        code = "coordinator_started"
        title_zh = "Akoya 协调器已启动"
        title_en = "Akoya coordinator started"
        detail_zh = "矿池/本地协调层已启动，正在等待 job 或 vLLM 服务继续加载。"
        detail_en = "The pool/local coordinator is up and waiting for jobs or vLLM startup."
        action_zh = "继续等一会儿；如果长时间无新日志，再停止重试。"
        action_en = "Wait briefly; if the log stops moving, stop and retry."
        severity = "warn"
    elif has_vllm_loading:
        code = "vllm_loading"
        title_zh = "vLLM 正在加载"
        title_en = "vLLM loading"
        detail_zh = "后台进程还活着，正在加载 vLLM/模型。"
        detail_en = "The background process is alive and loading vLLM/model code."
        action_zh = "等健康检查变成 online 后再对话。"
        action_en = "Wait for health to become online before chatting."
        severity = "warn"
    else:
        code = "starting"
        title_zh = "正在启动"
        title_en = "Starting"
        detail_zh = "进程还活着，但还没有足够日志判断阶段。"
        detail_en = "The process is alive, but there is not enough log signal yet."
        action_zh = "等 30-60 秒，或查看日志尾部。"
        action_en = "Wait 30-60 seconds or inspect the log tail."
        severity = "warn"

    return {
        "code": code,
        "severity": severity,
        "title": title_zh,
        "title_en": title_en,
        "detail": detail_zh,
        "detail_en": detail_en,
        "next_action": action_zh,
        "next_action_en": action_en,
        "age_seconds": age_seconds,
        "health_online": health_online,
        "health_error": None if health_online else (health.error if health else None),
        "has_pool_job": has_job,
        "has_coordinator": has_coordinator,
        "has_reserved_inference": has_reserved,
        "recent_error": recent_error,
        "recent_log": recent_lines,
    }


def runtime_status_payload(api_base: str | None = None, health: HttpResult | None = None) -> dict[str, Any]:
    state = refresh_runtime_state()
    base = (api_base or DEFAULT_API_BASE).rstrip("/")
    if health is None:
        health = get_text(base, "/health", timeout=0.5)
    processes = []
    for profile_id, record in state.get("processes", {}).items():
        if isinstance(record, dict):
            profile = profile_by_id(str(record.get("profile_id") or profile_id))
            row = dict(record)
            row["profile"] = profile["redacted"] if profile else None
            log_lines, log_error = tail_text(record.get("log_path"))
            row["diagnostic"] = runtime_stage_from_log(record, health, log_lines)
            row["log_tail_error"] = log_error
            processes.append(redact_sensitive(row))
    return {
        "runtime_state_path": str(RUNTIME_STATE_PATH),
        "run_log_dir": str(RUN_LOG_DIR),
        "api_base": base,
        "health": {
            "online": bool(health.ok),
            "status": health.status,
            "error": health.error,
        },
        "processes": processes,
        "error": state.get("state_error"),
    }


def parse_pool_host_port(host: str, port: str | int | None) -> tuple[str, str]:
    host_text = str(host or "pool-v2.akoyapool.com").strip()
    host_text = re.sub(r"^(grpcs?|stratum2?\+tcp|tcp)://", "", host_text)
    if ":" in host_text:
        left, right = host_text.rsplit(":", 1)
        if right.isdigit():
            return left, right
    return host_text, str(port or "443")


def shell_env(exports: dict[str, Any]) -> str:
    return " ".join(f"{key}={shlex.quote(str(value))}" for key, value in exports.items() if has_value(value))


def runtime_env_overrides(effective: dict[str, Any]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for field in ("env", "environment", "extra_env"):
        raw = effective.get(field)
        if not isinstance(raw, dict):
            continue
        for key, value in raw.items():
            name = str(key or "").strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                continue
            if has_value(value):
                merged[name] = str(value)
    return merged


def extend_cli_option(args: list[str], flag: str, value: Any) -> None:
    if has_value(value):
        args.extend([flag, shlex.quote(str(value))])


def extend_cli_extra(args: list[str], value: Any) -> None:
    if not has_value(value):
        return
    if isinstance(value, list):
        args.extend(shlex.quote(str(item)) for item in value if has_value(item))
        return
    if isinstance(value, str):
        args.extend(shlex.split(value))
        return
    args.append(shlex.quote(str(value)))


def parse_gpu_selector(value: Any) -> set[str]:
    text = str(value or "").strip().lower()
    if not text:
        return set()
    if text in {"all", "*"}:
        return {"*"}
    selected: set[str] = set()
    for token in re.split(r"[,\s]+", text):
        token = token.strip()
        if not token:
            continue
        if token in {"all", "*"}:
            selected.add("*")
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            if start_text.isdigit() and end_text.isdigit():
                start, end = int(start_text), int(end_text)
                if start <= end and end - start <= 32:
                    selected.update(str(index) for index in range(start, end + 1))
                    continue
        selected.add(token)
    return selected


def gpu_selectors_overlap(left: Any, right: Any) -> bool:
    left_set = parse_gpu_selector(left)
    right_set = parse_gpu_selector(right)
    if not left_set or not right_set:
        return False
    if "*" in left_set or "*" in right_set:
        return True
    return bool(left_set & right_set)


def build_runtime_command(profile: dict[str, Any], overrides: dict[str, Any]) -> tuple[list[str] | None, dict[str, Any], str | None]:
    backend = str(profile.get("backend", "custom"))
    effective = {**profile, **{key: value for key, value in overrides.items() if has_value(value)}}
    if backend == "akoya_vllm":
        selected_gpus = parse_gpu_selector(effective.get("gpu") or "0")
        gpu_count = 0 if "*" in selected_gpus else len(selected_gpus)
        explicit_tp = has_value(overrides.get("tensor_parallel_size"))
        current_tp = str(effective.get("tensor_parallel_size") or "").strip()
        if gpu_count > 1 and not explicit_tp and current_tp in {"", "1"}:
            effective["tensor_parallel_size"] = str(gpu_count)
    cwd = str(effective.get("cwd") or "")
    if not cwd:
        return None, effective, "profile cwd is required"
    if backend == "akoya_plain":
        wallet = str(effective.get("wallet_address") or "").strip()
        if not wallet:
            return None, effective, "wallet_address is required for pool mining"
        host, port = parse_pool_host_port(str(effective.get("pool_host") or ""), effective.get("pool_port"))
        exports = {
            "AKOYA_POOL_WALLET": wallet,
            "AKOYA_POOL_WORKER": effective.get("worker") or "PapiMiner",
            "AKOYA_POOL_HOST": host,
            "AKOYA_POOL_PORT": port,
            "AKOYA_POOL_TLS": "1" if truthy(effective.get("pool_tls", True)) else "0",
            "AKOYA_GPU_INDICES": effective.get("akoya_gpu_indices") or effective.get("gpu") or "0",
        }
        exports.update(runtime_env_overrides(effective))
        command = f"cd {shlex.quote(windows_to_wsl_path(cwd))} && env {shell_env(exports)} ./akoya-miner mine-blocks"
        return ["wsl", "-e", "bash", "-lc", command], effective, None
    if backend == "akoya_vllm":
        model = str(effective.get("model") or "").strip()
        if not model:
            return None, effective, "model is required for useful work"
        model_arg = windows_to_wsl_path(model)
        no_pool = truthy(effective.get("no_pool")) or not truthy(effective.get("connect_pool", True))
        args = ["python3", "./run.py", "--model", shlex.quote(model_arg)]
        if no_pool:
            args.append("--no-pool")
        else:
            wallet = str(effective.get("wallet_address") or "").strip()
            if not wallet:
                return None, effective, "wallet_address is required unless no_pool is enabled"
            args.extend(["--wallet", shlex.quote(wallet), "--worker", shlex.quote(str(effective.get("worker") or "PapiMiner"))])
            if truthy(effective.get("pool_routed")):
                args.extend(["--inference-stream-mode", "pool"])
            else:
                args.extend(["--inference-stream-mode", "reserved"])
        host = str(effective.get("api_host") or "127.0.0.1")
        port = str(effective.get("api_port") or "8001")
        args.extend(["--host", shlex.quote(host), "--port", shlex.quote(port)])
        extend_cli_option(args, "--max-model-len", effective.get("max_model_len"))
        extend_cli_option(args, "--gpu-memory-utilization", effective.get("gpu_memory_utilization"))
        extend_cli_option(args, "--max-num-batched-tokens", effective.get("max_num_batched_tokens"))
        extend_cli_option(args, "--max-num-seqs", effective.get("max_num_seqs"))
        args.append("--")
        extend_cli_option(args, "--tensor-parallel-size", effective.get("tensor_parallel_size"))
        extend_cli_extra(args, effective.get("vllm_args") or effective.get("extra_vllm_args"))
        exports = {
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "CUDA_VISIBLE_DEVICES": effective.get("gpu") or "0",
        }
        exports.update(runtime_env_overrides(effective))
        run_dir = str(effective.get("run_dir") or "").strip()
        if run_dir:
            exports["RUN_DIR"] = windows_to_wsl_path(run_dir)
        command = f"cd {shlex.quote(windows_to_wsl_path(cwd))} && env {shell_env(exports)} {' '.join(args)}"
        return ["wsl", "-e", "bash", "-lc", command], effective, None
    template = str(effective.get("command") or "").strip()
    if not template:
        return None, effective, "custom profile requires command"
    command = template.format(**{key: str(value) for key, value in effective.items()})
    if os.name == "nt":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], effective, None
    return ["bash", "-lc", command], effective, None


def start_runtime(profile_id: str, overrides: dict[str, Any]) -> tuple[dict[str, Any], int]:
    profile = profile_by_id(profile_id)
    if not profile:
        return {"ok": False, "error": f"profile not found: {profile_id}"}, 404
    state = refresh_runtime_state()
    requested_gpu = str(overrides.get("gpu") or profile.get("gpu") or "").strip()
    requested_kind = str(profile.get("kind") or "custom")
    for record in state.get("processes", {}).values():
        if not isinstance(record, dict) or not record.get("running"):
            continue
        same_gpu = gpu_selectors_overlap(requested_gpu, record.get("gpu"))
        same_kind = requested_kind in {"plain", "useful"} and str(record.get("kind")) in {"plain", "useful"}
        if same_gpu and same_kind and record.get("profile_id") != profile_id:
            return {
                "ok": False,
                "error": f"GPU(s) {requested_gpu} overlap with {record.get('profile_id')} on {record.get('gpu')}",
            }, 409
    command, effective, error = build_runtime_command(profile, overrides)
    if error or not command:
        return {"ok": False, "error": error or "could not build command"}, 400
    log_dir = Path(str(effective.get("log_dir") or (RUN_LOG_DIR / profile_id))).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"{profile_id}-{stamp}.log"
    with log_path.open("ab") as log_handle:
        log_handle.write(f"\n# PapiMiner start {now_local()}\n".encode("utf-8"))
        log_handle.write(f"# command {json.dumps(redact_sensitive(command), ensure_ascii=False)}\n".encode("utf-8"))
        process = subprocess.Popen(command, cwd=str(APP_DIR), stdout=log_handle, stderr=subprocess.STDOUT)
    monitor: dict[str, Any] | None = None
    monitor_error: str | None = None
    if truthy(effective.get("open_monitor")):
        monitor, monitor_error = start_monitor_window(profile_id, str(profile.get("backend") or ""), effective, log_path)
    record = {
        "profile_id": profile_id,
        "kind": requested_kind,
        "backend": profile.get("backend"),
        "pid": process.pid,
        "monitor_pid": monitor.get("pid") if monitor else None,
        "monitor": redact_sensitive(monitor) if monitor else None,
        "monitor_error": monitor_error,
        "running": True,
        "status": "running",
        "gpu": requested_gpu,
        "gpu_indices": sorted(parse_gpu_selector(requested_gpu)),
        "started_at": now_local(),
        "log_path": str(log_path),
        "command_preview": redact_sensitive(command),
        "effective": redact_sensitive(effective),
    }
    state.setdefault("processes", {})[profile_id] = record
    save_runtime_state(state)
    return {"ok": True, "process": record}, 200


def stop_runtime(profile_id: str) -> tuple[dict[str, Any], int]:
    state = refresh_runtime_state()
    record = state.get("processes", {}).get(profile_id)
    if not isinstance(record, dict):
        return {"ok": False, "error": f"profile is not running: {profile_id}"}, 404
    errors = []
    if record.get("running") and record.get("pid"):
        ok, error = stop_pid(record["pid"])
        if not ok:
            errors.append(error or "stop failed")
    if record.get("monitor_pid") and pid_running(record.get("monitor_pid")):
        ok, error = stop_pid(record["monitor_pid"])
        if not ok:
            errors.append(error or "monitor stop failed")
    child_ok, child_error = stop_profile_children(record)
    if not child_ok:
        errors.append(child_error or "child cleanup failed")
    if errors:
        return {"ok": False, "error": "; ".join(errors), "process": redact_sensitive(record)}, 500
    record["running"] = False
    record["status"] = "stopped"
    record["stopped_at"] = now_local()
    save_runtime_state(state)
    return {"ok": True, "process": redact_sensitive(record)}, 200


def configured_background_path() -> Path | None:
    settings = load_settings()
    theme = settings.get("theme", {})
    if not isinstance(theme, dict):
        return None
    path_text = str(theme.get("background_image_path", "")).strip()
    if not path_text:
        return None
    path = Path(path_text).expanduser()
    return path if path.exists() and path.is_file() else None


def theme_payload() -> dict[str, Any]:
    path = configured_background_path()
    if not path:
        return {
            "has_background": False,
            "background_url": None,
            "background_name": None,
            "settings_path": str(SETTINGS_PATH),
        }
    stat = path.stat()
    return {
        "has_background": True,
        "background_url": f"/api/background?v={int(stat.st_mtime)}",
        "background_name": path.name,
        "background_path": str(path),
        "settings_path": str(SETTINGS_PATH),
    }


def sanitize_filename(name: str, fallback: str = "background.png") -> str:
    name = Path(name).name.strip()
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    if not name or name in {".", ".."}:
        return fallback
    return name[:120]


def set_background_path(path_text: str) -> dict[str, Any]:
    path = Path(path_text).expanduser()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(path_text)
    settings = load_settings()
    theme = settings.get("theme", {})
    if not isinstance(theme, dict):
        theme = {}
    theme["background_image_path"] = str(path.resolve())
    settings["theme"] = theme
    save_settings(settings)
    return theme_payload()


def clear_background_path() -> dict[str, Any]:
    settings = load_settings()
    theme = settings.get("theme", {})
    if isinstance(theme, dict):
        theme.pop("background_image_path", None)
        settings["theme"] = theme
    save_settings(settings)
    return theme_payload()


def choose_local_path_windows(kind: str) -> dict[str, Any]:
    dialogs = {
        "model-folder": r"""
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Choose a local model folder'
$dialog.ShowNewFolderButton = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  Write-Output $dialog.SelectedPath
}
""",
        "model-file": r"""
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'Choose a local model file'
$dialog.Filter = 'Model files (*.gguf;*.safetensors;*.bin;*.pt;*.pth;*.onnx)|*.gguf;*.safetensors;*.bin;*.pt;*.pth;*.onnx|All files (*.*)|*.*'
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  Write-Output $dialog.FileName
}
""",
        "profile-json": r"""
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'Choose a run profile JSON file'
$dialog.Filter = 'JSON files (*.json)|*.json|All files (*.*)|*.*'
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  Write-Output $dialog.FileName
}
""",
    }
    script = dialogs.get(kind)
    if not script:
        return {"ok": False, "error": f"unknown dialog kind: {kind}"}
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if result.returncode != 0:
        return {"ok": False, "error": (result.stderr or result.stdout or "dialog failed").strip()}
    path = result.stdout.strip()
    if not path:
        return {"ok": False, "cancelled": True, "path": ""}
    return {"ok": True, "path": path, "name": Path(path).name}


def choose_local_path_tk(kind: str) -> dict[str, Any]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        return {"ok": False, "error": f"native dialog unavailable: {exc}"}

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    try:
        if kind == "model-folder":
            path = filedialog.askdirectory(title="Choose a local model folder")
        elif kind == "model-file":
            path = filedialog.askopenfilename(
                title="Choose a local model file",
                filetypes=[
                    ("Model files", "*.gguf *.safetensors *.bin *.pt *.pth *.onnx"),
                    ("All files", "*.*"),
                ],
            )
        elif kind == "profile-json":
            path = filedialog.askopenfilename(
                title="Choose a run profile JSON file",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            )
        else:
            return {"ok": False, "error": f"unknown dialog kind: {kind}"}
    finally:
        try:
            root.destroy()
        except Exception:
            pass

    if not path:
        return {"ok": False, "cancelled": True, "path": ""}
    return {"ok": True, "path": str(path), "name": Path(path).name}


def choose_local_path(kind: str) -> dict[str, Any]:
    if os.name == "nt":
        payload = choose_local_path_windows(kind)
        if payload.get("ok") or payload.get("cancelled"):
            return payload
    return choose_local_path_tk(kind)


def choose_profile_json_payload() -> dict[str, Any]:
    payload = choose_local_path("profile-json")
    if not payload.get("ok"):
        return payload
    path = Path(str(payload["path"]))
    try:
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {"ok": False, "path": str(path), "error": str(exc)}
    payload["content"] = content
    return payload


def model_path_exists(path_text: str | None) -> bool:
    if not path_text:
        return False
    return Path(path_text).expanduser().exists()


def model_manifest_status(path: Path) -> str | None:
    manifest_path = path.parent / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    for item in manifest.get("models", []):
        if not isinstance(item, dict):
            continue
        destination = str(item.get("destination") or "")
        try:
            if destination and Path(destination).resolve() == path.resolve():
                return str(item.get("status") or "")
        except Exception:
            if destination and destination == str(path):
                return str(item.get("status") or "")
    return None


def model_integrity(path_text: str | None) -> dict[str, Any]:
    if not path_text:
        return {"complete": False, "reason": "path is empty", "weight_files": 0, "weight_bytes": 0}
    path = Path(path_text).expanduser()
    if not path.exists():
        return {"complete": False, "reason": "path missing", "weight_files": 0, "weight_bytes": 0}
    if path.is_file():
        size = path.stat().st_size
        complete = size > 0 and path.suffix.lower() in {".gguf", ".safetensors", ".bin", ".pt", ".pth", ".onnx"}
        return {
            "complete": complete,
            "reason": "single weight file" if complete else "not a supported weight file",
            "weight_files": 1 if complete else 0,
            "weight_bytes": size if complete else 0,
        }

    manifest_status = model_manifest_status(path)
    if manifest_status and manifest_status != "complete":
        weights = [item for pattern in MODEL_FILE_PATTERNS for item in path.glob(pattern) if item.is_file()]
        return {
            "complete": False,
            "reason": f"manifest status: {manifest_status}",
            "weight_files": len(weights),
            "weight_bytes": sum(item.stat().st_size for item in weights),
        }

    index_path = path / "model.safetensors.index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            names = sorted(set(str(name) for name in index.get("weight_map", {}).values()))
        except Exception as exc:
            return {"complete": False, "reason": f"bad safetensors index: {exc}", "weight_files": 0, "weight_bytes": 0}
        missing = [name for name in names if not (path / name).exists() or (path / name).stat().st_size <= 0]
        existing = [(path / name) for name in names if (path / name).exists()]
        return {
            "complete": not missing,
            "reason": "indexed safetensors complete" if not missing else "missing indexed safetensors",
            "weight_files": len(existing),
            "weight_bytes": sum(item.stat().st_size for item in existing),
            "missing_files": missing[:12],
            "missing_count": len(missing),
        }

    weights = [item for pattern in MODEL_FILE_PATTERNS for item in path.glob(pattern) if item.is_file() and item.stat().st_size > 0]
    if weights:
        return {
            "complete": True,
            "reason": "weight files present",
            "weight_files": len(weights),
            "weight_bytes": sum(item.stat().st_size for item in weights),
        }
    return {"complete": False, "reason": "no local weight files found", "weight_files": 0, "weight_bytes": 0}


def normalize_registry_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(entry)
    path_text = str(normalized.get("path", "")).strip()
    normalized["path"] = path_text
    normalized["exists"] = model_path_exists(path_text)
    normalized["integrity"] = model_integrity(path_text)
    if "id" not in normalized or not normalized["id"]:
        normalized["id"] = Path(path_text).name if path_text else "unknown-model"
    if "source" not in normalized:
        normalized["source"] = "local"
    if "kind" not in normalized:
        normalized["kind"] = infer_model_kind(Path(path_text)) if path_text else "unknown"
    return normalized


def registry_models(registry: dict[str, Any]) -> list[dict[str, Any]]:
    entries = registry.get("models", [])
    if not isinstance(entries, list):
        return []
    return [normalize_registry_entry(entry) for entry in entries if isinstance(entry, dict)]


def model_match_score(model_id: str, entry: dict[str, Any]) -> int:
    entry_id = str(entry.get("id", ""))
    path_name = Path(str(entry.get("path", ""))).name
    if model_id == entry_id:
        return 100
    if model_id == path_name:
        return 90
    if model_id.endswith("/" + entry_id) or model_id.endswith("\\" + entry_id):
        return 70
    if entry_id and entry_id in model_id:
        return 40
    if path_name and path_name in model_id:
        return 35
    return 0


def attach_model_details(model_ids: list[str]) -> list[dict[str, Any]]:
    registry, error = load_model_registry()
    entries = registry_models(registry)
    details = []
    for model_id in model_ids:
        best = None
        best_score = 0
        for entry in entries:
            score = model_match_score(model_id, entry)
            if score > best_score:
                best = entry
                best_score = score
        details.append({
            "id": model_id,
            "registry": best if best_score else None,
            "registry_error": error,
        })
    return details


def normalize_model_id_text(value: Any) -> str:
    text = str(value or "").strip().strip('"').strip("'").replace("\\", "/").rstrip("/")
    return re.sub(r"/+", "/", text).lower()


def model_tail_keys(value: Any, max_parts: int = 5) -> set[str]:
    key = normalize_model_id_text(value)
    parts = [part for part in key.split("/") if part]
    tails = {key} if key else set()
    for size in range(1, min(max_parts, len(parts)) + 1):
        tails.add("/".join(parts[-size:]))
    return tails


def candidate_model_ids(requested: Any) -> list[str]:
    raw = str(requested or "").strip()
    candidates: list[str] = []

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if text and text not in candidates:
            candidates.append(text)

    add(raw)
    add(windows_to_wsl_path(raw))
    add(raw.replace("\\", "/"))

    registry, _ = load_model_registry()
    for entry in registry_models(registry):
        entry_id = str(entry.get("id", "")).strip()
        path_text = str(entry.get("path", "")).strip()
        path_name = Path(path_text).name if path_text else ""
        if raw and raw in {entry_id, path_text, path_name}:
            add(entry_id)
            add(path_text)
            add(path_name)
            add(windows_to_wsl_path(path_text))
    return candidates


def resolve_served_model_id(base: str, requested: Any) -> tuple[str | None, str | None, str | None]:
    requested_text = str(requested or "").strip()
    if not requested_text:
        model, error = infer_default_model(base, None)
        return model, None, error

    served_models, served_error = get_models(base)
    if not served_models:
        return requested_text, requested_text, served_error

    candidates = candidate_model_ids(requested_text)
    served_by_key = {normalize_model_id_text(model): model for model in served_models}
    for candidate in candidates:
        direct = served_by_key.get(normalize_model_id_text(candidate))
        if direct:
            return direct, requested_text, None

    for candidate in candidates:
        candidate_tails = model_tail_keys(candidate)
        for served in served_models:
            served_tails = model_tail_keys(served)
            if candidate_tails & served_tails:
                return served, requested_text, None

    return requested_text, requested_text, None


def infer_model_kind(path: Path) -> str:
    if path.is_file():
        suffix = path.suffix.lower()
        if suffix == ".gguf":
            return "gguf"
        if suffix in {".safetensors", ".bin", ".pt", ".pth", ".onnx"}:
            return "weights-file"
        return suffix.lstrip(".") or "file"
    if (path / "config.json").exists():
        return "huggingface"
    if any(path.glob("*.gguf")):
        return "gguf-dir"
    if any(path.glob("*.safetensors")):
        return "safetensors-dir"
    return "directory"


def looks_like_model_path(path: Path) -> bool:
    if path.is_file():
        return path.suffix.lower() in {".gguf", ".safetensors", ".bin", ".pt", ".pth", ".onnx"}
    if not path.is_dir():
        return False
    if (path / "config.json").exists() or (path / "tokenizer.json").exists():
        return True
    return any(any(path.glob(pattern)) for pattern in MODEL_FILE_PATTERNS)


def scan_model_roots(roots: list[str], max_depth: int) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    queue: list[tuple[Path, int]] = [(Path(root).expanduser(), 0) for root in roots]
    while queue:
        path, depth = queue.pop(0)
        try:
            resolved = path.resolve()
        except Exception:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if looks_like_model_path(resolved):
            found.append({
                "id": resolved.stem if resolved.is_file() else resolved.name,
                "path": str(resolved),
                "kind": infer_model_kind(resolved),
                "source": "scan",
            })
            continue
        if depth >= max_depth or not resolved.is_dir():
            continue
        try:
            children = [child for child in resolved.iterdir() if child.is_dir()]
        except OSError:
            continue
        for child in children:
            if child.name.startswith((".", "__")):
                continue
            queue.append((child, depth + 1))
    return found


def upsert_model_entries(new_entries: list[dict[str, Any]]) -> dict[str, Any]:
    registry, _ = load_model_registry()
    existing = registry_models(registry)
    by_key: dict[str, dict[str, Any]] = {}
    for entry in existing:
        key = str(entry.get("id") or entry.get("path")).lower()
        by_key[key] = entry
    for entry in new_entries:
        normalized = normalize_registry_entry(entry)
        key = str(normalized.get("id") or normalized.get("path")).lower()
        old = by_key.get(key, {})
        by_key[key] = {**old, **normalized}
    registry["models"] = list(by_key.values())
    save_model_registry(registry)
    return registry


def get_gpu_rows() -> tuple[list[list[str]], str | None]:
    query = "index,name,temperature.gpu,power.draw,power.limit,utilization.gpu,memory.used,memory.total"
    cmd = [
        "nvidia-smi",
        f"--query-gpu={query}",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
    except FileNotFoundError:
        return [], "nvidia-smi not found"
    except subprocess.TimeoutExpired:
        return [], "nvidia-smi timeout"
    if completed.returncode != 0:
        return [], completed.stderr.strip() or completed.stdout.strip() or "nvidia-smi failed"
    rows = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 8:
            rows.append(parts[:8])
    return rows, None


def collect_gpu_status() -> tuple[list[dict[str, str]], str | None]:
    rows, error = get_gpu_rows()
    if error:
        return [], error
    keys = ["index", "name", "temp_c", "power_w", "power_limit_w", "util_pct", "memory_used_mib", "memory_total_mib"]
    return [dict(zip(keys, row)) for row in rows], None


def print_gpu_status() -> None:
    rows, error = get_gpu_rows()
    section("GPU")
    if error:
        print(f"GPU 状态读取失败: {error}")
        return
    if not rows:
        print("没有读到 GPU。")
        return
    print("idx  name                         temp  power/limit     util  mem")
    for idx, name, temp, power, limit, util, mem_used, mem_total in rows:
        short_name = name[:28]
        print(f"{idx:<4} {short_name:<28} {temp:>3}C  {power:>6}W/{limit:<5}W {util:>3}%  {mem_used}/{mem_total} MiB")


def print_akoya_summary(metrics: dict[str, list[dict[str, Any]]]) -> None:
    section("Akoya useful-work metrics")
    useful_hps = first_metric(metrics, "akoya_vllm_useful_hashes_per_second")
    jobs = sum_metric(metrics, "akoya_vllm_jobs_received_total")
    registered = sum_metric(metrics, "akoya_vllm_pool_registered")
    mining_enabled = sum_metric(metrics, "akoya_vllm_worker_mining_enabled")
    request_gemms = sum_metric(metrics, "akoya_vllm_request_gemms_total")
    capi_calls = sum_metric(metrics, "akoya_vllm_useful_capi_calls_total")
    completed_launches = sum_metric(metrics, "akoya_vllm_useful_op_completed_launches_delta")
    expected_seconds = first_metric(metrics, "akoya_vllm_expected_seconds_per_open")
    stream = sum_metric(metrics, "akoya_vllm_inference_stream_connected")

    kv("useful hashrate", fmt_hashrate(useful_hps))
    kv("pool registered", fmt_number(registered, 0))
    kv("jobs received", fmt_number(jobs, 0))
    kv("worker mining enabled", fmt_number(mining_enabled, 0))
    kv("request GEMMs", fmt_number(request_gemms, 0))
    kv("useful CAPI calls", fmt_number(capi_calls, 0))
    kv("completed launches", fmt_number(completed_launches, 0))
    kv("expected sec/open", fmt_number(expected_seconds, 2))
    kv("pool inference stream", fmt_number(stream, 0))


def metrics_summary(metrics: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    useful_hps = first_metric(metrics, "akoya_vllm_useful_hashes_per_second")
    useful_tmads = first_metric(metrics, "akoya_vllm_useful_tmads_per_second")
    jobs = sum_metric(metrics, "akoya_vllm_jobs_received_total")
    registered = sum_metric(metrics, "akoya_vllm_pool_registered")
    mining_enabled = sum_metric(metrics, "akoya_vllm_worker_mining_enabled")
    request_gemms = sum_metric(metrics, "akoya_vllm_request_gemms_total")
    capi_calls = sum_metric(metrics, "akoya_vllm_useful_capi_calls_total")
    completed_launches = sum_metric(metrics, "akoya_vllm_useful_op_completed_launches_delta")
    expected_seconds = first_metric(metrics, "akoya_vllm_expected_seconds_per_open")
    stream = sum_metric(metrics, "akoya_vllm_inference_stream_connected")
    shares_total = sum_metric(metrics, "akoya_vllm_share_results_total")
    rejects_total = sum_metric(metrics, "akoya_vllm_share_rejects_total")
    skipped_total = sum_metric(metrics, "akoya_vllm_gemm_skipped_total")
    kernel_apply_total = sum_metric(metrics, "akoya_vllm_pearl_kernel_apply_total")
    kernel_eligible_total = sum_metric(metrics, "akoya_vllm_pearl_kernel_eligible_total")
    kernel_skipped_total = sum_metric(metrics, "akoya_vllm_pearl_kernel_skipped_total")
    total_launches = sum_metric(metrics, "akoya_vllm_useful_op_completed_launches")
    native_hits = sum_metric(metrics, "akoya_vllm_useful_op_hit_signals")
    native_no_hits = sum_metric(metrics, "akoya_vllm_useful_op_no_hit_signals")
    registered_gpus = sum_metric(metrics, "akoya_vllm_registered_gpus")
    return {
        "useful_hashrate_hps": useful_hps,
        "useful_hashrate_label": fmt_hashrate(useful_hps),
        "useful_tmads_per_second": useful_tmads,
        "useful_tmads_label": fmt_number(useful_tmads, 2),
        "jobs_received": jobs,
        "pool_registered": registered,
        "worker_mining_enabled": mining_enabled,
        "request_gemms": request_gemms,
        "useful_capi_calls": capi_calls,
        "completed_launches": completed_launches,
        "expected_seconds_per_open": expected_seconds,
        "inference_stream_connected": stream,
        "share_results_total": shares_total,
        "share_rejects_total": rejects_total,
        "share_results": metric_samples_by_label(metrics, "akoya_vllm_share_results_total"),
        "share_rejects": metric_samples_by_label(metrics, "akoya_vllm_share_rejects_total"),
        "gemm_skipped_total": skipped_total,
        "gemm_skipped": metric_samples_by_label(metrics, "akoya_vllm_gemm_skipped_total"),
        "pearl_kernel_apply_total": kernel_apply_total,
        "pearl_kernel_eligible_total": kernel_eligible_total,
        "pearl_kernel_skipped_total": kernel_skipped_total,
        "completed_launches_total": total_launches,
        "native_hit_signals": native_hits,
        "native_no_hit_signals": native_no_hits,
        "registered_gpus": registered_gpus,
        "layers": layer_metrics(metrics),
    }


def metric_samples_by_label(metrics: dict[str, list[dict[str, Any]]], name: str) -> list[dict[str, Any]]:
    rows = []
    for sample in metrics.get(name, []):
        labels = sample.get("labels") or {}
        label = ",".join(f"{key}={value}" for key, value in sorted(labels.items())) or "total"
        rows.append({"label": label, "labels": labels, "value": float(sample.get("value", 0))})
    return rows


def metric_value_for_label(
    metrics: dict[str, list[dict[str, Any]]],
    name: str,
    key: str,
    value: str,
) -> float | None:
    total = 0.0
    found = False
    for sample in metrics.get(name, []):
        labels = sample.get("labels") or {}
        if str(labels.get(key, "")) == value:
            total += float(sample.get("value", 0))
            found = True
    return total if found else None


def metric_delta_for_label(
    before: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    name: str,
    key: str,
    value: str,
) -> float | None:
    before_value = metric_value_for_label(before, name, key, value)
    after_value = metric_value_for_label(after, name, key, value)
    if before_value is None or after_value is None:
        return None
    return after_value - before_value


def layer_metrics(metrics: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    avg_ms: dict[str, float] = {}
    for sample in metrics.get("akoya_vllm_layer_avg_total_ms", []):
        labels = sample.get("labels") or {}
        layer = labels.get("layer_id") or labels.get("layer") or labels.get("id") or "unknown"
        avg_ms[str(layer)] = float(sample.get("value", 0))
    rows = []
    for sample in metrics.get("akoya_vllm_layer_hashes_per_second", []):
        labels = sample.get("labels") or {}
        layer = str(labels.get("layer_id") or labels.get("layer") or labels.get("id") or "unknown")
        hps = float(sample.get("value", 0))
        rows.append({
            "layer_id": layer,
            "hashes_per_second": hps,
            "hashrate_label": fmt_hashrate(hps),
            "avg_total_ms": avg_ms.get(layer),
        })
    def sort_key(item: dict[str, Any]) -> tuple[int, str]:
        layer = str(item.get("layer_id", ""))
        return (0, f"{int(layer):08d}") if layer.isdigit() else (1, layer)
    return sorted(rows, key=sort_key)


def metric_delta(before: dict[str, list[dict[str, Any]]], after: dict[str, list[dict[str, Any]]], name: str) -> float | None:
    before_value = sum_metric(before, name)
    after_value = sum_metric(after, name)
    if before_value is None or after_value is None:
        return None
    return after_value - before_value


def useful_evidence_payload(
    metrics: dict[str, list[dict[str, Any]]],
    before: dict[str, list[dict[str, Any]]] | None = None,
    model: str | None = None,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = metrics_summary(metrics) if metrics else {}
    has_request_window = before is not None
    before = before or {}
    completed_launches_total_delta = metric_delta(before, metrics, "akoya_vllm_useful_op_completed_launches") if metrics else None
    completed_launches_window_delta = metric_delta(before, metrics, "akoya_vllm_useful_op_completed_launches_delta") if metrics else None
    kernel_apply_delta = metric_delta(before, metrics, "akoya_vllm_pearl_kernel_apply_total") if metrics else None
    kernel_eligible_delta = metric_delta(before, metrics, "akoya_vllm_pearl_kernel_eligible_total") if metrics else None
    kernel_skipped_delta = metric_delta(before, metrics, "akoya_vllm_pearl_kernel_skipped_total") if metrics else None
    deltas = {
        "request_gemms": metric_delta(before, metrics, "akoya_vllm_request_gemms_total") if metrics else None,
        "useful_capi_calls": metric_delta(before, metrics, "akoya_vllm_useful_capi_calls_total") if metrics else None,
        "completed_launches": completed_launches_total_delta if completed_launches_total_delta is not None else completed_launches_window_delta,
        "completed_launches_window": completed_launches_window_delta,
        "completed_launches_total": completed_launches_total_delta,
        "gemm_skipped": metric_delta(before, metrics, "akoya_vllm_gemm_skipped_total") if metrics else None,
        "shape_gate_skipped": metric_delta_for_label(before, metrics, "akoya_vllm_gemm_skipped_total", "reason", "shape_gate") if metrics else None,
        "pearl_kernel_apply": kernel_apply_delta,
        "pearl_kernel_eligible": kernel_eligible_delta,
        "pearl_kernel_skipped": kernel_skipped_delta,
        "native_hit_signals": metric_delta(before, metrics, "akoya_vllm_useful_op_hit_signals") if metrics else None,
        "native_no_hit_signals": metric_delta(before, metrics, "akoya_vllm_useful_op_no_hit_signals") if metrics else None,
        "share_results": metric_delta(before, metrics, "akoya_vllm_share_results_total") if metrics else None,
        "share_rejects": metric_delta(before, metrics, "akoya_vllm_share_rejects_total") if metrics else None,
    }
    reasons = []
    if not metrics:
        reasons.append({
            "code": "metrics_unavailable",
            "text": "metrics 不可用，无法判断 useful work",
            "text_en": "metrics are unavailable, so useful work cannot be verified",
        })
    if metrics and not has_request_window:
        reasons.append({
            "code": "no_request_window",
            "text": "这是当前快照，不是一次推理请求的前后差值",
            "text_en": "this is a current snapshot, not a before/after inference request delta",
        })
    if model and "pearl" not in model.lower():
        reasons.append({
            "code": "model_may_not_be_pearl",
            "text": "模型名不像 Pearl 模型，普通模型通常不会产生 PRL share",
            "text_en": "the model name does not look like a Pearl model; ordinary models usually do not produce PRL shares",
        })
    if summary.get("pool_registered") in {None, 0}:
        reasons.append({
            "code": "no_pool_registration",
            "text": "还没有注册到 pool，或 pool metrics 不可用",
            "text_en": "not registered with the pool yet, or pool registration metrics are unavailable",
        })
    elif summary.get("inference_stream_connected") in {None, 0}:
        reasons.append({
            "code": "pool_stream_not_connected",
            "text": "pool 已注册但推理流没有连接；网站侧通常也不会显示 useful worker 在线",
            "text_en": "the pool is registered but the inference stream is not connected; the website usually will not show the useful worker online",
        })
    if summary.get("worker_mining_enabled") in {None, 0}:
        reasons.append({
            "code": "mining_disabled",
            "text": "worker mining 未开启",
            "text_en": "worker mining is disabled",
        })
    if summary.get("jobs_received") in {None, 0}:
        reasons.append({
            "code": "no_pool_job",
            "text": "没有 pool job，推理可能只能本地服务但不会提交 share",
            "text_en": "no pool job is available; inference may be local-only and cannot submit shares",
        })
    if deltas["shape_gate_skipped"] and deltas["shape_gate_skipped"] > 0:
        reasons.append({
            "code": "shape_gate",
            "text": f"本次请求有 {fmt_number(deltas['shape_gate_skipped'], 0)} 个 GEMM 被 Akoya shape gate 跳过；模型在跑，但这些 shape 不计入 useful share",
            "text_en": f"{fmt_number(deltas['shape_gate_skipped'], 0)} GEMMs were skipped by Akoya's shape gate; the model ran, but these shapes did not count as useful shares",
        })
    elif deltas["pearl_kernel_skipped"] and deltas["pearl_kernel_skipped"] > 0 and not (deltas["pearl_kernel_eligible"] and deltas["pearl_kernel_eligible"] > 0):
        reasons.append({
            "code": "kernel_skipped_not_useful",
            "text": f"本次请求触发了 {fmt_number(deltas['pearl_kernel_apply'], 0)} 次 Pearl kernel hook，但 {fmt_number(deltas['pearl_kernel_skipped'], 0)} 次被跳过，eligible 没增加；这不是 accepted share",
            "text_en": f"this request hit {fmt_number(deltas['pearl_kernel_apply'], 0)} Pearl kernel hooks, but {fmt_number(deltas['pearl_kernel_skipped'], 0)} were skipped and eligible did not increase; this is not an accepted share",
        })
    elif (summary.get("gemm_skipped_total") or summary.get("pearl_kernel_skipped_total")) and (deltas["request_gemms"] == 0 and deltas["completed_launches_total"] == 0):
        skipped_seen = summary.get("gemm_skipped_total") or summary.get("pearl_kernel_skipped_total")
        reasons.append({
            "code": "shape_gate_seen",
            "text": f"Akoya 已累计跳过 {fmt_number(skipped_seen, 0)} 个 GEMM/kernel；最近问题很可能是请求 shape 没进 useful 路径",
            "text_en": f"Akoya has skipped {fmt_number(skipped_seen, 0)} GEMMs/kernels in total; recent requests likely missed the useful path because of shape gating",
        })
    if deltas["request_gemms"] == 0 and deltas["completed_launches"] == 0 and deltas["completed_launches_total"] == 0:
        reasons.append({
            "code": "request_shape_or_idle",
            "text": "本次请求没有观察到 useful GEMM/launch 增量，可能请求 shape 太小、被 shape gate 跳过，或 metrics 还没刷新",
            "text_en": "no GEMM/launch delta was observed; the request may be too small, shape-gated, or metrics may not have refreshed",
        })
    if deltas["useful_capi_calls"] == 0:
        reasons.append({
            "code": "no_useful_capi_delta",
            "text": "本次请求没有 useful CAPI 增量，原生库、模型路径或 shape 可能没有接入 useful 路径",
            "text_en": "no useful CAPI delta was observed; the native library, model path, or shape may not have entered the useful path",
        })
    if deltas["native_no_hit_signals"] and deltas["native_no_hit_signals"] > 0:
        reasons.append({
            "code": "native_no_hit",
            "text": f"原生 useful op 返回 {fmt_number(deltas['native_no_hit_signals'], 0)} 个 no-hit signal；这是正常概率事件，不等于 accepted share",
            "text_en": f"the native useful op returned {fmt_number(deltas['native_no_hit_signals'], 0)} no-hit signals; this is normal probability behavior, not an accepted share",
        })
    if deltas["share_results"] is None:
        reasons.append({
            "code": "share_metric_missing",
            "text": "当前 metrics 没暴露 share_results_total，所以还不能从本地证明 accepted/rejected share",
            "text_en": "the current metrics do not expose share_results_total, so accepted/rejected shares are not locally proven",
        })
    elif deltas["share_results"] == 0:
        reasons.append({
            "code": "no_share_in_window",
            "text": "本次窗口没有 accepted/rejected share 增量，这可能只是时间太短",
            "text_en": "no accepted/rejected share delta appeared in this short window",
        })
    useful = bool(
        metrics
        and (summary.get("useful_hashrate_hps") or 0) > 0
        and (
            (deltas["request_gemms"] or 0) > 0
            or (deltas["completed_launches"] or 0) > 0
            or (deltas["completed_launches_total"] or 0) > 0
        )
    )
    snapshot_useful = bool(
        metrics
        and (summary.get("useful_hashrate_hps") or 0) > 0
        and (
            (summary.get("request_gemms") or 0) > 0
            or (summary.get("useful_capi_calls") or 0) > 0
            or (summary.get("completed_launches_total") or 0) > 0
        )
    )
    share_proven = bool((deltas["share_results"] or 0) > 0)
    if useful:
        verdict = "useful-work observed"
        verdict_zh = "本次观察到 useful-work"
        verdict_en = "useful-work observed"
    elif snapshot_useful:
        verdict = "useful-work signal present (snapshot, no share proven)"
        verdict_zh = "有 useful 信号快照，但未证明本次 share"
        verdict_en = "useful signal snapshot, no share proven"
    else:
        verdict = "useful-work not proven yet"
        verdict_zh = "还未证明 useful-work"
        verdict_en = "useful-work not proven yet"
    return {
        "useful": useful,
        "snapshot_useful": snapshot_useful,
        "share_proven": share_proven,
        "verdict": verdict,
        "verdict_zh": verdict_zh,
        "verdict_en": verdict_en,
        "model": model,
        "request_time": now_local(),
        "usage": usage or {},
        "delta": deltas,
        "summary": summary,
        "layers": summary.get("layers", []),
        "reasons": reasons,
    }

def collect_status(base: str) -> dict[str, Any]:
    gpu, gpu_error = collect_gpu_status()
    health = get_text(base, "/health", timeout=0.8)
    models, models_error = get_models(base, timeout=0.8)
    metrics, metrics_error = get_metrics(base, timeout=0.8)
    registry, registry_error = load_model_registry()
    registry_entries = registry_models(registry)
    runtime = runtime_status_payload(base, health)
    health_error = health.error
    if not health.ok:
        active_vllm = next(
            (
                process
                for process in runtime.get("processes", [])
                if process.get("running") and process.get("backend") == "akoya_vllm"
            ),
            None,
        )
        if active_vllm:
            diagnostic = active_vllm.get("diagnostic") if isinstance(active_vllm.get("diagnostic"), dict) else {}
            health_error = f"starting: {diagnostic.get('title_en') or diagnostic.get('code') or 'vLLM not ready'}"
        else:
            failed_vllm = next(
                (
                    process
                    for process in runtime.get("processes", [])
                    if process.get("backend") == "akoya_vllm"
                    and isinstance(process.get("diagnostic"), dict)
                    and process["diagnostic"].get("severity") == "bad"
                ),
                None,
            )
            if failed_vllm:
                diagnostic = failed_vllm.get("diagnostic") or {}
                title = diagnostic.get("title_en") or diagnostic.get("code") or "Runtime failed"
                recent_error = diagnostic.get("recent_error")
                health_error = f"{title}: {recent_error}" if recent_error else title
    return {
        "api_base": base,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "health": {
            "online": health.ok,
            "status": health.status,
            "error": health_error,
        },
        "models": models,
        "model_details": attach_model_details(models),
        "models_error": models_error,
        "model_registry": {
            "path": str(MODEL_REGISTRY_PATH),
            "models": registry_entries,
            "error": registry_error,
        },
        "metrics": metrics_summary(metrics) if metrics else {},
        "metrics_error": metrics_error,
        "evidence": useful_evidence_payload(metrics) if metrics else useful_evidence_payload({}),
        "run_profiles": run_profiles_payload(),
        "runtime": runtime,
        "import_summary": import_summary_payload(),
        "gpu": gpu,
        "gpu_error": gpu_error,
    }


def status_command(args: argparse.Namespace) -> int:
    base = args.api_base.rstrip("/")
    print("PapiMiner local status")
    print(f"API: {base}")

    health = get_text(base, "/health", timeout=3.0)
    section("vLLM / Akoya endpoint")
    if health.ok:
        kv("health", f"online (HTTP {health.status})")
    else:
        kv("health", f"offline ({health.error or health.status})")

    models, models_error = get_models(base)
    if models:
        kv("models", ", ".join(models[:3]) + (" ..." if len(models) > 3 else ""))
    else:
        kv("models", f"- ({models_error or 'none'})")

    metrics, metrics_error = get_metrics(base)
    if metrics:
        print_akoya_summary(metrics)
    else:
        section("Akoya useful-work metrics")
        print(f"metrics unavailable: {metrics_error}")

    print_gpu_status()
    return 0


def metrics_command(args: argparse.Namespace) -> int:
    base = args.api_base.rstrip("/")
    metrics, error = get_metrics(base)
    if error:
        print(f"metrics unavailable: {error}", file=sys.stderr)
        return 1
    names = sorted(name for name in metrics if name.startswith("akoya_vllm_"))
    if args.names:
        wanted = set(args.names)
        names = [name for name in names if name in wanted]
    if not names:
        print("没有 Akoya metrics。")
        return 0
    for name in names:
        samples = metrics[name]
        for sample in samples[: args.max_samples]:
            labels = sample["labels"]
            label_text = ""
            if labels:
                label_text = " " + " ".join(f"{key}={value}" for key, value in sorted(labels.items()))
            print(f"{name}{label_text} = {fmt_number(sample['value'], 4)}")
        if len(samples) > args.max_samples:
            print(f"{name} ... {len(samples) - args.max_samples} more samples")
    return 0


def phi_tiny_moe_1024_prompt() -> str:
    # This exact probe matched the earlier local phi-tiny-moe-pearl-int7 run and
    # reached the 1024-token MoE shape. Treat it as a trigger probe, not prose.
    base = "You are a tiny local test model. Explain Pearl useful work in simple words. Use a different concrete example each time. "
    return base + "Request number 0. " + ("matrix multiply, reward, proof. " * 141) + (" x" * 5)


def build_prompt(args: argparse.Namespace) -> str:
    if args.profile == "phi-tiny-moe-1024":
        return phi_tiny_moe_1024_prompt()
    if args.prompt:
        return args.prompt
    return "用中文解释 Pearl useful work 是什么，讲得短一点。"


def infer_default_model(base: str, explicit: str | None) -> tuple[str | None, str | None]:
    if explicit:
        return explicit, None
    models, error = get_models(base)
    if models:
        return models[0], None
    return None, error or "no model from /v1/models"


def prompt_command(args: argparse.Namespace) -> int:
    base = args.api_base.rstrip("/")
    model, model_error = infer_default_model(base, args.model)
    if not model:
        print(f"没有可用模型: {model_error}", file=sys.stderr)
        return 1

    before, _ = get_metrics(base)
    before_launches = sum_metric(before, "akoya_vllm_useful_op_completed_launches_delta")
    before_gemms = sum_metric(before, "akoya_vllm_request_gemms_total")

    prompt = build_prompt(args)
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    }
    print(f"PapiMiner request -> {model}")
    if args.profile:
        print(f"profile: {args.profile}")
    print(f"prompt chars: {len(prompt)}")

    data, result = post_json(base, "/v1/completions", payload=payload, timeout=args.timeout)
    if not data:
        print(f"请求失败: {result.error or result.status}", file=sys.stderr)
        if result.text:
            print(result.text[:1200], file=sys.stderr)
        return 1

    text = ""
    choices = data.get("choices") or []
    if choices:
        text = str(choices[0].get("text", "")).strip()
    section("Model output")
    print(text or "(empty)")

    after, _ = get_metrics(base)
    after_launches = sum_metric(after, "akoya_vllm_useful_op_completed_launches_delta")
    after_gemms = sum_metric(after, "akoya_vllm_request_gemms_total")
    after_hps = first_metric(after, "akoya_vllm_useful_hashes_per_second")

    section("Useful-work delta")
    kv("useful hashrate", fmt_hashrate(after_hps))
    if before_launches is not None and after_launches is not None:
        kv("completed launches +", fmt_number(after_launches - before_launches, 0))
    else:
        kv("completed launches +", "-")
    if before_gemms is not None and after_gemms is not None:
        kv("request GEMMs +", fmt_number(after_gemms - before_gemms, 0))
    else:
        kv("request GEMMs +", "-")
    return 0


def flatten_messages(messages: list[dict[str, str]]) -> str:
    chunks = []
    for message in messages:
        role = str(message.get("role", "user"))
        content = str(message.get("content", ""))
        if content.strip():
            chunks.append(f"{role}: {content}")
    chunks.append("assistant:")
    return "\n".join(chunks)


def completion_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    first = choices[0]
    if isinstance(first.get("message"), dict):
        return str(first["message"].get("content", "")).strip()
    return str(first.get("text", "")).strip()


def upstream_error_message(result: HttpResult) -> str:
    raw = (result.text or "").strip()
    if raw:
        try:
            data = json.loads(raw)
            error = data.get("error") if isinstance(data, dict) else None
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
            if isinstance(data, dict) and data.get("message"):
                return str(data["message"])
        except json.JSONDecodeError:
            pass
    return raw or result.error or f"HTTP {result.status}"


def chat_error_payload(result: HttpResult) -> tuple[dict[str, Any], int]:
    message = upstream_error_message(result)
    context_match = re.search(
        r"maximum context length is (\d+) tokens.*?requested (\d+) output tokens.*?"
        r"prompt contains at least (\d+) input tokens.*?total of at least (\d+) tokens",
        message,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if context_match:
        max_context, output_tokens, input_tokens, total_tokens = context_match.groups()
        return {
            "ok": False,
            "error": (
                f"输入太长：当前模型最大上下文是 {max_context} tokens；"
                f"这次输入至少 {input_tokens} tokens，输出预留 {output_tokens} tokens，"
                f"合计至少 {total_tokens} tokens。请缩短输入，或把 Max tokens 调小。"
            ),
            "error_en": (
                f"Input is too long: this model allows {max_context} context tokens; "
                f"your prompt has at least {input_tokens} input tokens and reserves "
                f"{output_tokens} output tokens, totaling at least {total_tokens}. "
                "Shorten the prompt or lower Max tokens."
            ),
            "detail": message[:1200],
        }, 400

    status = 400 if result.status == 400 else 502
    short = message[:700]
    return {
        "ok": False,
        "error": f"vLLM 请求失败：{short}",
        "error_en": f"vLLM request failed: {short}",
        "detail": message[:1200],
    }, status


def chat_once(base: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
    requested_model = body.get("model")
    model, requested_model_text, model_error = resolve_served_model_id(base, requested_model)
    if not model:
        return {"ok": False, "error": f"no model: {model_error}"}, 400

    messages = body.get("messages") or []
    if not isinstance(messages, list) or not messages:
        return {"ok": False, "error": "messages is required"}, 400

    max_tokens = int(body.get("max_tokens", 256))
    temperature = float(body.get("temperature", 0.3))
    before, _ = get_metrics(base)

    chat_payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data, result = post_json(base, "/v1/chat/completions", chat_payload, timeout=120.0)
    mode = "chat"
    if not data:
        if result.status == 400:
            return chat_error_payload(result)
        prompt_payload = {
            "model": model,
            "prompt": flatten_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        data, result = post_json(base, "/v1/completions", prompt_payload, timeout=120.0)
        mode = "completion"

    if not data:
        return chat_error_payload(result)

    after, _ = get_metrics(base)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    evidence = useful_evidence_payload(after, before, str(model), usage)

    return {
        "ok": True,
        "mode": mode,
        "model": model,
        "requested_model": requested_model_text,
        "text": completion_text(data),
        "metrics": metrics_summary(after),
        "usage": usage,
        "delta": evidence["delta"],
        "evidence": evidence,
    }, 200


def make_handler(api_base: str) -> type[BaseHTTPRequestHandler]:
    class PapiMinerHandler(BaseHTTPRequestHandler):
        server_version = "PapiMinerHTTP/0.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            if os.environ.get("PapiMiner_HTTP_LOG") == "1":
                super().log_message(fmt, *args)

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8-sig"))

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/ready":
                self.send_json({"ok": True, "api_base": api_base, "time": now_local()})
                return
            if parsed.path == "/api/status":
                self.send_json(collect_status(api_base))
                return
            if parsed.path == "/api/import/summary":
                self.send_json(import_summary_payload())
                return
            if parsed.path == "/api/run-profiles":
                self.send_json(run_profiles_payload())
                return
            if parsed.path == "/api/runtime/status":
                self.send_json(runtime_status_payload(api_base))
                return
            if parsed.path == "/api/useful/evidence":
                metrics, error = get_metrics(api_base)
                payload = useful_evidence_payload(metrics)
                payload["metrics_error"] = error
                self.send_json(payload)
                return
            if parsed.path == "/api/theme":
                self.send_json(theme_payload())
                return
            if parsed.path == "/api/background":
                self.serve_background()
                return
            self.serve_static(parsed.path)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/chat":
                try:
                    payload = self.read_json()
                    response, status = chat_once(api_base, payload)
                    self.send_json(response, status)
                except Exception as exc:  # keep the local UI alive on bad requests
                    self.send_json({"ok": False, "error": str(exc)}, 500)
                return
            if parsed.path == "/api/dialog/model-folder":
                self.send_json(choose_local_path("model-folder"))
                return
            if parsed.path == "/api/dialog/model-file":
                self.send_json(choose_local_path("model-file"))
                return
            if parsed.path == "/api/dialog/profile-json":
                self.send_json(choose_profile_json_payload())
                return
            if parsed.path == "/api/import/model":
                try:
                    payload = self.read_json()
                    response, status = self.import_model(payload)
                    self.send_json(response, status)
                except Exception as exc:
                    self.send_json({"ok": False, "error": str(exc)}, 500)
                return
            if parsed.path == "/api/import/profile":
                try:
                    payload = self.read_json()
                    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else payload
                    imported = upsert_run_profile(profile)
                    self.send_json({"ok": True, "profile": imported, "profiles": run_profiles_payload()})
                except Exception as exc:
                    self.send_json({"ok": False, "error": str(exc)}, 500)
                return
            if parsed.path == "/api/runtime/start":
                try:
                    payload = self.read_json()
                    profile_id = str(payload.get("profile_id") or "")
                    overrides = payload.get("overrides") if isinstance(payload.get("overrides"), dict) else {}
                    response, status = start_runtime(profile_id, overrides)
                    self.send_json(response, status)
                except Exception as exc:
                    self.send_json({"ok": False, "error": str(exc)}, 500)
                return
            if parsed.path == "/api/runtime/stop":
                try:
                    payload = self.read_json()
                    profile_id = str(payload.get("profile_id") or "")
                    response, status = stop_runtime(profile_id)
                    self.send_json(response, status)
                except Exception as exc:
                    self.send_json({"ok": False, "error": str(exc)}, 500)
                return
            if parsed.path == "/api/theme/background":
                self.receive_background()
                return
            if parsed.path == "/api/theme/reset-background":
                self.send_json(clear_background_path())
                return
            self.send_json({"ok": False, "error": "not found"}, 404)

        def import_model(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
            path_text = str(payload.get("path") or "").strip()
            if not path_text:
                return {"ok": False, "error": "path is required"}, 400
            path = Path(path_text).expanduser()
            try:
                resolved = path.resolve()
            except Exception:
                resolved = path
            if not resolved.exists():
                return {
                    "ok": False,
                    "error": "path does not exist",
                    "privacy": privacy_hits({"path": str(resolved)}),
                }, 400
            entry = {
                "id": payload.get("id") or (resolved.stem if resolved.is_file() else resolved.name),
                "path": str(resolved),
                "kind": payload.get("kind") or infer_model_kind(resolved),
                "source": payload.get("source") or "ui-import",
                "notes": payload.get("notes") or "",
            }
            registry = upsert_model_entries([entry])
            return {
                "ok": True,
                "entry": normalize_registry_entry(entry),
                "privacy": privacy_hits(entry),
                "models": registry_models(registry),
            }, 200

        def receive_background(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length <= 0:
                    self.send_json({"ok": False, "error": "empty upload"}, 400)
                    return
                if length > MAX_BACKGROUND_BYTES:
                    self.send_json({"ok": False, "error": "image is too large"}, 413)
                    return
                raw_name = self.headers.get("X-Filename", "background.png")
                filename = sanitize_filename(html.unescape(raw_name))
                suffix = Path(filename).suffix.lower()
                if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                    content_type = self.headers.get("Content-Type", "")
                    suffix = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".png"
                    filename = f"{Path(filename).stem}{suffix}"
                BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
                target = BACKGROUND_DIR / filename
                if target.exists():
                    stem, ext = target.stem, target.suffix
                    target = BACKGROUND_DIR / f"{stem}-{int(time.time())}{ext}"
                target.write_bytes(self.rfile.read(length))
                payload = set_background_path(str(target))
                payload["ok"] = True
                self.send_json(payload)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, 500)

        def serve_background(self) -> None:
            path = configured_background_path()
            if not path:
                self.send_error(404)
                return
            content_type, _ = mimetypes.guess_type(str(path))
            raw = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def serve_static(self, raw_path: str) -> None:
            path = raw_path.lstrip("/") or "index.html"
            target = (WEB_DIR / path).resolve()
            web_root = WEB_DIR.resolve()
            if not str(target).startswith(str(web_root)) or not target.is_file():
                self.send_error(404)
                return
            content_type, _ = mimetypes.guess_type(str(target))
            raw = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

    return PapiMinerHandler


class MockVllmState:
    def __init__(self) -> None:
        self.started_at = time.time()
        self.chat_count = 0
        self.completion_count = 0
        self.jobs_received = 3
        self.completed_launches = 0
        self.request_gemms = 0
        self.useful_capi_calls = 0
        self.share_results = 0
        self.share_rejects = 0
        self.useful_hps = 0.0

    def bump(self) -> None:
        self.completed_launches += 8
        self.request_gemms += 8
        self.useful_capi_calls += 8
        self.share_results += 1
        self.useful_hps = 650_000_000_000.0 + (self.chat_count + self.completion_count) * 10_000_000_000.0


def make_mock_vllm_handler() -> type[BaseHTTPRequestHandler]:
    state = MockVllmState()
    models = [
        "PapiMiner-demo-qwen",
        "phi-tiny-moe-pearl-int7",
        "tinyllama-pearl-int7",
    ]

    class MockVllmHandler(BaseHTTPRequestHandler):
        server_version = "PapiMinerMockVLLM/0.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            if os.environ.get("PapiMiner_HTTP_LOG") == "1":
                super().log_message(fmt, *args)

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8-sig"))

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"ok")
                return
            if parsed.path == "/v1/models":
                self.send_json({
                    "object": "list",
                    "data": [{"id": model, "object": "model", "created": int(state.started_at)} for model in models],
                })
                return
            if parsed.path == "/metrics":
                text = "\n".join([
                    "# HELP akoya_vllm_useful_hashes_per_second Mock useful hash rate",
                    "# TYPE akoya_vllm_useful_hashes_per_second gauge",
                    f"akoya_vllm_useful_hashes_per_second {state.useful_hps}",
                    "akoya_vllm_pool_registered 1",
                    f"akoya_vllm_jobs_received_total {state.jobs_received}",
                    "akoya_vllm_worker_mining_enabled 1",
                    f"akoya_vllm_request_gemms_total {state.request_gemms}",
                    f"akoya_vllm_useful_capi_calls_total {state.useful_capi_calls}",
                    f"akoya_vllm_useful_op_completed_launches_delta {state.completed_launches}",
                    f"akoya_vllm_useful_tmads_per_second {state.useful_hps / 1e12}",
                    f"akoya_vllm_share_results_total{{accepted=\"true\"}} {state.share_results}",
                    f"akoya_vllm_share_rejects_total{{reason=\"mock\"}} {state.share_rejects}",
                    f"akoya_vllm_layer_hashes_per_second{{layer_id=\"0\"}} {state.useful_hps * 0.55}",
                    f"akoya_vllm_layer_hashes_per_second{{layer_id=\"1\"}} {state.useful_hps * 0.45}",
                    "akoya_vllm_layer_avg_total_ms{layer_id=\"0\"} 11.8",
                    "akoya_vllm_layer_avg_total_ms{layer_id=\"1\"} 13.2",
                    "akoya_vllm_expected_seconds_per_open 42",
                    "akoya_vllm_inference_stream_connected 0",
                    "",
                ]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
                self.send_header("Content-Length", str(len(text)))
                self.end_headers()
                self.wfile.write(text)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/v1/chat/completions":
                payload = self.read_json()
                state.chat_count += 1
                state.bump()
                messages = payload.get("messages") or []
                last_user = ""
                for message in reversed(messages):
                    if message.get("role") == "user":
                        last_user = str(message.get("content", ""))
                        break
                model = payload.get("model") or models[0]
                text = (
                    f"这是 PapiMiner mock 模型回复。你选择的模型是 {model}。\n"
                    f"我收到了：{last_user or '空消息'}\n"
                    "这条回复用于验证模型选择、聊天链路和 useful-work 指标刷新。"
                )
                self.send_json({
                    "id": f"chatcmpl-mock-{state.chat_count}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                    "usage": {
                        "prompt_tokens": max(1, len(last_user) // 4),
                        "completion_tokens": max(1, len(text) // 4),
                        "total_tokens": max(2, (len(last_user) + len(text)) // 4),
                    },
                })
                return
            if parsed.path == "/v1/completions":
                payload = self.read_json()
                state.completion_count += 1
                state.bump()
                model = payload.get("model") or models[0]
                prompt = str(payload.get("prompt", ""))
                text = f"PapiMiner mock completion from {model}. Prompt chars={len(prompt)}."
                self.send_json({
                    "id": f"cmpl-mock-{state.completion_count}",
                    "object": "text_completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{"index": 0, "text": text, "finish_reason": "stop"}],
                    "usage": {
                        "prompt_tokens": max(1, len(prompt) // 4),
                        "completion_tokens": max(1, len(text) // 4),
                        "total_tokens": max(2, (len(prompt) + len(text)) // 4),
                    },
                })
                return
            self.send_json({"error": "not found"}, 404)

    return MockVllmHandler


def watch_command(args: argparse.Namespace) -> int:
    try:
        while True:
            if not args.no_clear:
                os.system("cls" if os.name == "nt" else "clear")
            status_command(args)
            print(f"\nrefresh every {args.interval}s, Ctrl+C to stop")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nPapiMiner watch stopped.")
        return 0


def serve_command(args: argparse.Namespace) -> int:
    base = args.api_base.rstrip("/")
    handler = make_handler(base)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"
    print("PapiMiner UI running")
    print(f"UI:  {url}")
    print(f"API: {base}")
    print("Press Ctrl+C to stop.")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPapiMiner UI stopped.")
    finally:
        server.server_close()
    return 0


def mock_vllm_command(args: argparse.Namespace) -> int:
    handler = make_mock_vllm_handler()
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}"
    print("PapiMiner mock vLLM running")
    print(f"API: {url}")
    print("Use it with:")
    print(f"  .\\PapiMiner.ps1 --api-base {url} serve --host 127.0.0.1 --port 8788")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPapiMiner mock vLLM stopped.")
    finally:
        server.server_close()
    return 0


def models_list_command(args: argparse.Namespace) -> int:
    registry, error = load_model_registry()
    entries = registry_models(registry)
    print(f"Model registry: {MODEL_REGISTRY_PATH}")
    if error:
        print(f"Registry warning: {error}")
    if not entries:
        print("No registered local models yet.")
        return 0
    for entry in entries:
        exists = "ok" if entry.get("exists") else "missing"
        integrity = entry.get("integrity") if isinstance(entry.get("integrity"), dict) else {}
        complete = "complete" if integrity.get("complete") else f"incomplete: {integrity.get('reason') or 'unknown'}"
        size_gb = float(integrity.get("weight_bytes") or 0) / 1e9
        print(f"- {entry.get('id')} [{entry.get('kind')}, {exists}, {complete}, {size_gb:.2f} GB]")
        print(f"  path: {entry.get('path')}")
        print(f"  source: {entry.get('source')}")
        if entry.get("notes"):
            print(f"  notes: {entry.get('notes')}")
    return 0


def models_add_command(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser()
    try:
        path_text = str(path.resolve())
    except Exception:
        path_text = str(path)
    entry = {
        "id": args.id or (Path(path_text).stem if Path(path_text).is_file() else Path(path_text).name),
        "path": path_text,
        "kind": args.kind or infer_model_kind(Path(path_text)),
        "source": args.source,
    }
    if args.notes:
        entry["notes"] = args.notes
    upsert_model_entries([entry])
    print(f"Registered model: {entry['id']}")
    print(f"path: {entry['path']}")
    return 0


def models_scan_command(args: argparse.Namespace) -> int:
    roots = args.roots
    if not roots:
        roots = [
            str(APP_DIR / "models"),
            str(APP_DIR.parent / "pearl-hf-models"),
            str(APP_DIR.parent / "pearl-qwen3-30b-model"),
            str(APP_DIR.parent / "upstream-akoya-vllm-miner" / "models"),
            str(Path.home() / ".cache" / "huggingface" / "hub"),
        ]
    found = scan_model_roots(roots, args.max_depth)
    if args.save and found:
        upsert_model_entries(found)
    print(f"Scanned roots: {len(roots)}")
    print(f"Found models: {len(found)}")
    for entry in found:
        integrity = model_integrity(entry["path"])
        complete = "complete" if integrity.get("complete") else f"incomplete: {integrity.get('reason') or 'unknown'}"
        size_gb = float(integrity.get("weight_bytes") or 0) / 1e9
        print(f"- {entry['id']} [{entry['kind']}, {complete}, {size_gb:.2f} GB]")
        print(f"  path: {entry['path']}")
    if found and not args.save:
        print("Run again with --save to write them into local/models.local.json.")
    return 0


def theme_show_command(args: argparse.Namespace) -> int:
    payload = theme_payload()
    print(f"Settings: {payload['settings_path']}")
    if payload["has_background"]:
        print(f"Background: {payload['background_path']}")
    else:
        print("Background: none")
    return 0


def theme_background_command(args: argparse.Namespace) -> int:
    payload = set_background_path(args.path)
    print(f"Background set: {payload['background_path']}")
    return 0


def theme_reset_command(args: argparse.Namespace) -> int:
    clear_background_path()
    print("Background reset.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="PapiMiner",
        description="Local CLI frontend for Pearl useful-work experiments.",
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"OpenAI/vLLM base URL, default: {DEFAULT_API_BASE}")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Show local vLLM/Akoya and GPU status")
    status.set_defaults(func=status_command)

    metrics = sub.add_parser("metrics", help="Print Akoya Prometheus metrics")
    metrics.add_argument("names", nargs="*", help="Optional metric names to filter")
    metrics.add_argument("--max-samples", type=int, default=8, help="Max samples per metric")
    metrics.set_defaults(func=metrics_command)

    prompt = sub.add_parser("prompt", help="Send one local completion request")
    prompt.add_argument("--model", help="Model id. Defaults to first /v1/models entry.")
    prompt.add_argument("--prompt", help="Prompt text. Ignored by fixed probe profiles.")
    prompt.add_argument("--profile", choices=["phi-tiny-moe-1024"], help="Use a known useful-work probe prompt")
    prompt.add_argument("--max-tokens", type=int, default=64)
    prompt.add_argument("--temperature", type=float, default=0.2)
    prompt.add_argument("--timeout", type=float, default=90.0)
    prompt.set_defaults(func=prompt_command)

    watch = sub.add_parser("watch", help="Refresh status repeatedly")
    watch.add_argument("--interval", type=float, default=3.0)
    watch.add_argument("--no-clear", action="store_true")
    watch.set_defaults(func=watch_command)

    serve = sub.add_parser("serve", help="Run the local PapiMiner web UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--open", action="store_true", help="Open the system browser")
    serve.set_defaults(func=serve_command)

    mock = sub.add_parser("mock-vllm", help="Run a tiny local OpenAI-compatible mock server for UI testing")
    mock.add_argument("--host", default="127.0.0.1")
    mock.add_argument("--port", type=int, default=8890)
    mock.set_defaults(func=mock_vllm_command)

    models = sub.add_parser("models", help="Track local model paths without committing private paths")
    models_sub = models.add_subparsers(dest="models_command", required=True)

    models_list = models_sub.add_parser("list", help="List local model registry")
    models_list.set_defaults(func=models_list_command)

    models_add = models_sub.add_parser("add", help="Register one local model path")
    models_add.add_argument("--id", help="Model id shown in the UI")
    models_add.add_argument("--path", required=True, help="Local model directory or file path")
    models_add.add_argument("--kind", help="Model kind, for example huggingface or gguf")
    models_add.add_argument("--source", default="manual")
    models_add.add_argument("--notes")
    models_add.set_defaults(func=models_add_command)

    models_scan = models_sub.add_parser("scan", help="Scan folders for model-looking paths")
    models_scan.add_argument("roots", nargs="*", help="Folders to scan. Defaults to local known model roots.")
    models_scan.add_argument("--max-depth", type=int, default=2)
    models_scan.add_argument("--save", action="store_true", help="Save found models into local/models.local.json")
    models_scan.set_defaults(func=models_scan_command)

    theme = sub.add_parser("theme", help="Manage local-only UI customization")
    theme_sub = theme.add_subparsers(dest="theme_command", required=True)

    theme_show = theme_sub.add_parser("show", help="Show current local theme settings")
    theme_show.set_defaults(func=theme_show_command)

    theme_background = theme_sub.add_parser("background", help="Use a local image file as the UI background")
    theme_background.add_argument("--path", required=True)
    theme_background.set_defaults(func=theme_background_command)

    theme_reset = theme_sub.add_parser("reset-background", help="Reset the UI background")
    theme_reset.set_defaults(func=theme_reset_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
