"""Markdown parsing for the implement plan and story-testplan templates."""

import re


def visible_lines(text):
    """Mask fenced examples while preserving offsets for targeted edits."""
    fence = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            if (marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence)
                    and re.fullmatch(r"[ \t]*", line[marker.end():].rstrip("\r\n"))):
                fence = None
            yield " " * len(line.rstrip("\r\n")) + line[len(line.rstrip("\r\n")):]
        elif marker:
            fence = marker[1]
            yield " " * len(line.rstrip("\r\n")) + line[len(line.rstrip("\r\n")):]
        else:
            yield line


def sections(text, level):
    masked = "".join(visible_lines(text))
    headings = list(re.finditer(r"^(#{1,6})[ \t]+(.+?)[ \t]*\r?$", masked, re.M))
    result = []
    for i, heading in enumerate(headings):
        if len(heading[1]) != level:
            continue
        end = next((h.start() for h in headings[i + 1:] if len(h[1]) <= level), len(text))
        result.append((heading[2], heading.end(), end))
    return result


def section(text, title):
    matches = [(a, b) for name, a, b in sections(text, 2) if name == title]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one '## {title}' section")
    return matches[0]


def tasks(text):
    start, end = section(text, "Task Breakdown")
    result = {}
    for title, a, b in sections(text[start:end], 3):
        match = re.fullmatch(r"Task ([1-9][0-9]*): .+", title)
        if not match:
            raise ValueError(f"Unsupported task heading: {title}")
        number = int(match[1])
        if number in result:
            raise ValueError(f"Duplicate Task {number}")
        result[number] = (start + a, start + b)
    if not result:
        raise ValueError("No task headings found")
    return result
