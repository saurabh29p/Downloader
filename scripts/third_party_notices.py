"""Regenerate the dependency tables in THIRD_PARTY_NOTICES.md (`make notices`).

Run with the API's environment so Python package metadata is readable:
    uv run --project apps/api python scripts/third_party_notices.py

npm: `pnpm licenses list --prod --json -r` (production dependencies of every workspace).
PyPI: the API's runtime dependencies (`uv export --no-dev`), licences read from the
installed packages' metadata. Licences that are not MIT-compatible when linked into
AnyGet are flagged so a person can check how the package is used.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"
START = "<!-- generated:start (make notices) -->"
END = "<!-- generated:end -->"

# Strong copyleft or non-commercial terms: fine for a separate program, not for code
# linked into AnyGet. Weak copyleft (LGPL, MPL) is fine when used unmodified.
STRONG = re.compile(r"\b(A?GPL|SSPL|CC-BY-NC|Commons Clause|proprietary)", re.IGNORECASE)
WEAK = re.compile(r"\b(LGPL|MPL|EPL|CDDL)", re.IGNORECASE)


def flag(licence: str) -> str:
    if not licence or licence.upper() == "UNKNOWN":
        return "⚠ unknown: check"
    if STRONG.search(licence) and not re.search(r"\bLGPL", licence, re.IGNORECASE):
        return "⚠ copyleft: see the notes above"
    if WEAK.search(licence):
        return "weak copyleft, used unmodified"
    return ""


def npm_packages() -> list[tuple[str, str, str]]:
    out = subprocess.run(
        ["pnpm", "licenses", "list", "--prod", "--json", "-r"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    rows: set[tuple[str, str, str]] = set()
    for licence, packages in json.loads(out).items():
        for package in packages:
            for version in package.get("versions", [package.get("version", "")]):
                rows.add((package["name"], version, licence))
    return sorted(rows, key=lambda r: (r[0].lower(), r[1]))


def python_licence(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return expression.strip()
    classifiers = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::") and "OSI Approved" not in c.split("::")[-1]
    ]
    if classifiers:
        return " / ".join(dict.fromkeys(classifiers))
    text = (meta.get("License") or "").strip()
    # Some packages put the whole licence text here; keep only a short name.
    return text if text and "\n" not in text and len(text) < 60 else "UNKNOWN"


def python_packages() -> list[tuple[str, str, str]]:
    out = subprocess.run(
        ["uv", "export", "--no-dev", "--no-hashes", "--no-emit-project", "-q"],
        cwd=ROOT / "apps" / "api",
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    names = []
    for line in out.splitlines():
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==", line)
        if match:
            names.append(match.group(1))
    rows = []
    for name in names:
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            rows.append((name, "", "not installed here"))
            continue
        rows.append((dist.metadata["Name"], dist.version, python_licence(dist)))
    return sorted(set(rows), key=lambda r: r[0].lower())


def table(rows: list[tuple[str, str, str]]) -> str:
    lines = ["| Package | Version | Licence | Note |", "|---|---|---|---|"]
    for name, version, licence in rows:
        clean = licence.replace("|", "/")
        lines.append(f"| {name} | {version} | {clean} | {flag(licence)} |")
    return "\n".join(lines)


def main() -> int:
    npm = npm_packages()
    py = python_packages()
    flagged = [r for r in npm + py if flag(r[2]).startswith("⚠")]
    body = "\n".join(
        [
            START,
            "",
            f"### npm (production dependencies of every workspace: {len(npm)})",
            "",
            table(npm),
            "",
            f"### PyPI (runtime dependencies of `apps/api`: {len(py)})",
            "",
            table(py),
            "",
            END,
        ]
    )
    text = NOTICES.read_text(encoding="utf-8")
    if START not in text or END not in text:
        print(f"{NOTICES.name} has no generated markers", file=sys.stderr)
        return 1
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    NOTICES.write_text(head + body + tail, encoding="utf-8")
    print(f"{len(npm)} npm and {len(py)} PyPI packages written to {NOTICES.name}")
    for name, version, licence in flagged:
        print(f"  check: {name} {version} ({licence})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
