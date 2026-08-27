#!/usr/bin/env python3
"""
Pre-commit checks for Jupyter notebooks. Two independent checks:

1. Hardcoded secrets in cell source -- BLOCKS the commit (exit 1).
   A credential in a notebook cell is never intentional, and once pushed it is
   compromised and must be rotated. Blocking is the only useful behaviour.

2. Cell outputs / execution counts -- WARNS only (never blocks).
   Outputs bloat diffs, churn on every re-run, and can leak absolute data paths
   or record counts. But a deliberately-rendered example notebook is legitimate,
   so this stays a warning.

Read credentials from the environment instead of inlining them:

    import os
    from dotenv import load_dotenv

    load_dotenv()
    storage_options = {
        "key": os.environ["S3_ACCESS_KEY"],
        "secret": os.environ["S3_SECRET_KEY"],
        "client_kwargs": {"endpoint_url": os.environ["S3_ENDPOINT"]},
    }

Note `os.environ[...]` rather than `os.getenv(..., <literal fallback>)` -- a
literal fallback is how a hardcoded secret survives a load_dotenv() that silently
failed to find its .env.

To strip outputs:  jupyter nbconvert --clear-output --inplace <notebook>
"""

import json
import re
import sys

# Keys whose *value* is a credential. Matches "secret": "<20+ chars>" and friends
# in notebook source, i.e. an assignment to a string literal rather than a lookup.
SECRET_KEY_PATTERN = re.compile(
    r"""["']?(?:secret|password|passwd|token|api[_-]?key|access[_-]?key|"""
    r"""secret[_-]?key|aws_secret_access_key|aws_access_key_id)["']?"""
    r"""\s*[:=]\s*["']([^"']{16,})["']""",
    re.IGNORECASE,
)

# AWS-style access key IDs, and the long opaque keys Ceph/Nautilus issues.
AWS_KEY_ID_PATTERN = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")

# Values that are obviously not real credentials.
PLACEHOLDER = re.compile(
    r"^(?:your|my|the|xxx|placeholder|example|changeme|dummy|fake|test|"
    r"<.*>|\{\{.*\}\}|\$\{.*\}|\.\.\.|\*+)",
    re.IGNORECASE,
)


def _is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER.match(value.strip()))


def scan(path: str) -> tuple[list[tuple[int, str]], int, int]:
    """Return (secret_findings, cells_with_outputs, cells_with_exec_counts)."""
    try:
        with open(path, encoding="utf-8") as handle:
            notebook = json.load(handle)
    except (OSError, json.JSONDecodeError):
        # Unreadable/invalid notebooks are other hooks' problem.
        return ([], 0, 0)

    findings: list[tuple[int, str]] = []
    with_outputs = 0
    with_counts = 0

    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue

        if cell.get("outputs"):
            with_outputs += 1
        if cell.get("execution_count") is not None:
            with_counts += 1

        source = "".join(cell.get("source", []))

        for match in SECRET_KEY_PATTERN.finditer(source):
            value = match.group(1)
            if _is_placeholder(value):
                continue
            # Report a redacted fragment so the log itself never carries the secret.
            findings.append(
                (
                    index,
                    f"{match.group(0).split(':')[0].strip()} = "
                    f"{value[:4]}...{value[-2:]} ({len(value)} chars)",
                )
            )

        for match in AWS_KEY_ID_PATTERN.finditer(source):
            key_id = match.group(0)
            findings.append((index, f"AWS-style key id {key_id[:8]}..."))

    return (findings, with_outputs, with_counts)


def main(paths: list[str]) -> int:
    secret_hits: list[tuple[str, list[tuple[int, str]]]] = []
    output_hits: list[tuple[str, int, int]] = []

    for path in paths:
        findings, with_outputs, with_counts = scan(path)
        if findings:
            secret_hits.append((path, findings))
        if with_outputs or with_counts:
            output_hits.append((path, with_outputs, with_counts))

    if output_hits:
        print("")
        print("WARNING: notebook(s) staged with cell outputs:")
        for path, with_outputs, with_counts in output_hits:
            print(
                f"  {path}  ({with_outputs} cells with outputs, "
                f"{with_counts} with execution counts)"
            )
        print("")
        print("Outputs bloat diffs and can leak data paths, tokens, or record counts.")
        print("If that is not intended, strip them and re-stage:")
        for path, _, _ in output_hits:
            print(f"  jupyter nbconvert --clear-output --inplace {path}")
        print("")
        print("(Warning only -- this does not block the commit.)")
        print("")

    if secret_hits:
        print("")
        print("BLOCKED: possible hardcoded credential(s) in notebook cell source:")
        for path, findings in secret_hits:
            for cell_index, detail in findings:
                print(f"  {path}  cell {cell_index}:  {detail}")
        print("")
        print("Read credentials from the environment instead:")
        print('    load_dotenv(); os.environ["S3_SECRET_KEY"]')
        print("")
        print("Avoid os.getenv(KEY, '<literal>') -- a literal fallback is how a")
        print("hardcoded secret survives a load_dotenv() that found no .env file.")
        print("")
        print("If this value is already committed and pushed, treat it as")
        print("compromised: rotate it first, then purge it from history.")
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
