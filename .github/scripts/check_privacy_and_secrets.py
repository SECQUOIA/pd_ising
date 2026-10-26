"""Scan tracked files or diffs for absolute home paths, credentials, and emails.

This repository is public. This script fails when tracked files contain:
1. An absolute path under ``/home/<user>`` or ``/Users/<user>``
2. A string matching common API-token shapes or literal credential assignments
3. An email address in source or notebook content
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

HOME_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users)/[A-Za-z0-9._-]+")

# Common API token patterns and direct credential assignments in code/notebooks.
TOKEN_PATTERNS = (
    (
        "github-token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    ),
    (
        "github-pat",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    ),
    (
        "openai-or-sk-token",
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "dwave-token",
        re.compile(r"\bDEV-[0-9a-fA-F]{32,40}\b"),
    ),
    (
        "env-credential-assignment",
        re.compile(
            r'os\.environ\s*\[\s*\\?["\'](?:DWAVE_API_TOKEN|QCI_API_TOKEN|API_TOKEN)["\']\s*\]\s*='
        ),
    ),
)

EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Package metadata files may legitimately declare author contact metadata.
EMAIL_EXEMPT_FILES = frozenset(
    {
        "il-rxtor-sep-opt/pyproject.toml",
        "pyproject.toml",
        "Project.toml",
        "ds-mfg/Project.toml",
        "il-rxtor-sep-opt/Project.toml",
        "CITATION.cff",
    }
)

BINARY_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".ico", ".zip", ".gz", ".tar"}
)


def scan_text(text: str, path: str = "<stdin>") -> list[tuple[int, str, str]]:
    """Return ``(line_no, kind, snippet)`` violations found in *text*."""
    violations: list[tuple[int, str, str]] = []
    check_emails = path not in EMAIL_EXEMPT_FILES

    for line_no, line in enumerate(text.splitlines(), start=1):
        match = HOME_PATH_RE.search(line)
        if match:
            violations.append((line_no, "home-path", match.group(0)))

        for kind, pattern in TOKEN_PATTERNS:
            tmatch = pattern.search(line)
            if tmatch:
                violations.append((line_no, kind, tmatch.group(0)))

        if check_emails:
            ematch = EMAIL_RE.search(line)
            if ematch:
                violations.append((line_no, "email", ematch.group(0)))

    return violations


def tracked_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def scan_repository(repo_root: Path) -> list[tuple[str, int, str, str]]:
    findings: list[tuple[str, int, str, str]] = []
    for rel_path in tracked_files(repo_root):
        if Path(rel_path).suffix.lower() in BINARY_EXTENSIONS:
            continue
        file_path = repo_root / rel_path
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, kind, snippet in scan_text(text, path=rel_path):
            findings.append((rel_path, line_no, kind, snippet))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root to scan (default: parent of .github/).",
    )
    args = parser.parse_args(argv)

    findings = scan_repository(args.root.resolve())
    if not findings:
        print("No home paths, credentials, or unexpected email addresses found.")
        return 0

    print("Privacy / credential scan failed:\n")
    for rel_path, line_no, kind, snippet in findings:
        print(f"  {rel_path}:{line_no} [{kind}] {snippet}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
