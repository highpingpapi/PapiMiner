from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1]
SCRIPT = APP_DIR / "PapiMiner.py"
LOCAL_DIR = APP_DIR / "local"
RUN_DIR = LOCAL_DIR / "test-runs"
STATE_FILES = [
    LOCAL_DIR / "run-profiles.local.json",
    LOCAL_DIR / "settings.local.json",
    LOCAL_DIR / "runtime.local.json",
]


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 5.0) -> dict[str, Any]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def request_json_expect_error(method: str, url: str, payload: dict[str, Any], timeout: float = 5.0) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def wait_json(url: str, timeout: float = 15.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            return request_json("GET", url, timeout=1.0)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.25)
    raise RuntimeError(f"timed out waiting for {url}: {last_error}")


def start_process(args: list[str], name: str) -> subprocess.Popen[str]:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    stdout = (RUN_DIR / f"{name}.out.log").open("w", encoding="utf-8")
    stderr = (RUN_DIR / f"{name}.err.log").open("w", encoding="utf-8")
    return subprocess.Popen(args, cwd=str(APP_DIR), stdout=stdout, stderr=stderr, text=True)


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


class LocalStateBackup:
    def __init__(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="papiminer-smoke-backup-"))
        self.existed: dict[Path, bool] = {}

    def __enter__(self) -> "LocalStateBackup":
        for path in STATE_FILES:
            self.existed[path] = path.exists()
            if path.exists():
                shutil.copy2(path, self.tmp / path.name)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        for path in STATE_FILES:
            backup = self.tmp / path.name
            if self.existed.get(path):
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, path)
            elif path.exists():
                path.unlink()
        shutil.rmtree(self.tmp, ignore_errors=True)


def check(condition: bool, name: str, details: Any = None) -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "details": details}


def main() -> int:
    web_port = 8791
    web_base = f"http://127.0.0.1:{web_port}"
    results: list[dict[str, Any]] = []
    web_proc: subprocess.Popen[str] | None = None

    with LocalStateBackup():
        try:
            web_proc = start_process(
                [sys.executable, str(SCRIPT), "serve", "--host", "127.0.0.1", "--port", str(web_port)],
                "papiminer-8791",
            )
            ready = wait_json(f"{web_base}/api/ready")
            results.append(check(ready.get("ok") is True, "ready endpoint", ready))
            results.append(check(ready.get("mode") == "plain-only", "plain-only mode", ready))

            status = request_json("GET", f"{web_base}/api/status", timeout=8.0)
            profile_ids = [item.get("id") for item in status.get("run_profiles", {}).get("profiles", [])]
            profile_kinds = [item.get("kind") for item in status.get("run_profiles", {}).get("profiles", [])]
            results.append(check("akoya-plain-default" in profile_ids, "built-in plain profile present", profile_ids))
            results.append(check(set(profile_kinds) == {"plain"}, "only plain profiles are exposed", profile_kinds))
            results.append(check("gpu" in status and isinstance(status.get("gpu"), list), "gpu status payload is a list"))

            imported_profile = request_json(
                "POST",
                f"{web_base}/api/import/profile",
                {
                    "id": "papiminer-smoke-profile",
                    "label": "PapiMiner smoke profile",
                    "kind": "plain",
                    "backend": "custom",
                    "cwd": str(APP_DIR),
                    "command": f'"{sys.executable}" --version',
                    "gpu": "0",
                    "worker": "smoke-worker",
                    "wallet_address": "PRL_TEST_ADDRESS_PLACEHOLDER",
                },
            )
            profile = imported_profile.get("profile", {})
            results.append(check(imported_profile.get("ok") is True, "plain profile import", profile.get("id")))
            results.append(check(len(profile.get("privacy", [])) >= 1, "profile privacy flags local-only fields"))

            code, rejected = request_json_expect_error(
                "POST",
                f"{web_base}/api/import/profile",
                {
                    "id": "bad-ai-profile",
                    "kind": "ai",
                    "backend": "model_runner",
                    "cwd": str(APP_DIR),
                },
            )
            results.append(check(code == 400 and rejected.get("ok") is False, "non-plain profile rejected", rejected))

            theme = request_json("GET", f"{web_base}/api/theme", timeout=5.0)
            results.append(check("has_background" in theme, "theme endpoint", theme))

        finally:
            if web_proc is not None:
                stop_process(web_proc)

    ok = all(item["ok"] for item in results)
    payload = {
        "ok": ok,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tests": results,
    }
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RUN_DIR / f"smoke-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote: {out_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
