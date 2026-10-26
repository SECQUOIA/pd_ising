## Summary

<!-- Briefly describe the purpose of this pull request and link any related issues (e.g., Closes #...). -->

## What to Review (Primary Code & Notebook Targets)

<!-- List the scripts, modules, tests, and notebooks that require manual code review. -->
- 

## Generated Result & Export Artifacts (Out of Scope for Line-by-Line Code Review)

<!-- If this PR adds generated solver outputs (`result_raw/`, `result_gurobi/`, `julia_exports/`), summarize them as a group here rather than listing every file individually. GitHub collapses these paths in diffs via `.gitattributes` (`linguist-generated=true`). -->
- **Directories touched:** `None`
- **File count & format:** `0 files` (for multi-seed `replicates/` sweeps, commit 1 representative `.json` file to show the schema plus a compressed `<prefix>_replicates_<YYYYMMDD>.zip` archive)
- **Representative file (for schema inspection):** `N/A`
- **`REPRODUCE.md` provenance row updated:** `[ ] Yes / [ ] N/A`

## Review & Reproducibility Checklist

- [ ] Code/model changes and generated result records are clearly separated in the description above
- [ ] Newly added `.json` result files follow `<solver_or_model>_<kind>_<YYYYMMDD_HHMMSS>.json` and include `run_info` or `meta` provenance metadata
- [ ] Existing committed result and data files were not modified, renamed, or deleted (enforced by `protect-results` CI)
- [ ] `python .github/scripts/check_privacy_and_secrets.py` and `pytest` pass locally
