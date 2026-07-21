"""Small durable repository used by the standalone application.

It is intentionally JSONL rather than a database dependency: judges can
inspect every event, copy a run, and replay it with standard tools.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Iterable

from .contracts import ContractError, canonical_json, validate_event


class JsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def append(self, value: dict[str, Any]) -> dict[str, Any]:
        with self.lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(canonical_json(value) + "\n")
            stream.flush()
        return value

    def all(self) -> list[dict[str, Any]]:
        with self.lock:
            if not self.path.exists():
                return []
            values = []
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    values.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ContractError(f"invalid JSONL record: {exc}") from exc
            return values

    def query(self, **filters: Any) -> list[dict[str, Any]]:
        return [item for item in self.all() if all(item.get(key) == value for key, value in filters.items())]

    def export(self, destination: str | Path) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("\n".join(canonical_json(item) for item in self.all()) + "\n", encoding="utf-8")
        return destination

    def verify_chain(self) -> dict[str, Any]:
        records = self.all()
        previous = "0" * 64
        failures: list[str] = []
        for index, record in enumerate(records):
            try:
                validate_event(record)
            except ContractError as exc:
                failures.append(f"{index}: {exc}")
                continue
            if record["previous_hash"] != previous:
                failures.append(f"{index}: previous hash mismatch")
            unsigned = dict(record)
            actual = unsigned.pop("hash")
            import hashlib
            expected = hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()
            if actual != expected:
                failures.append(f"{index}: event hash mismatch")
            previous = actual
        return {"valid": not failures, "events": len(records), "failures": failures, "head": previous}


class RunStore:
    """In-memory run index with durable audit storage."""

    def __init__(self, audit_path: str | Path) -> None:
        self.runs: dict[str, dict[str, Any]] = {}
        self.audit = JsonlStore(audit_path)
        self.lock = threading.RLock()

    def put(self, run_id: str, run: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self.runs[run_id] = run
            return run

    def get(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            if run_id not in self.runs:
                raise KeyError(run_id)
            return self.runs[run_id]

    def values(self) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.runs.values())

    def clear(self) -> None:
        with self.lock:
            self.runs.clear()


def redact_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    from .contracts import redact
    return [redact(dict(record)) for record in records]
