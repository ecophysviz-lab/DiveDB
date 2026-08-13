#!/usr/bin/env python3
"""
Warn when a Jupyter notebook is about to be committed with its cell outputs.

Committed outputs bloat diffs (they are frequently the bulk of a notebook's line
count), churn on every re-run, and can leak absolute data paths, API tokens, or
record counts into the repo's history.

This hook only warns -- it always exits 0, so it never blocks a commit. Sometimes
outputs are deliberate (a published, rendered example notebook). The point is that
it should be a decision, not an accident.

To strip outputs from a notebook:

    jupyter nbconvert --clear-output --inplace <notebook>
"""

import json
import sys


def outputs_in(path: str) -> tuple[int, int]:
    """Return (cells_with_outputs, cells_with_execution_count) for a notebook."""
    try:
        with open(path, encoding="utf-8") as handle:
            notebook = json.load(handle)
    except (OSError, json.JSONDecodeError):
        # Not our job to police unreadable/invalid notebooks; other hooks cover that.
        return (0, 0)

    with_outputs = 0
    with_counts = 0
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        if cell.get("outputs"):
            with_outputs += 1
        if cell.get("execution_count") is not None:
            with_counts += 1
    return (with_outputs, with_counts)


def main(paths: list[str]) -> int:
    flagged = []
    for path in paths:
        with_outputs, with_counts = outputs_in(path)
        if with_outputs or with_counts:
            flagged.append((path, with_outputs, with_counts))

    if flagged:
        print("")
        print("WARNING: notebook(s) staged with cell outputs:")
        for path, with_outputs, with_counts in flagged:
            print(
                f"  {path}  ({with_outputs} cells with outputs, "
                f"{with_counts} with execution counts)"
            )
        print("")
        print("Outputs bloat diffs and can leak data paths, tokens, or record counts.")
        print("If that is not intended, strip them and re-stage:")
        for path, _, _ in flagged:
            print(f"  jupyter nbconvert --clear-output --inplace {path}")
        print("")
        print("(This is a warning only -- the commit will proceed.)")
        print("")

    # Always succeed: warn, never block.
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
