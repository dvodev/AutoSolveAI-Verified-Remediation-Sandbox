"""Synthetic target: a disposable local worker, never a host service."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


class IncidentSandbox:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or tempfile.mkdtemp(prefix="verified-remediation-"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_file = self.root / "worker-state.json"
        self.log_file = self.root / "worker.log"
        self.pid_file = self.root / "worker.pid"
        self.process: subprocess.Popen[bytes] | None = None

    def _pid(self) -> int | None:
        try:
            return int(self.pid_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _alive(self, pid: int | None) -> bool:
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def start(self, *, hung: bool = False) -> dict[str, Any]:
        self.stop()
        # Do not let a previous worker's heartbeat satisfy the new worker's
        # readiness check during the small process-start race.
        self.state_file.unlink(missing_ok=True)
        log = self.log_file.open("a", encoding="utf-8")
        command = [sys.executable, "-m", "verified_sandbox.worker", "--state", str(self.state_file)]
        if hung:
            command.append("--hung")
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=str(Path(__file__).parents[1]),
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        log.close()
        self.process = process
        self.pid_file.write_text(str(process.pid), encoding="utf-8")
        deadline = time.time() + 5
        while time.time() < deadline:
            if self.state_file.exists():
                return self.inspect()
            time.sleep(0.05)
        raise RuntimeError("sandbox worker did not publish state")

    def stop(self) -> None:
        process = self.process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
            except OSError:
                pass
        self.process = None
        self.pid_file.unlink(missing_ok=True)

    def inspect(self) -> dict[str, Any]:
        pid = self._pid()
        state: dict[str, Any] = {}
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        heartbeat = float(state.get("heartbeat") or 0)
        state.update({
            "pid": pid,
            "alive": self._alive(pid),
            "heartbeat_age_seconds": round(max(0.0, time.time() - heartbeat), 3) if heartbeat else None,
            "healthy": self._alive(pid) and state.get("status") == "healthy" and time.time() - heartbeat < 3,
            "target": "synthetic.local.worker",
            "os": {"system": platform.system(), "release": platform.release(), "python": platform.python_version()},
            "logs": self.logs(),
        })
        return state

    def logs(self) -> str:
        try:
            return self.log_file.read_text(encoding="utf-8")[-4000:]
        except OSError:
            return ""

    def reset(self) -> dict[str, Any]:
        self.stop()
        self.state_file.unlink(missing_ok=True)
        return self.start(hung=False)

    def close(self) -> None:
        self.stop()
