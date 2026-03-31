"""
Validate satellite JSON datasets before running expensive protocol simulations.

This script enforces integrity-first checks and can optionally copy validated
files into data_raw/ for reproducible runs.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, List


# Required keys are aligned with handoff/manifest expectations.
REQUIRED_KEYS = [
    "OBJECT_NAME",
    "OBJECT_ID",
    "EPOCH",
    "MEAN_MOTION",
    "INCLINATION",
    "NORAD_CAT_ID",
]


def _validate_file(path: Path) -> Dict[str, object]:
    """Return validation summary and pass/fail signals for one JSON file."""
    summary: Dict[str, object] = {
        "file": path.name,
        "exists": path.exists(),
        "size_bytes": 0,
        "json_parse_ok": False,
        "record_count": 0,
        "missing_required_rows": 0,
        "non_object_rows": 0,
    }

    if not path.exists():
        return summary

    summary["size_bytes"] = path.stat().st_size
    if summary["size_bytes"] == 0:
        return summary

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return summary

    summary["json_parse_ok"] = True
    if not isinstance(data, list):
        return summary

    summary["record_count"] = len(data)

    missing_required_rows = 0
    non_object_rows = 0
    for row in data:
        if not isinstance(row, dict):
            non_object_rows += 1
            continue
        missing = [key for key in REQUIRED_KEYS if key not in row or row[key] is None]
        if missing:
            missing_required_rows += 1

    summary["missing_required_rows"] = missing_required_rows
    summary["non_object_rows"] = non_object_rows
    return summary


def _print_report(reports: List[Dict[str, object]]) -> None:
    """Print a compact integrity report for all files."""
    print("DATASET VALIDATION REPORT")
    print("=" * 80)
    for report in reports:
        print(f"file: {report['file']}")
        print(f"  exists: {report['exists']}")
        print(f"  size_bytes: {report['size_bytes']}")
        print(f"  json_parse_ok: {report['json_parse_ok']}")
        print(f"  record_count: {report['record_count']}")
        print(f"  missing_required_rows: {report['missing_required_rows']}")
        print(f"  non_object_rows: {report['non_object_rows']}")
    print("=" * 80)


def _is_report_valid(report: Dict[str, object]) -> bool:
    """A file is valid only when all hard integrity checks pass."""
    return bool(
        report["exists"]
        and int(report["size_bytes"]) > 0
        and report["json_parse_ok"]
        and int(report["record_count"]) > 0
        and int(report["missing_required_rows"]) == 0
        and int(report["non_object_rows"]) == 0
    )


def _copy_validated_files(source_dir: Path, target_dir: Path, reports: List[Dict[str, object]]) -> None:
    """Copy only validated files into data_raw to preserve immutable inputs."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for report in reports:
        if not _is_report_valid(report):
            continue
        src = source_dir / str(report["file"])
        dst = target_dir / str(report["file"])
        shutil.copy2(src, dst)
        print(f"copied: {src} -> {dst}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate rerun JSON datasets.")
    parser.add_argument(
        "--input-dir",
        default="Dataset",
        help="Directory containing raw JSON files to validate.",
    )
    parser.add_argument(
        "--copy-to-data-raw",
        action="store_true",
        help="Copy validated files into satellite-rerun-ssc26/data_raw.",
    )
    parser.add_argument(
        "--data-raw-dir",
        default="satellite-rerun-ssc26/data_raw",
        help="Destination directory for validated raw file copies.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"ERROR: input directory not found: {input_dir}")
        return 1

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        print(f"ERROR: no JSON files found in {input_dir}")
        return 1

    reports = [_validate_file(path) for path in json_files]
    _print_report(reports)

    all_valid = all(_is_report_valid(report) for report in reports)
    if args.copy_to_data_raw and all_valid:
        _copy_validated_files(input_dir, Path(args.data_raw_dir), reports)
    elif args.copy_to_data_raw and not all_valid:
        print("ERROR: copy skipped because one or more files failed validation.")

    if not all_valid:
        print("VALIDATION_STATUS: FAIL")
        return 1

    print("VALIDATION_STATUS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

