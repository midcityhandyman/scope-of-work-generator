"""Render a scope to Markdown and HTML from template files.

The template language is deliberately tiny so the project has no dependencies:

    {{ name.path }}                        value lookup (HTML escaped for HTML output)
    {% for item in name.path %} ... {% endfor %}
    {% if name.path %} ... {% else %} ... {% endif %}   (also: {% if not name.path %})

A line that holds only a block tag produces no output line.
"""

from __future__ import annotations

import html
import os
import re
from pathlib import Path
from typing import Any

from .model import Scope

TEMPLATE_DIR = Path(__file__).parent / "templates"
DEFAULT_COMPANY = "Example Remodeling Co"

_TOKEN = re.compile(r"(\{\{.*?\}\}|\{%.*?%\})", re.S)
_BLOCK_LINE = re.compile(r"^[ \t]*(\{%[^\n]*?%\})[ \t]*\r?\n", re.M)


class TemplateError(ValueError):
    pass


def parse(source: str) -> list[Any]:
    """Turn template text into a tree of text, var, for and if nodes."""
    source = _BLOCK_LINE.sub(r"\1", source)
    root: list[Any] = []
    stack: list[tuple[dict[str, Any] | None, list[Any]]] = [(None, root)]
    for token in _TOKEN.split(source):
        node, current = stack[-1]
        if token.startswith("{{"):
            current.append({"kind": "var", "path": token[2:-2].strip()})
        elif token.startswith("{%"):
            words = token[2:-2].split()
            if len(words) == 4 and words[0] == "for" and words[2] == "in":
                new = {"kind": "for", "name": words[1], "path": words[3], "body": []}
                current.append(new)
                stack.append((new, new["body"]))
            elif words[:1] == ["if"] and (len(words) == 2 or (len(words) == 3 and words[1] == "not")):
                new = {"kind": "if", "negate": len(words) == 3, "path": words[-1], "body": [], "else": []}
                current.append(new)
                stack.append((new, new["body"]))
            elif words == ["else"] and node is not None and node["kind"] == "if" and current is node["body"]:
                stack[-1] = (node, node["else"])
            elif words in (["endfor"], ["endif"]) and node is not None and node["kind"] == words[0][3:]:
                stack.pop()
            else:
                raise TemplateError(f"unexpected tag: {token}")
        elif token:
            current.append({"kind": "text", "text": token})
    if len(stack) != 1:
        raise TemplateError(f"unclosed {stack[-1][0]['kind']} block")
    return root


def _lookup(path: str, scopes: list[dict[str, Any]]) -> Any:
    head, *rest = path.split(".")
    for scope in reversed(scopes):
        if head in scope:
            value = scope[head]
            break
    else:
        raise TemplateError(f"unknown name: {head}")
    for part in rest:
        if not isinstance(value, dict) or part not in value:
            raise TemplateError(f"unknown name: {path}")
        value = value[part]
    return value


def _render(nodes: list[Any], scopes: list[dict[str, Any]], escape: bool, out: list[str]) -> None:
    for node in nodes:
        kind = node["kind"]
        if kind == "text":
            out.append(node["text"])
        elif kind == "var":
            text = str(_lookup(node["path"], scopes))
            out.append(html.escape(text) if escape else text)
        elif kind == "for":
            for item in _lookup(node["path"], scopes):
                _render(node["body"], scopes + [{node["name"]: item}], escape, out)
        else:
            truthy = bool(_lookup(node["path"], scopes))
            branch = node["body"] if truthy != node["negate"] else node["else"]
            _render(branch, scopes, escape, out)


def render_template(source: str, context: dict[str, Any], escape: bool = False) -> str:
    out: list[str] = []
    _render(parse(source), [context], escape, out)
    return "".join(out)


def company_name() -> str:
    return os.environ.get("SOWGEN_COMPANY_NAME", "").strip() or DEFAULT_COMPANY


def _render_file(name: str, scope: Scope, company: str | None, escape: bool) -> str:
    source = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    return render_template(source, scope.to_context(company or company_name()), escape=escape)


def render_markdown(scope: Scope, company: str | None = None) -> str:
    return _render_file("scope.md.tmpl", scope, company, escape=False)


def render_html(scope: Scope, company: str | None = None) -> str:
    return _render_file("scope.html.tmpl", scope, company, escape=True)
