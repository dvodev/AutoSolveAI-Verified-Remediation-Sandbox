"""Local, dependency-free release-boundary checks for the public submission.

The checker intentionally reports only high-confidence credential signatures;
it is a release aid, not a replacement for an enterprise secret scanner.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any


_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}")),
)
_SKIP_PARTS = {".git", "data", "__pycache__", ".venv", "venv", "node_modules"}
_SENSITIVE_NAME = re.compile(r"(?:^|[._-])(secret|secrets|credential|credentials|password|token)(?:$|[._-])", re.I)


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or any(part in _SKIP_PARTS for part in path.relative_to(root).parts):
            continue
        yield path


def scan_secrets(root: str | Path) -> list[dict[str, Any]]:
    """Return high-confidence secret matches with safe, non-value snippets."""
    root = Path(root).resolve()
    findings: list[dict[str, Any]] = []
    for path in _iter_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for label, pattern in _SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append({"pattern": label, "path": str(path.relative_to(root)), "line": line_number})
    return findings


def sensitive_filenames(root: str | Path) -> list[str]:
    """Find likely sensitive filenames, excluding the intentionally empty template."""
    root = Path(root).resolve()
    result = []
    for path in _iter_files(root):
        relative = path.relative_to(root)
        if path.name in {".env.example"}:
            continue
        if path.name == ".env" or _SENSITIVE_NAME.search(path.name) or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
            result.append(str(relative))
    return sorted(result)


def git_status(root: str | Path) -> list[str] | None:
    try:
        result = subprocess.run(["git", "status", "--porcelain"], cwd=Path(root), text=True, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return [line for line in result.stdout.splitlines() if line.strip()]


def release_check(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root).resolve()
    required = ["README.md", "SUBMISSION.md", "DEMO_SCRIPT.md", "BUILD_LOG.md", ".env.example", "pyproject.toml", "tests"]
    missing = [item for item in required if not (root / item).exists()]
    secrets = scan_secrets(root)
    names = sensitive_filenames(root)
    status = git_status(root)
    result = {
        "ready": not missing and not secrets and not names and status in ([], None),
        "missing_files": missing,
        "secret_findings": secrets,
        "sensitive_filenames": names,
        "git_status": status,
    }
    return result
