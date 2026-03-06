import re
from pathlib import Path


def split_into_sections(text: str) -> list[dict]:
    """Split markdown text into sections by headers. Returns list of {heading, body}."""
    sections = []
    current_heading = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        header_match = re.match(r"^(#{1,4})\s+(.*)", line)
        if header_match and current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append({"heading": current_heading, "body": body})
            current_heading = header_match.group(2).strip()
            current_lines = []
        elif header_match:
            current_heading = header_match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append({"heading": current_heading, "body": body})

    return [s for s in sections if len(s["body"]) >= 20]


def discover_auto_memory_dirs() -> list[Path]:
    """Find all Claude Code auto-memory directories."""
    base = Path("~/.claude/projects").expanduser()
    if not base.exists():
        return []

    dirs = []
    for project_dir in base.iterdir():
        memory_dir = project_dir / "memory"
        if memory_dir.is_dir():
            dirs.append(memory_dir)
    return dirs


def discover_memory_files() -> list[Path]:
    """Find all memory files that could be migrated."""
    files = []

    # User-level CLAUDE.md
    user_claude = Path("~/.claude/CLAUDE.md").expanduser()
    if user_claude.exists():
        files.append(user_claude)

    # Auto-memory files
    for memory_dir in discover_auto_memory_dirs():
        for md_file in sorted(memory_dir.glob("*.md")):
            files.append(md_file)

    return files


def read_and_split_file(file_path: Path) -> dict:
    """Read a file and split it into sections for review."""
    content = file_path.read_text()
    sections = split_into_sections(content)
    return {
        "file": str(file_path),
        "section_count": len(sections),
        "sections": sections,
    }
