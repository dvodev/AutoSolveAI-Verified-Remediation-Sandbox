"""Tiny disposable process used only by the local incident simulator."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--hung", action="store_true")
    args = parser.parse_args()
    state = Path(args.state)
    state.parent.mkdir(parents=True, exist_ok=True)
    while True:
        payload = {
            "pid": os.getpid(),
            "status": "hung" if args.hung else "healthy",
            "heartbeat": time.time(),
        }
        state.write_text(json.dumps(payload), encoding="utf-8")
        time.sleep(30 if args.hung else 0.5)


if __name__ == "__main__":
    main()
