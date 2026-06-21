#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


USER_AGENT = "PapiMiner/0.2 plain-only"
APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"
LOCAL_DIR = APP_DIR / "local"
RUN_PROFILES_PATH = Path(os.environ.get("PAPIMINER_RUN_PROFILES") or LOCAL_DIR / "run-profiles.local.json")
RUNTIME_STATE_PATH = Path(os.environ.get("PAPIMINER_RUNTIME_STATE") or LOCAL_DIR / "runtime.local.json")
SETTINGS_PATH = Path(os.environ.get("PAPIMINER_SETTINGS") or LOCAL_DIR / "settings.local.json")
RUN_LOG_DIR = LOCAL_DIR / "run-logs"
BACKGROUND_DIR = LOCAL_DIR / "backgrounds"
MONITOR_SCRIPT_PATH = APP_DIR / "tools" / "monitor_runtime.ps1"
MAX_BACKGROUND_BYTES = 80 * 1024 * 1024


@dataclass
class ProcessResult:
    ok: bool
    message: str | None = None


def now_local() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def load_json(path: Path, default: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return dict(default), None
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return dict(default), "json root is not an object"
        return data, None
    except Exception as exc:
        return dict(default), str(exc)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = now_local()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def has_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def redact_wallet(value: str) -> str:
    text = str(value or "")
    match = re.search(r"prl1[0-9a-z]{16,}", text, re.IGNORECASE)
    if not match:
        return text
    wallet = match.group(0)
    return text.replace(wallet, wallet[:10] + "..." + wallet[-8:])


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_sensitive(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return redact_wallet(value)
    return value


def privacy_hits(entry: dict[str, Any]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    local_only_keys = ("wallet", "worker", "path", "cwd", "log", "host", "machine", "account")
    for key, value in entry.items():
        key_l = str(key).lower()
        if key_l.endswith("_exists"):
            continue
        if any(marker in key_l for marker in local_only_keys):
            hits.append({
                "field": str(key),
                "policy": "local-only",
                "reason": "machine, pool, wallet, worker, or path field",
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
            "gpu": "0",
            "akoya_gpu_indices": "0",
            "pool_host": "pool-v2.akoyapool.com",
            "pool_port": "443",
            "pool_tls": True,
            "wallet_address": "",
            "worker": "PapiMiner-plain",
            "log_dir": str(RUN_LOG_DIR / "akoya-plain-default"),
            "notes": "PlainProof-only miner profile. It does not run model inference.",
        }
    ]


def normalize_profile(entry: dict[str, Any], origin: str = "local") -> dict[str, Any]:
    profile = dict(entry)
    profile.setdefault("id", f"profile-{abs(hash(json.dumps(profile, sort_keys=True, default=str))) % 1000000}")
    profile.setdefault("label", profile["id"])
    profile.setdefault("label_zh", profile.get("label", profile["id"]))
    profile.setdefault("kind", "plain")
    profile.setdefault("backend", "custom")
    profile.setdefault("source", origin)
    profile.setdefault("gpu", "")
    profile.setdefault("log_dir", str(RUN_LOG_DIR / str(profile["id"])))
    path_text = str(profile.get("path", "")).strip()
    cwd_text = str(profile.get("cwd", "")).strip()
    profile["path_exists"] = bool(path_text and Path(path_text).expanduser().exists())
    profile["cwd_exists"] = bool(cwd_text and Path(cwd_text).expanduser().exists())
    profile["privacy"] = privacy_hits(profile)
    profile["redacted"] = redact_sensitive(profile)
    return profile


def is_plain_profile(entry: dict[str, Any]) -> bool:
    if not isinstance(entry, dict):
        return False
    kind = str(entry.get("kind") or "plain").strip().lower()
    backend = str(entry.get("backend") or "custom").strip().lower()
    return kind == "plain" and backend in {"akoya_plain", "custom"}


def profile_has_runtime(entry: dict[str, Any]) -> bool:
    if not is_plain_profile(entry):
        return False
    return any(str(entry.get(field) or "").strip() for field in ("path", "command", "command_template"))


def load_run_profile_store() -> tuple[dict[str, Any], str | None]:
    data, error = load_json(RUN_PROFILES_PATH, {"profiles": []})
    if not isinstance(data.get("profiles"), list):
        data["profiles"] = []
    return data, error


def run_profiles_payload() -> dict[str, Any]:
    local_store, error = load_run_profile_store()
    by_id: dict[str, dict[str, Any]] = {}
    for profile in default_run_profiles():
        by_id[str(profile["id"])] = normalize_profile(profile, "builtin")
    ignored = 0
    for profile in local_store.get("profiles", []):
        if isinstance(profile, dict) and profile_has_runtime(profile):
            by_id[str(profile.get("id") or profile.get("label") or "custom")] = normalize_profile(profile, "local")
        else:
            ignored += 1
    return {
        "profiles_path": str(RUN_PROFILES_PATH),
        "profiles": list(by_id.values()),
        "ignored_non_plain_profiles": ignored,
        "error": error,
    }


def profile_by_id(profile_id: str) -> dict[str, Any] | None:
    for profile in run_profiles_payload()["profiles"]:
        if profile.get("id") == profile_id:
            return profile
    return None


def upsert_run_profile(profile: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if not is_plain_profile(profile):
        return None, "PapiMiner is plain-only. Import plain miner profiles only."
    store, _ = load_run_profile_store()
    profile = dict(profile)
    profile.setdefault("kind", "plain")
    profile.setdefault("source", "local")
    normalized = normalize_profile(profile, "local")
    existing = [item for item in store.get("profiles", []) if isinstance(item, dict)]
    by_id = {str(item.get("id")): item for item in existing}
    by_id[str(normalized["id"])] = {key: value for key, value in profile.items() if key not in {"redacted", "privacy"}}
    store["profiles"] = list(by_id.values())
    save_json(RUN_PROFILES_PATH, store)
    return normalized, None


def import_summary_payload() -> dict[str, Any]:
    profiles = run_profiles_payload()
    return {
        "settings_path": str(SETTINGS_PATH),
        "run_profiles_path": str(RUN_PROFILES_PATH),
        "runtime_state_path": str(RUNTIME_STATE_PATH),
        "run_log_dir": str(RUN_LOG_DIR),
        "profiles": profiles["profiles"],
        "profiles_error": profiles.get("error"),
        "ignored_non_plain_profiles": profiles.get("ignored_non_plain_profiles", 0),
        "privacy_rules": [
            "wallet addresses are local-only",
            "worker names are local-only",
            "machine names, private IPs, and local paths are local-only",
            "seed phrases, private keys, and exchange passwords are never stored",
        ],
    }


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


def load_runtime_state() -> tuple[dict[str, Any], str | None]:
    data, error = load_json(RUNTIME_STATE_PATH, {"processes": {}})
    if not isinstance(data.get("processes"), dict):
        data["processes"] = {}
    return data, error


def save_runtime_state(state: dict[str, Any]) -> None:
    save_json(RUNTIME_STATE_PATH, state)


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


def stop_pid(pid: int | str) -> ProcessResult:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return ProcessResult(False, "bad pid")
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
            message = (result.stderr or result.stdout or "taskkill failed").strip()
            return ProcessResult(False, message)
        return ProcessResult(True)
    try:
        os.kill(pid_int, 15)
        return ProcessResult(True)
    except OSError as exc:
        return ProcessResult(False, str(exc))


def refresh_runtime_state() -> dict[str, Any]:
    state, error = load_runtime_state()
    changed = False
    for record in state.get("processes", {}).values():
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
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) and has_value(value):
                merged[name] = str(value)
    return merged


def build_runtime_command(profile: dict[str, Any], overrides: dict[str, Any]) -> tuple[list[str] | None, dict[str, Any], str | None]:
    backend = str(profile.get("backend", "custom"))
    kind = str(profile.get("kind") or "plain")
    if kind != "plain" or backend not in {"akoya_plain", "custom"}:
        return None, dict(profile), "PapiMiner is plain-only. Use Papipearls for AI experiments."
    effective = {**profile, **{key: value for key, value in overrides.items() if has_value(value)}}
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
            "AKOYA_POOL_TLS": "1" if truthy(effective.get("pool_tls"), True) else "0",
            "AKOYA_GPU_INDICES": effective.get("akoya_gpu_indices") or effective.get("gpu") or "0",
        }
        exports.update(runtime_env_overrides(effective))
        binary = Path(str(effective.get("path") or "akoya-miner")).name or "akoya-miner"
        command = f"cd {shlex.quote(windows_to_wsl_path(cwd))} && env {shell_env(exports)} ./{shlex.quote(binary)} mine-blocks"
        return ["wsl", "-e", "bash", "-lc", command], effective, None
    template = str(effective.get("command") or effective.get("command_template") or "").strip()
    if not template:
        return None, effective, "custom plain profile requires command"
    command = template.format(**{key: str(value) for key, value in effective.items()})
    if os.name == "nt":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], effective, None
    return ["bash", "-lc", command], effective, None


def start_monitor_window(profile_id: str, log_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if os.name != "nt":
        return None, "monitor window is only implemented on Windows"
    if not MONITOR_SCRIPT_PATH.exists():
        return None, f"monitor script missing: {MONITOR_SCRIPT_PATH}"
    title = f"PapiMiner Monitor - {profile_id}"
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-NoExit",
        "-File",
        str(MONITOR_SCRIPT_PATH),
        "-Title",
        title,
        "-LogPath",
        str(log_path),
        "-IntervalSec",
        "2",
    ]
    try:
        process = subprocess.Popen(command, cwd=str(APP_DIR), creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    except OSError as exc:
        return None, str(exc)
    return {"pid": process.pid, "title": title, "command_preview": command}, None


def start_runtime(profile_id: str, overrides: dict[str, Any]) -> tuple[dict[str, Any], int]:
    profile = profile_by_id(profile_id)
    if not profile:
        return {"ok": False, "error": f"profile not found: {profile_id}"}, 404
    state = refresh_runtime_state()
    requested_gpu = str(overrides.get("gpu") or profile.get("gpu") or "").strip()
    for record in state.get("processes", {}).values():
        if not isinstance(record, dict) or not record.get("running"):
            continue
        if gpu_selectors_overlap(requested_gpu, record.get("gpu")) and record.get("profile_id") != profile_id:
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
        log_handle.write(f"\n# PapiMiner plain start {now_local()}\n".encode("utf-8"))
        log_handle.write(f"# command {json.dumps(redact_sensitive(command), ensure_ascii=False)}\n".encode("utf-8"))
        process = subprocess.Popen(command, cwd=str(APP_DIR), stdout=log_handle, stderr=subprocess.STDOUT)
    monitor = None
    monitor_error = None
    if truthy(effective.get("open_monitor")):
        monitor, monitor_error = start_monitor_window(profile_id, log_path)
    record = {
        "profile_id": profile_id,
        "kind": "plain",
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


def stop_plain_children() -> ProcessResult:
    try:
        result = subprocess.run(
            ["wsl", "-e", "bash", "-lc", "pkill -TERM -x akoya-miner 2>/dev/null || true; sleep 1; pkill -KILL -x akoya-miner 2>/dev/null || true"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return ProcessResult(False, str(exc))
    if result.returncode != 0:
        return ProcessResult(False, (result.stderr or result.stdout or "wsl cleanup failed").strip())
    return ProcessResult(True)


def stop_runtime(profile_id: str) -> tuple[dict[str, Any], int]:
    state = refresh_runtime_state()
    record = state.get("processes", {}).get(profile_id)
    if not isinstance(record, dict):
        return {"ok": False, "error": f"profile is not running: {profile_id}"}, 404
    errors = []
    if record.get("running") and record.get("pid"):
        result = stop_pid(record["pid"])
        if not result.ok:
            errors.append(result.message or "stop failed")
    if record.get("monitor_pid") and pid_running(record.get("monitor_pid")):
        result = stop_pid(record["monitor_pid"])
        if not result.ok:
            errors.append(result.message or "monitor stop failed")
    child_result = stop_plain_children()
    if not child_result.ok:
        errors.append(child_result.message or "child cleanup failed")
    if errors:
        return {"ok": False, "error": "; ".join(errors), "process": redact_sensitive(record)}, 500
    record["running"] = False
    record["status"] = "stopped"
    record["stopped_at"] = now_local()
    save_runtime_state(state)
    return {"ok": True, "process": redact_sensitive(record)}, 200


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
        text = raw.decode("utf-8", errors="replace").replace("\x00", "")
        return text.splitlines()[-80:], None
    except OSError as exc:
        return [], str(exc)


def runtime_status_payload() -> dict[str, Any]:
    state = refresh_runtime_state()
    processes = []
    for profile_id, record in state.get("processes", {}).items():
        if not isinstance(record, dict):
            continue
        profile = profile_by_id(str(record.get("profile_id") or profile_id))
        row = dict(record)
        row["profile"] = profile["redacted"] if profile else None
        lines, log_error = tail_text(record.get("log_path"))
        row["log_tail_error"] = log_error
        row["recent_log"] = [redact_sensitive(line) for line in lines[-20:]]
        processes.append(redact_sensitive(row))
    return {
        "runtime_state_path": str(RUNTIME_STATE_PATH),
        "run_log_dir": str(RUN_LOG_DIR),
        "processes": processes,
        "error": state.get("state_error"),
    }


def collect_gpu_status() -> tuple[list[dict[str, Any]], str | None]:
    query = "index,name,temperature.gpu,power.draw,power.limit,utilization.gpu,utilization.memory,memory.used,memory.total"
    try:
        result = subprocess.run(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return [], str(exc)
    if result.returncode != 0:
        return [], (result.stderr or result.stdout or "nvidia-smi failed").strip()
    rows = []
    keys = ["index", "name", "temperature_c", "power_w", "power_limit_w", "utilization_gpu_pct", "utilization_memory_pct", "memory_used_mib", "memory_total_mib"]
    for line in result.stdout.splitlines():
        parts = [item.strip() for item in line.split(",")]
        if len(parts) < len(keys):
            continue
        item: dict[str, Any] = {}
        for key, value in zip(keys, parts):
            if key == "name":
                item[key] = value
            else:
                try:
                    item[key] = float(value)
                except ValueError:
                    item[key] = value
        rows.append(item)
    return rows, None


def status_payload() -> dict[str, Any]:
    gpu, gpu_error = collect_gpu_status()
    return {
        "ok": True,
        "mode": "plain-only",
        "time": now_local(),
        "run_profiles": run_profiles_payload(),
        "runtime": runtime_status_payload(),
        "import_summary": import_summary_payload(),
        "gpu": gpu,
        "gpu_error": gpu_error,
    }


def load_settings() -> dict[str, Any]:
    data, _ = load_json(SETTINGS_PATH, {})
    return data


def save_settings(settings: dict[str, Any]) -> None:
    save_json(SETTINGS_PATH, settings)


def configured_background_path() -> Path | None:
    theme = load_settings().get("theme", {})
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
        return {"has_background": False, "background_url": None, "background_name": None, "settings_path": str(SETTINGS_PATH)}
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
    return (name or fallback)[:120]


def set_background_from_upload(headers: dict[str, str], raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_BACKGROUND_BYTES:
        return {"ok": False, "error": "image too large"}
    filename = sanitize_filename(headers.get("X-File-Name", "background.png"))
    BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKGROUND_DIR / filename
    dest.write_bytes(raw)
    settings = load_settings()
    theme = settings.get("theme", {})
    if not isinstance(theme, dict):
        theme = {}
    theme["background_image_path"] = str(dest)
    settings["theme"] = theme
    save_settings(settings)
    return {"ok": True, "theme": theme_payload()}


def reset_background() -> dict[str, Any]:
    settings = load_settings()
    theme = settings.get("theme", {})
    if isinstance(theme, dict):
        theme.pop("background_image_path", None)
        settings["theme"] = theme
    save_settings(settings)
    return {"ok": True, "theme": theme_payload()}


def read_body(handler: BaseHTTPRequestHandler, max_bytes: int = 5_000_000) -> bytes:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length > max_bytes:
        raise ValueError("request too large")
    return handler.rfile.read(length) if length else b""


def serve_file(handler: BaseHTTPRequestHandler, path: Path) -> None:
    if path.is_dir():
        path = path / "index.html"
    if not path.exists() or not path.is_file():
        handler.send_error(404)
        return
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    raw = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def make_handler() -> type[BaseHTTPRequestHandler]:
    class PapiMinerHandler(BaseHTTPRequestHandler):
        server_version = "PapiMinerHTTP/0.2"

        def log_message(self, fmt: str, *args: Any) -> None:
            if os.environ.get("PAPIMINER_HTTP_LOG") == "1":
                super().log_message(fmt, *args)

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def read_json(self) -> dict[str, Any]:
            raw = read_body(self)
            if not raw:
                return {}
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("json root must be an object")
            return data

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/ready":
                self.send_json({"ok": True, "app": "PapiMiner", "mode": "plain-only"})
                return
            if parsed.path == "/api/status":
                self.send_json(status_payload())
                return
            if parsed.path == "/api/import/summary":
                self.send_json(import_summary_payload())
                return
            if parsed.path == "/api/run-profiles":
                self.send_json(run_profiles_payload())
                return
            if parsed.path == "/api/runtime/status":
                self.send_json(runtime_status_payload())
                return
            if parsed.path == "/api/theme":
                self.send_json(theme_payload())
                return
            if parsed.path == "/api/background":
                path = configured_background_path()
                if not path:
                    self.send_error(404)
                    return
                serve_file(self, path)
                return
            rel = parsed.path.lstrip("/") or "index.html"
            serve_file(self, WEB_DIR / rel)

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            try:
                if parsed.path == "/api/import/profile":
                    profile = self.read_json()
                    imported, error = upsert_run_profile(profile)
                    if error:
                        self.send_json({"ok": False, "error": error}, 400)
                    else:
                        self.send_json({"ok": True, "profile": imported})
                    return
                if parsed.path == "/api/runtime/start":
                    body = self.read_json()
                    payload, status = start_runtime(str(body.get("profile_id") or ""), body.get("overrides") or {})
                    self.send_json(payload, status)
                    return
                if parsed.path == "/api/runtime/stop":
                    body = self.read_json()
                    payload, status = stop_runtime(str(body.get("profile_id") or ""))
                    self.send_json(payload, status)
                    return
                if parsed.path == "/api/theme/background":
                    result = set_background_from_upload(dict(self.headers), read_body(self, MAX_BACKGROUND_BYTES))
                    self.send_json(result, 200 if result.get("ok") else 400)
                    return
                if parsed.path == "/api/theme/reset-background":
                    self.send_json(reset_background())
                    return
            except json.JSONDecodeError:
                self.send_json({"ok": False, "error": "invalid json"}, 400)
                return
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)}, 400)
                return
            self.send_error(404)

    return PapiMinerHandler


def serve_command(args: argparse.Namespace) -> int:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler())
    url = f"http://{args.host}:{args.port}/"
    print(f"PapiMiner plain-only console: {url}")
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping PapiMiner.")
    return 0


def status_command(_args: argparse.Namespace) -> int:
    payload = status_payload()
    print("PapiMiner plain-only status")
    for gpu in payload.get("gpu", []):
        print(
            f"GPU {gpu.get('index')}: {gpu.get('name')} | "
            f"{gpu.get('temperature_c')} C | {gpu.get('power_w')}/{gpu.get('power_limit_w')} W | "
            f"{gpu.get('utilization_gpu_pct')}%"
        )
    if payload.get("gpu_error"):
        print(f"GPU error: {payload['gpu_error']}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PapiMiner plain-only Pearl miner console")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="serve the local web console")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8788)
    serve.add_argument("--open", action="store_true")
    serve.set_defaults(func=serve_command)

    status = sub.add_parser("status", help="print local GPU/runtime status")
    status.set_defaults(func=status_command)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
