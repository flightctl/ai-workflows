#!/usr/bin/env python3
"""Render one structured bug description as Markdown or Jira ADF.

The structured input is the source of truth. Templates control block ordering
but cannot introduce arbitrary Markdown, and renderers never reinterpret input
values as markup.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

REQUIRED = {
    "description",
    "reproducibility",
    "steps",
    "actual_results",
    "expected_results",
}
SCALARS = REQUIRED - {"steps"} | {"environment", "severity"}
SUPPORTED = SCALARS | {"steps", "diagnostics", "links"}
MODEL_FIELDS = SUPPORTED | {"assistant"}
PLACEHOLDER = re.compile(r"^\{\{([a-z_]+)\}\}$")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SKILL_FILE = Path(__file__).resolve().parents[1] / "SKILL.md"


class RenderError(ValueError):
    """Input or template cannot be rendered without guessing."""


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RenderError(f"{name} must be a non-empty string")
    return value


def _http_url(value: Any, name: str) -> str:
    """Validate a link target without accepting embedded credentials."""
    url = _string(value, name)
    if any(character.isspace() or ord(character) < 32 for character in url):
        raise RenderError(f"{name} must not contain whitespace or control characters")
    parsed = urlsplit(url)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise RenderError(f"{name} must be an absolute HTTP(S) URL without credentials")
    return url


def validate_model(raw: Any) -> dict[str, Any]:
    """Validate and normalize a decoded structured bug-description object."""
    if not isinstance(raw, dict):
        raise RenderError("input must be a JSON object")
    unknown = set(raw) - MODEL_FIELDS
    if unknown:
        raise RenderError("input has unsupported fields: " + ", ".join(sorted(unknown)))
    model = dict(raw)
    for name in SCALARS & REQUIRED:
        model[name] = _string(model.get(name), name)
    steps = model.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RenderError("steps must be a non-empty array")
    model["steps"] = [_string(value, f"steps[{i}]") for i, value in enumerate(steps)]
    for name in ("environment", "severity"):
        if model.get(name) is not None:
            model[name] = _string(model[name], name)
        else:
            model.pop(name, None)

    diagnostics = model.get("diagnostics", [])
    if not isinstance(diagnostics, list):
        raise RenderError("diagnostics must be an array")
    clean_diagnostics = []
    for i, item in enumerate(diagnostics):
        if not isinstance(item, dict):
            raise RenderError(f"diagnostics[{i}] must be an object")
        text = _string(item.get("text"), f"diagnostics[{i}].text")
        language = item.get("language", "text")
        if not isinstance(language, str) or not re.fullmatch(
            r"[A-Za-z0-9_+.-]*", language
        ):
            raise RenderError(f"diagnostics[{i}].language is invalid")
        clean_diagnostics.append({"text": text, "language": language})
    model["diagnostics"] = clean_diagnostics

    links = model.get("links", [])
    if not isinstance(links, list):
        raise RenderError("links must be an array")
    clean_links = []
    for i, item in enumerate(links):
        if not isinstance(item, dict):
            raise RenderError(f"links[{i}] must be an object")
        label = _string(item.get("label"), f"links[{i}].label")
        url = _http_url(item.get("url"), f"links[{i}].url")
        clean_links.append({"label": label, "url": url})
    model["links"] = clean_links

    assistant = model.get("assistant")
    if assistant is not None:
        if not isinstance(assistant, dict):
            raise RenderError("assistant must be an object")
        unknown_identity = set(assistant) - {"agent", "model"}
        if unknown_identity:
            raise RenderError(
                "assistant has unsupported fields: "
                + ", ".join(sorted(unknown_identity))
            )
        clean_assistant = {}
        for name in ("agent", "model"):
            if assistant.get(name) is not None:
                value = _string(assistant[name], f"assistant.{name}")
                if len(value) > 200 or "\n" in value:
                    raise RenderError(
                        f"assistant.{name} must be a single line of at most 200 characters"
                    )
                clean_assistant[name] = value
        model["assistant"] = clean_assistant
    return model


def load_skill_metadata(path: Path) -> dict[str, str]:
    """Read the skill name and semver from its bounded YAML frontmatter."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    if not lines or lines[0] != "---":
        raise RenderError(f"{path}: missing YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise RenderError(f"{path}: unterminated YAML frontmatter") from error

    metadata = {}
    for line in lines[1:end]:
        match = re.fullmatch(r"(name|version):\s*([^#]+?)\s*", line)
        if match:
            metadata[match.group(1)] = match.group(2).strip("'\"")
    if not re.fullmatch(r"[a-z0-9-]{1,64}", metadata.get("name", "")):
        raise RenderError(f"{path}: invalid or missing skill name")
    if not SEMVER.fullmatch(metadata.get("version", "")):
        raise RenderError(f"{path}: invalid or missing skill version")
    return metadata


def build_provenance(model: dict[str, Any], skill: dict[str, str]) -> str:
    """Build truthful provenance from skill metadata and optional runtime identity."""
    assistant = model.get("assistant", {})
    agent = assistant.get("agent")
    model_name = assistant.get("model")
    identity = ""
    if agent and model_name:
        identity = f" ({agent} using {model_name})"
    elif agent:
        identity = f" ({agent})"
    elif model_name:
        identity = f" (AI assistant using {model_name})"
    return (
        f"Reported with AI assistance{identity} using {skill['name']} "
        f"v{skill['version']}. Review for accuracy."
    )


def parse_template(source: str) -> list[tuple[str, Any]]:
    """Parse the constrained template language into ordered render blocks."""
    blocks: list[tuple[str, Any]] = []
    paragraph: list[str] = []
    seen: set[str] = set()

    def flush() -> None:
        if paragraph:
            blocks.append(("paragraph", "\n".join(paragraph)))
            paragraph.clear()

    for number, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        match = PLACEHOLDER.fullmatch(stripped)
        if match:
            flush()
            name = match.group(1)
            if name not in SUPPORTED:
                raise RenderError(f"line {number}: unsupported placeholder {name!r}")
            if name in seen:
                raise RenderError(f"line {number}: duplicate placeholder {name!r}")
            seen.add(name)
            blocks.append(("placeholder", name))
            continue
        match = HEADING.fullmatch(line)
        if match:
            flush()
            blocks.append(("heading", (len(match.group(1)), match.group(2))))
            continue
        begins_block_markup = stripped.startswith(("```", "- ", "* ", "+ ", "> "))
        if begins_block_markup or re.match(r"^\d+[.)]\s", stripped):
            raise RenderError(f"line {number}: unsupported template Markdown")
        if "{{" in line or "}}" in line or re.search(r"<[^>]+>", line):
            raise RenderError(
                f"line {number}: inline placeholders or HTML are unsupported"
            )
        paragraph.append(line)
    flush()
    missing = REQUIRED - seen
    if missing:
        raise RenderError(
            "template missing required placeholders: " + ", ".join(sorted(missing))
        )
    return blocks


def escape_markdown(text: str) -> str:
    """Escape plain text so the confirmation preview cannot treat it as markup."""
    escaped_lines = []
    for line in text.split("\n"):
        escaped = re.sub(r"([\\`*_[\]<>#])", r"\\\1", line)
        escaped = re.sub(r"^( {0,3})([-+])(?=\s)", r"\1\\\2", escaped)
        escaped = re.sub(r"^( {0,3})(\d{1,9})([.)])(?=\s)", r"\1\2\\\3", escaped)
        if re.fullmatch(r" {0,3}(?:-\s*){3,}", escaped):
            hyphen = escaped.index("-")
            escaped = escaped[:hyphen] + r"\-" + escaped[hyphen + 1 :]
        escaped_lines.append(escaped)
    return "\n".join(escaped_lines)


def validate_representation(
    blocks: list[tuple[str, Any]], model: dict[str, Any]
) -> None:
    """Reject templates that would discard populated optional fields."""
    represented = {value for kind, value in blocks if kind == "placeholder"}
    omitted = {
        name
        for name in SUPPORTED - REQUIRED
        if model.get(name) and name not in represented
    }
    if omitted:
        raise RenderError(
            "template omits populated fields: " + ", ".join(sorted(omitted))
        )


def _markdown_value(name: str, model: dict[str, Any]) -> str:
    if name in SCALARS:
        return escape_markdown(model.get(name, ""))
    if name == "steps":
        return "\n".join(
            f"{i}. {escape_markdown(value)}" for i, value in enumerate(model[name], 1)
        )
    if name == "diagnostics":
        result = []
        for item in model[name]:
            fence = "```"
            while fence in item["text"]:
                fence += "`"
            result.append(f"{fence}{item['language']}\n{item['text']}\n{fence}")
        return "\n\n".join(result)
    if name == "links":
        rendered = []
        for item in model[name]:
            url = quote(item["url"], safe=":/?#[]@!$&'*+,;=%")
            rendered.append(f"- [{escape_markdown(item['label'])}]({url})")
        return "\n".join(rendered)
    raise AssertionError(name)


def render_markdown(
    blocks: list[tuple[str, Any]],
    model: dict[str, Any],
    provenance: str | None = None,
) -> str:
    """Render validated blocks and model as a confirmation-safe Markdown view."""
    validate_representation(blocks, model)
    output = []
    for kind, value in blocks:
        if kind == "heading":
            level, title = value
            rendered = f"{'#' * level} {escape_markdown(title)}"
        elif kind == "paragraph":
            rendered = escape_markdown(value)
        else:
            rendered = _markdown_value(value, model)
        if rendered:
            output.append(rendered)
    if provenance:
        output.extend(("---", f"_{escape_markdown(provenance)}_"))
    return "\n\n".join(output) + "\n"


def _text(value: str, marks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "text", "text": value}
    if marks:
        node["marks"] = marks
    return node


def _paragraphs(value: str) -> list[dict[str, Any]]:
    result = []
    for part in re.split(r"\n\s*\n", value):
        if not part:
            continue
        content = []
        for index, line in enumerate(part.splitlines() or [""]):
            if index:
                content.append({"type": "hardBreak"})
            if line:
                content.append(_text(line))
        result.append({"type": "paragraph", "content": content})
    return result


def _adf_value(name: str, model: dict[str, Any]) -> list[dict[str, Any]]:
    if name in SCALARS:
        return _paragraphs(model[name]) if model.get(name) else []
    if name == "steps":
        return [
            {
                "type": "orderedList",
                "attrs": {"order": 1},
                "content": [
                    {"type": "listItem", "content": _paragraphs(value)}
                    for value in model[name]
                ],
            }
        ]
    if name == "diagnostics":
        return [
            {
                "type": "codeBlock",
                "attrs": {"language": item["language"]},
                "content": [_text(item["text"])],
            }
            for item in model[name]
        ]
    if name == "links" and model[name]:
        return [
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    _text(
                                        item["label"],
                                        [
                                            {
                                                "type": "link",
                                                "attrs": {"href": item["url"]},
                                            }
                                        ],
                                    )
                                ],
                            }
                        ],
                    }
                    for item in model[name]
                ],
            }
        ]
    if name == "links":
        return []
    raise AssertionError(name)


def render_adf(
    blocks: list[tuple[str, Any]],
    model: dict[str, Any],
    provenance: str | None = None,
) -> dict[str, Any]:
    """Render validated blocks and model as an Atlassian Document Format doc."""
    validate_representation(blocks, model)
    content: list[dict[str, Any]] = []
    for kind, value in blocks:
        if kind == "heading":
            level, title = value
            content.append(
                {
                    "type": "heading",
                    "attrs": {"level": level},
                    "content": [_text(title)],
                }
            )
        elif kind == "paragraph":
            content.extend(_paragraphs(value))
        else:
            content.extend(_adf_value(value, model))
    if provenance:
        content.extend(
            (
                {"type": "rule"},
                {
                    "type": "paragraph",
                    "content": [
                        _text(provenance, [{"type": "em"}]),
                    ],
                },
            )
        )
    return {"version": 1, "type": "doc", "content": content}


def main(argv: list[str] | None = None) -> int:
    """Run the command-line renderer and return a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--format", required=True, choices=("markdown", "adf"))
    parser.add_argument("--skill-file", type=Path, default=SKILL_FILE)
    parser.add_argument("--no-provenance", action="store_true")
    args = parser.parse_args(argv)
    try:
        model = validate_model(json.loads(args.input.read_text(encoding="utf-8")))
        blocks = parse_template(args.template.read_text(encoding="utf-8"))
        provenance = None
        if not args.no_provenance:
            skill = load_skill_metadata(args.skill_file)
            provenance = build_provenance(model, skill)
        output: Any
        if args.format == "markdown":
            output = render_markdown(blocks, model, provenance)
        else:
            output = render_adf(blocks, model, provenance)
        if isinstance(output, str):
            sys.stdout.write(output)
        else:
            json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
    except (OSError, json.JSONDecodeError, RenderError) as error:
        print(f"render_issue: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
