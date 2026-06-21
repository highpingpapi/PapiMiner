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
    LOCAL_DIR / "models.local.json",
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


def wait_json(url: str, timeout: float = 15.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            return request_json("GET", url, timeout=1.0)
        except Exception as exc:  # pragma: no cover - diagnostic path
            last_error = str(exc)
            time.sleep(0.25)
    raise RuntimeError(f"timed out waiting for {url}: {last_error}")


def start_process(args: list[str], name: str) -> subprocess.Popen[str]:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    stdout = (RUN_DIR / f"{name}.out.log").open("w", encoding="utf-8")
    stderr = (RUN_DIR / f"{name}.err.log").open("w", encoding="utf-8")
    return subprocess.Popen(
        args,
        cwd=str(APP_DIR),
        stdout=stdout,
        stderr=stderr,
        text=True,
    )


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
    mock_port = 8891
    web_port = 8791
    mock_base = f"http://127.0.0.1:{mock_port}"
    web_base = f"http://127.0.0.1:{web_port}"
    results: list[dict[str, Any]] = []
    mock_proc: subprocess.Popen[str] | None = None
    web_proc: subprocess.Popen[str] | None = None

    with LocalStateBackup():
        with tempfile.TemporaryDirectory(prefix="papiminer-smoke-model-") as model_dir:
            model_path = Path(model_dir)
            (model_path / "config.json").write_text('{"model_type":"mock"}\n', encoding="utf-8")

            try:
                mock_proc = start_process(
                    [sys.executable, str(SCRIPT), "mock-vllm", "--host", "127.0.0.1", "--port", str(mock_port)],
                    "mock-vllm-8891",
                )
                wait_json(f"{mock_base}/v1/models")

                web_proc = start_process(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--api-base",
                        mock_base,
                        "serve",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(web_port),
                    ],
                    "papiminer-8791",
                )
                ready = wait_json(f"{web_base}/api/ready")
                results.append(check(ready.get("ok") is True, "ready endpoint", ready))

                status = request_json("GET", f"{web_base}/api/status", timeout=8.0)
                results.append(check(status.get("health", {}).get("online") is True, "mock vLLM health online"))
                results.append(check(len(status.get("models", [])) >= 3, "online model list", status.get("models", [])))
                profile_ids = [item.get("id") for item in status.get("run_profiles", {}).get("profiles", [])]
                results.append(check("akoya-plain-default" in profile_ids, "built-in plain profile present", profile_ids))
                results.append(check("akoya-vllm-local" in profile_ids, "built-in useful profile present", profile_ids))
                results.append(check("gpu" in status and isinstance(status.get("gpu"), list), "gpu status payload is a list"))

                imported_model = request_json(
                    "POST",
                    f"{web_base}/api/import/model",
                    {"id": "papiminer-smoke-model", "path": str(model_path)},
                )
                results.append(check(imported_model.get("ok") is True, "model import", imported_model.get("entry", {})))

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
                results.append(check(imported_profile.get("ok") is True, "profile import", profile.get("id")))
                privacy = profile.get("privacy", [])
                results.append(check(len(privacy) >= 1, "profile privacy flags local-only fields", privacy))

                chat = request_json(
                    "POST",
                    f"{web_base}/api/chat",
                    {
                        "model": "tinyllama-pearl-int7",
                        "messages": [{"role": "user", "content": "Explain Pearl useful work in one short sentence."}],
                        "max_tokens": 64,
                        "temperature": 0.2,
                    },
                    timeout=10.0,
                )
                evidence = chat.get("evidence", {})
                delta = evidence.get("delta", {})
                results.append(check(chat.get("ok") is True and bool(chat.get("text")), "chat response from mock model"))
                results.append(check(evidence.get("useful") is True, "useful evidence observed", evidence.get("verdict")))
                results.append(check((delta.get("share_results") or 0) >= 1, "accepted share delta from mock", delta))

                useful = request_json("GET", f"{web_base}/api/useful/evidence", timeout=5.0)
                results.append(check(len(useful.get("layers", [])) >= 2, "layer useful-work metrics", useful.get("layers", [])))
                results.append(check(useful.get("snapshot_useful") is True, "snapshot useful signal", useful.get("verdict")))

                theme = request_json("GET", f"{web_base}/api/theme", timeout=5.0)
                results.append(check("has_background" in theme, "theme endpoint", theme))

            finally:
                if web_proc is not None:
                    stop_process(web_proc)
                if mock_proc is not None:
                    stop_process(mock_proc)

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
