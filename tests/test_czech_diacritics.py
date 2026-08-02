import re
from pathlib import Path

# Regular expression to find Czech diacritic characters (lowercase and uppercase)
CZECH_DIACRITICS_RE = re.compile(r"[áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]")


def test_no_czech_diacritics_in_code() -> None:
    """Ensure that no Czech diacritics are written in python source files."""
    app_dir = Path(__file__).parent.parent / "src"
    violating_lines: list[str] = []

    # Recursively traverse all .py files in src/ directory
    for py_file in app_dir.glob("**/*.py"):
        content = py_file.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), 1):
            if CZECH_DIACRITICS_RE.search(line):
                # Store relative path, line number, and the stripped line
                rel_path = py_file.relative_to(app_dir.parent)
                violating_lines.append(f"{rel_path}:{line_num} -> {line.strip()}")

    # If any Czech characters are found, the test fails
    assert not violating_lines, (
        "Found Czech diacritics in python codebase. Please keep all code, comments, "
        "and strings in English. Violations:\n" + "\n".join(violating_lines)
    )
