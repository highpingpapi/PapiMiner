from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "candidates.json"


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    target = data["target"]
    print("PapiMiner kernel lab")
    print(f"Scope: {data['scope']}")
    print(f"Near-term target: {target['near_term']}")
    print(f"Stretch target: {target['stretch_ths']} TH/s")
    print()

    next_items = [item for item in data["candidates"] if item["status"] == "next"]
    if not next_items:
        print("No candidate is marked as next.")
        return 1

    for item in next_items:
        print(f"Next candidate: {item['id']}")
        print(f"Kind: {item['kind']}")
        print(f"Goal: {item['goal']}")
        print(f"Why: {item['why']}")
        if item.get("owned_artifacts"):
            print("Owned artifacts:")
            for artifact in item["owned_artifacts"]:
                print(f"- {artifact}")
        if item.get("build_env"):
            print("Build env:")
            for key, value in item["build_env"].items():
                print(f"- {key}={value}")
        print("Gates:")
        for gate in item.get("gates", []):
            print(f"- {gate}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
