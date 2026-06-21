from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "candidates.json"


def make_command(upstream: str, env: dict[str, str]) -> str:
    parts = [f"{key}={value}" for key, value in env.items()]
    parts.append("NVCC_THREADS=1")
    parts.append("make -f csrc/capi/Makefile")
    return f"cd {upstream} && " + " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print Akoya pearl-gemm candidate build commands."
    )
    parser.add_argument(
        "--upstream",
        default="<akoya-pearl-gemm>",
        help="Path to Akoya native/pearl-gemm when you are ready to apply a candidate.",
    )
    args = parser.parse_args()

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = [
        item for item in data["candidates"]
        if item.get("kind") == "akoya_hot_path_candidate"
    ]
    if not rows:
        print("No Akoya hot path candidates found.")
        return 1

    for item in rows:
        print(f"[{item['status']}] {item['id']}")
        print(f"Goal: {item['goal']}")
        print(f"Why: {item['why']}")
        print("Command:")
        print(make_command(args.upstream, item["build_env"]))
        print("Gates:")
        for gate in item.get("gates", []):
            print(f"- {gate}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
