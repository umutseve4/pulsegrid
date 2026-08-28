#!/usr/bin/env python3
"""Fail-closed documentation validation for PulseGrid M0."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md",
    "docs/M0_PRODUCT_CONTRACT.md",
    "docs/M0_ACCEPTANCE.md",
    "docs/VISUAL_STORYBOARD.md",
    "docs/adr/0001-smallest-honest-architecture.md",
)
CANONICAL_CHECKLIST = ROOT / "docs/M0_ACCEPTANCE.md"
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
FORBIDDEN_PROMOTIONAL_CLAIMS = (
    re.compile(r"\bproduction[- ]ready\b", re.IGNORECASE),
    re.compile(r"\b(Kafka|Spark|Databricks|Kubernetes)[- ](?:backed|powered)\b", re.IGNORECASE),
    re.compile(r"\blive now\b", re.IGNORECASE),
    re.compile(r"\bhandles\s+[\d,.]+\s*(?:rps|events?/s)\b", re.IGNORECASE),
)


def markdown_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*.md") if ".git" not in path.parts)


def validate() -> list[str]:
    errors: list[str] = []

    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")

    files = markdown_files()
    for path in files:
        relative = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        if text and not text.endswith("\n"):
            errors.append(f"{relative}: missing final newline")
        for number, line in enumerate(lines, start=1):
            if line != line.rstrip():
                errors.append(f"{relative}:{number}: trailing whitespace")
            if "\t" in line:
                errors.append(f"{relative}:{number}: tab character")

        for target in MARKDOWN_LINK.findall(text):
            clean = target.split("#", 1)[0].strip()
            if not clean or clean.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (path.parent / clean).resolve()
            if ROOT not in resolved.parents and resolved != ROOT:
                errors.append(f"{relative}: link escapes repository: {target}")
            elif not resolved.exists():
                errors.append(f"{relative}: broken local link: {target}")

        if path.name != "validate_docs.py":
            for pattern in FORBIDDEN_PROMOTIONAL_CLAIMS:
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    errors.append(
                        f"{relative}:{line}: forbidden promotional claim: {match.group(0)!r}"
                    )

        if path != CANONICAL_CHECKLIST:
            for number, line in enumerate(lines, start=1):
                if re.match(r"^\s*- \[[ xX]\] ", line):
                    errors.append(
                        f"{relative}:{number}: checklist duplicated outside docs/M0_ACCEPTANCE.md"
                    )

    if CANONICAL_CHECKLIST.is_file():
        checklist = CANONICAL_CHECKLIST.read_text(encoding="utf-8")
        gates = re.findall(r"^- \[[ xX]\] ", checklist, flags=re.MULTILINE)
        if len(gates) != 10:
            errors.append(
                f"docs/M0_ACCEPTANCE.md: expected 10 canonical gates, found {len(gates)}"
            )

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Documentation validation passed.")
    print(f"Validated {len(markdown_files())} Markdown files and 10 canonical M0 gates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
