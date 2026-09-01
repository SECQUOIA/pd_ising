"""Fail when a pull request changes a committed result or data file.

Committed results record runs that in several cases cannot be repeated: D-Wave and
QCI samplers are hardware-backed and stochastic, and the Gurobi runs need a licence.
Regenerating, reformatting, or renaming one of those files destroys the record.

Adding a new result file is ordinary work and is allowed -- that is how results
accumulate. Modifying, deleting, or renaming an existing one is what this check
blocks, so that it can only happen as a deliberate, labelled act.

Usage:
    git diff --name-status <base>...<head> | python check_protected_paths.py
"""

from __future__ import annotations

import sys
from pathlib import PurePosixPath

# Any path with one of these directories as a component is protected, at any depth.
PROTECTED_DIRS = frozenset(
    {
        "result_raw",
        "result_gurobi",
        "result_all_configs",
        "julia_exports",
        "data",
    }
)

# Protected only at the repository root.
PROTECTED_ROOTS = ("images",)

# Statuses that destroy or alter an existing file. "A" (add) is deliberately absent.
BLOCKED_STATUSES = {
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied over",
    "T": "type changed",
}

OVERRIDE_LABEL = "allow-result-changes"


def is_protected(path: str) -> bool:
    """True when *path* lies inside a protected results or data directory."""
    parts = PurePosixPath(path).parts
    if not parts:
        return False
    if parts[0] in PROTECTED_ROOTS:
        return True
    # The final component is the filename, so only directory components count.
    return any(part in PROTECTED_DIRS for part in parts[:-1])


def parse_diff(text: str) -> list[tuple[str, str]]:
    """Parse ``git diff --name-status`` output into (status, path) pairs.

    A rename or copy line carries two paths; the source path is the one at risk,
    since the rename removes it.
    """
    changes: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        status = fields[0][:1]
        # For R/C the source path is fields[1]; the destination is a new file.
        changes.append((status, fields[1]))
    return changes


def find_violations(text: str) -> list[tuple[str, str]]:
    """Return (status, path) for each change this check refuses."""
    return [
        (status, path)
        for status, path in parse_diff(text)
        if status in BLOCKED_STATUSES and is_protected(path)
    ]


def main() -> int:
    violations = find_violations(sys.stdin.read())
    if not violations:
        print("No committed result or data file was altered.")
        return 0

    print("This pull request alters files that record completed runs.\n")
    for status, path in violations:
        print(f"  {BLOCKED_STATUSES[status]:<14} {path}")
    print(
        "\nThese records cannot always be regenerated: the sampler runs are"
        "\nhardware-backed and stochastic, and the Gurobi runs need a licence."
        "\n"
        "\nAdding a new result file is allowed. If altering these files is genuinely"
        f"\nintended, apply the '{OVERRIDE_LABEL}' label to the pull request and say"
        "\nin the description why the existing record is being changed."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
