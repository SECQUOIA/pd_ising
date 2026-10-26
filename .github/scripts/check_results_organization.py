"""Validate organization, naming, and provenance of newly added result files.

Whereas ``check_protected_paths.py`` prevents pull requests from modifying or
deleting existing committed result records, this script enforces the repository
standard (Issue #4 and ``REPRODUCE.md``) on *newly added* result files:

1. **Canonical directory layout**:
   Result and export files must live under ``<subproject>/<workflow>/<kind>/``
   where ``<subproject>`` is ``ds-mfg`` or ``il-rxtor-sep-opt`` and ``<kind>``
   is one of ``result_raw``, ``result_gurobi`` (optionally ``replicates/``),
   ``result_all_configs``, or ``julia_exports``.
2. **Filename convention**:
   - Solver JSON records: ``<solver_or_model>_<YYYYMMDD_HHMMSS>[_<id>].json``
   - Replicate archives under ``replicates/``:
     ``<prefix>_replicates_<YYYYMMDD>[_<HHMMSS>].zip``
   - Julia QUBO exports under ``julia_exports/``:
     ``(Q_matrix|L_vector|scalars)[_<tag>].csv``
3. **Provenance metadata**:
   Every newly added ``.json`` result record (and every JSON entry inside a new
   replicate ``.zip`` archive) must be a JSON object containing a non-empty
   ``"run_info"`` or ``"meta"`` dictionary.
4. **Replicate PR flood guard**:
   A single pull request may add at most ``MAX_UNCOMPRESSED_REPLICATES_PER_PR``
   (20) loose ``.json`` files under ``replicates/``. Larger replicate sweeps
   must commit one representative ``.json`` file (to show the schema) plus a
   compressed ``.zip`` archive created with ``--bundle-replicates``.

Usage:
    git diff --name-status <base>...<head> | python .github/scripts/check_results_organization.py
    python .github/scripts/check_results_organization.py --bundle-replicates <replicates_dir>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile
from typing import Any

RESULT_DIRS = frozenset(
    {
        "result_raw",
        "result_gurobi",
        "result_all_configs",
        "julia_exports",
    }
)

VALID_SUBPROJECTS = frozenset({"ds-mfg", "il-rxtor-sep-opt"})

MAX_UNCOMPRESSED_REPLICATES_PER_PR = 20

# e.g. SA_results_20260114_163501.json, gurobi_pool_solutions_n10_20260204_164337_126559.json
RESULT_JSON_RE = re.compile(
    r"^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*_\d{8}_\d{6}(?:_\d+)?\.json$"
)

# e.g. gurobi_pool_replicates_20260204.zip or ilrs_gpool_replicates_20260204_155730.zip
REPLICATE_ARCHIVE_RE = re.compile(
    r"^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*_replicates_\d{8}(?:_\d{6})?\.zip$"
)

# e.g. Q_matrix.csv, Q_matrix_1.csv, L_vector_20260114.csv, scalars.csv
JULIA_EXPORT_CSV_RE = re.compile(
    r"^(?:Q_matrix|L_vector|scalars)(?:_[A-Za-z0-9]+)*\.csv$"
)


def is_result_or_export_path(path: str) -> bool:
    """Return True if *path* is inside one of the managed result/export directories."""
    parts = PurePosixPath(path).parts
    return any(part in RESULT_DIRS for part in parts[:-1])


def parse_added_paths(diff_text: str) -> list[str]:
    """Return newly introduced paths (``A`` or ``R``/``C`` destination) from ``git diff --name-status``."""
    added: list[str] = []
    for line in diff_text.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        status = fields[0].strip()
        if status == "A":
            added.append(fields[1].strip())
        elif status.startswith(("R", "C")) and len(fields) >= 3:
            added.append(fields[2].strip())
    return added


def _validate_json_provenance(data: Any, label: str) -> list[str]:
    if not isinstance(data, dict):
        return [f"{label}: top-level JSON value must be an object (dict)"]
    provenance = (
        data.get("run_info") or data.get("meta") or data.get("Pool Search Info")
    )
    if not isinstance(provenance, dict) or not provenance:
        return [
            f"{label}: missing non-empty 'run_info' or 'meta' provenance dictionary"
        ]
    return []


def validate_result_file(rel_path: str, repo_root: Path) -> list[str]:
    """Validate layout, filename, and provenance of a single newly added result file."""
    errors: list[str] = []
    posix = PurePosixPath(rel_path)
    parts = posix.parts

    if len(parts) < 4 or parts[0] not in VALID_SUBPROJECTS:
        return [
            f"{rel_path}: result/export files must live under "
            f"<subproject>/<workflow>/<result_dir>/ (subproject in {sorted(VALID_SUBPROJECTS)})"
        ]

    result_dir_indices = [i for i, part in enumerate(parts[:-1]) if part in RESULT_DIRS]
    if len(result_dir_indices) != 1 or result_dir_indices[0] != 2:
        return [
            f"{rel_path}: expected canonical path <subproject>/<workflow>/<result_dir>/<file>"
        ]

    idx = result_dir_indices[0]
    result_dir = parts[idx]
    subparts = parts[idx + 1 :]
    filename = parts[-1]
    full_path = repo_root / rel_path

    if result_dir == "julia_exports":
        if len(subparts) != 1 or not JULIA_EXPORT_CSV_RE.match(filename):
            errors.append(
                f"{rel_path}: julia_exports files must match "
                "(Q_matrix|L_vector|scalars)[_<tag>].csv directly under julia_exports/"
            )
        return errors

    # Allow either direct placement or a single replicates/ subdirectory.
    in_replicates = False
    if len(subparts) == 2 and subparts[0] == "replicates":
        in_replicates = True
    elif len(subparts) != 1:
        errors.append(
            f"{rel_path}: unexpected subdirectory under {result_dir}/ "
            "(only direct files or 'replicates/' are permitted)"
        )
        return errors

    if in_replicates and REPLICATE_ARCHIVE_RE.match(filename):
        if full_path.is_file() and filename.endswith(".zip"):
            try:
                with zipfile.ZipFile(full_path, "r") as zf:
                    json_members = [
                        m for m in zf.namelist() if not m.endswith("/") and m.endswith(".json")
                    ]
                    if not json_members:
                        errors.append(
                            f"{rel_path}: replicate archive must contain at least one .json file"
                        )
                    for member in json_members:
                        member_name = PurePosixPath(member).name
                        if not RESULT_JSON_RE.match(member_name):
                            errors.append(
                                f"{rel_path}::{member}: archive member {member_name!r} "
                                "must match <prefix>_<YYYYMMDD_HHMMSS>[_<id>].json"
                            )
                        raw = json.loads(zf.read(member).decode("utf-8"))
                        errors.extend(
                            _validate_json_provenance(raw, f"{rel_path}::{member}")
                        )
            except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"{rel_path}: invalid replicate zip archive ({exc})")
        return errors

    if not RESULT_JSON_RE.match(filename):
        errors.append(
            f"{rel_path}: filename {filename!r} must match "
            "<solver_or_model>_<YYYYMMDD_HHMMSS>[_<id>].json"
            + (
                " or <prefix>_replicates_<YYYYMMDD>.zip"
                if in_replicates
                else ""
            )
        )
        return errors

    if full_path.is_file():
        try:
            payload = json.loads(full_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"{rel_path}: invalid JSON file ({exc})")
            return errors
        errors.extend(_validate_json_provenance(payload, rel_path))

    return errors


def validate_diff(
    diff_text: str,
    repo_root: Path,
    max_uncompressed_replicates: int = MAX_UNCOMPRESSED_REPLICATES_PER_PR,
) -> list[str]:
    """Validate all newly added result/export files in ``git diff --name-status``."""
    errors: list[str] = []
    added_result_paths = [
        path for path in parse_added_paths(diff_text) if is_result_or_export_path(path)
    ]

    uncompressed_replicates: list[str] = []
    added_replicate_archives: list[str] = []
    for rel_path in added_result_paths:
        parts = PurePosixPath(rel_path).parts
        if "replicates" in parts[:-1]:
            if rel_path.endswith(".json"):
                uncompressed_replicates.append(rel_path)
            elif REPLICATE_ARCHIVE_RE.match(parts[-1]):
                added_replicate_archives.append(rel_path)
        errors.extend(validate_result_file(rel_path, repo_root))

    for archive_rel in added_replicate_archives:
        rep_parent = PurePosixPath(archive_rel).parent
        has_rep_in_diff = any(
            PurePosixPath(p).parent == rep_parent and p.endswith(".json")
            for p in uncompressed_replicates
        )
        rep_dir_disk = repo_root / str(rep_parent)
        has_rep_on_disk = rep_dir_disk.is_dir() and any(rep_dir_disk.glob("*.json"))
        if not (has_rep_in_diff or has_rep_on_disk):
            errors.append(
                f"{archive_rel}: replicate archive must be accompanied by at least "
                f"one representative .json file in {rep_parent}/"
            )

    if len(uncompressed_replicates) > max_uncompressed_replicates:
        errors.append(
            f"PR adds {len(uncompressed_replicates)} loose JSON files under replicates/ "
            f"(limit: {max_uncompressed_replicates}). Commit 1 representative .json file "
            "plus a compressed <prefix>_replicates_<YYYYMMDD>.zip archive using "
            "'python .github/scripts/check_results_organization.py --bundle-replicates <dir>'."
        )

    return errors


def bundle_replicates(
    replicates_dir: Path,
    archive_name: str | None = None,
    keep_representative: bool = True,
    delete_bundled: bool = False,
) -> tuple[Path, Path | None]:
    """Bundle loose ``*.json`` files in *replicates_dir* into a deterministic ``.zip``.

    Returns ``(archive_path, representative_json_path)``. By default, keeps the
    lexicographically first ``.json`` file unpacked as the schema representative.
    """
    json_files = sorted(p for p in replicates_dir.glob("*.json") if p.is_file())
    if not json_files:
        raise ValueError(f"No .json files found in {replicates_dir}")

    representative = json_files[0] if keep_representative else None
    if archive_name is None:
        m = re.match(r"^([A-Za-z0-9_]+?)_(\d{8})_\d{6}", json_files[0].stem)
        if m:
            prefix, date_str = m.group(1), m.group(2)
        else:
            prefix, date_str = "solver", "00000000"
        archive_name = f"{prefix}_replicates_{date_str}.zip"
    elif not REPLICATE_ARCHIVE_RE.match(archive_name):
        raise ValueError(
            f"Invalid archive_name {archive_name!r}: must match "
            "<prefix>_replicates_<YYYYMMDD>[_<HHMMSS>].zip"
        )

    archive_path = replicates_dir / archive_name
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in json_files:
            info = zipfile.ZipInfo(filename=path.name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())

    if delete_bundled:
        for path in json_files:
            if representative is not None and path == representative:
                continue
            path.unlink()

    return archive_path, representative


def load_replicate_records(replicates_dir: Path) -> dict[str, dict[str, Any]]:
    """Load replicate JSON records from both loose ``*.json`` and ``*_replicates_*.zip``."""
    records: dict[str, dict[str, Any]] = {}
    for archive_path in sorted(replicates_dir.glob("*_replicates_*.zip")):
        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in sorted(zf.namelist()):
                if member.endswith(".json") and not member.endswith("/"):
                    name = PurePosixPath(member).name
                    records[name] = json.loads(zf.read(member).decode("utf-8"))
    for json_path in sorted(replicates_dir.glob("*.json")):
        records[json_path.name] = json.loads(json_path.read_text(encoding="utf-8"))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root directory.",
    )
    parser.add_argument(
        "--bundle-replicates",
        type=Path,
        metavar="REPLICATES_DIR",
        help="Bundle loose *.json replicate files in REPLICATES_DIR into a .zip archive.",
    )
    parser.add_argument(
        "--archive-name",
        type=str,
        default=None,
        help="Optional archive filename for --bundle-replicates.",
    )
    parser.add_argument(
        "--delete-bundled",
        action="store_true",
        help="Delete bundled loose .json files except the representative file.",
    )
    args = parser.parse_args(argv)

    if args.bundle_replicates is not None:
        archive_path, rep_path = bundle_replicates(
            args.bundle_replicates.resolve(),
            archive_name=args.archive_name,
            keep_representative=True,
            delete_bundled=args.delete_bundled,
        )
        print(f"Created replicate archive: {archive_path}")
        if rep_path is not None:
            print(f"Representative schema file retained: {rep_path}")
        return 0

    diff_text = sys.stdin.read()
    errors = validate_diff(diff_text, args.root.resolve())
    if not errors:
        print("Result file organization, naming, and provenance checks passed.")
        return 0

    print("Result file organization / provenance check failed:\n")
    for err in errors:
        print(f"  - {err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
