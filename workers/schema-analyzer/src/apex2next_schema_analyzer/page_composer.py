"""R4a page composer: a page assembled region by region (static content, lists, reports, Interactive Reports, Cards).

The R3 generator recognized whole-page patterns (Interactive Report page, faceted search, form dialog). The Oracle
sample applications showed that most pages combine a few simple regions instead. The composer emits such a page
when every region and button on it is one the runtime can render; what it cannot render is never guessed:

* a region without a renderer, or with a display condition other than an item being null / not null, keeps the
  page MANUAL (the page would show something APEX does not, or hide something it shows);
* a button whose action or condition needs server logic is left out and reported, and the page is PARTIAL.

Static HTML is reduced to an allowlist of tags with no attributes except safe links, and rendered from data, so
no markup of the export reaches the browser as HTML.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any

# region types the composer renders; None is a static content (or empty container) region
COMPOSE_TYPES = {None, "NATIVE_BREADCRUMB", "NATIVE_LIST", "NATIVE_DISPLAY_SELECTOR", "NATIVE_IR", "NATIVE_CARDS", "NATIVE_IG"}
ITEM_CONDITIONS = {"ITEM_IS_NULL", "ITEM_IS_NOT_NULL"}
ALLOWED_TAGS = {"p", "br", "ul", "ol", "li", "strong", "b", "em", "i", "a", "h1", "h2", "h3", "h4", "h5", "h6",
                "code", "pre", "span", "div", "small", "blockquote", "hr", "table", "thead", "tbody", "tr", "th", "td",
                "dl", "dt", "dd", "u", "sup", "sub"}
VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "col"}
DROP_CONTENT = {"script", "style", "iframe", "object", "embed", "template", "noscript", "svg", "canvas"}
SUBSTITUTION = re.compile(r"&([A-Za-z_][A-Za-z0-9_$#]*)(?:![A-Z_]+)?\.|#([A-Z][A-Z0-9_]*)#")


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root: list[Any] = []
        self.stack: list[tuple[str, list[Any]]] = []
        self.dropping = 0
        self.dropped: set[str] = set()
        self.links: list[str] = []
        self.text: list[str] = []

    def _children(self) -> list[Any]:
        return self.stack[-1][1] if self.stack else self.root

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.dropping or tag in DROP_CONTENT:
            if tag not in VOID_TAGS:
                self.dropping += 1
            self.dropped.add(tag)
            return
        if tag not in ALLOWED_TAGS:
            self.dropped.add(tag)  # unknown wrapper: keep its text, drop the tag
            return
        node: dict[str, Any] = {"t": tag}
        if tag == "a":
            href = dict(attrs).get("href") or ""
            node["href"] = href
            self.links.append(href)
        self._children().append(node)
        if tag not in VOID_TAGS:
            node["c"] = []
            self.stack.append((tag, node["c"]))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS and not self.dropping and tag in ALLOWED_TAGS and self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        if self.dropping:
            if tag in DROP_CONTENT or tag not in VOID_TAGS:
                self.dropping -= 1
            return
        for n in range(len(self.stack) - 1, -1, -1):
            if self.stack[n][0] == tag:
                del self.stack[n:]
                return

    def handle_data(self, data: str) -> None:
        if not self.dropping and data:
            self.text.append(data)
            children = self._children()
            if children and isinstance(children[-1], str):
                children[-1] += data
            else:
                children.append(data)


def _squeeze(nodes: list[Any]) -> list[Any]:
    """Collapse white space as a browser does and drop empty text."""
    out: list[Any] = []
    for n in nodes:
        if isinstance(n, str):
            text = re.sub(r"\s+", " ", n)
            if text.strip() or (out and not isinstance(out[-1], str)):
                if text.strip():
                    out.append(text)
        else:
            if "c" in n:
                n["c"] = _squeeze(n["c"])
            out.append(n)
    return out


def sanitize_html(html: str) -> dict[str, Any]:
    """HTML of a static region as allowlisted nodes: ``{"nodes", "links", "dropped", "substitutions"}``."""
    parser = _Sanitizer()
    parser.feed(html)
    parser.close()
    # substitutions in shown text, and in links that are not APEX f?p links (those are resolved to routes)
    shown = "".join(parser.text) + " ".join(h for h in parser.links if not h.startswith("f?p="))
    subs = sorted({m.group(1) or m.group(2) for m in SUBSTITUTION.finditer(shown)})
    return {"nodes": _squeeze(parser.root), "links": parser.links, "dropped": sorted(parser.dropped), "substitutions": subs}


def map_text(nodes: list[Any], fn) -> list[Any]:
    out = []
    for n in nodes:
        if isinstance(n, str):
            out.append(fn(n))
        else:
            m = dict(n)
            if "c" in m:
                m["c"] = map_text(m["c"], fn)
            out.append(m)
    return out


def node_links(nodes: list[Any], fn) -> list[Any]:
    """Replace every link href with fn(href); None removes the link and keeps its text."""
    out: list[Any] = []
    for n in nodes:
        if isinstance(n, str):
            out.append(n)
            continue
        m = dict(n)
        if "c" in m:
            m["c"] = node_links(m["c"], fn)
        if m["t"] == "a":
            href = fn(m.get("href") or "")
            if href is None:
                out.extend(m.get("c", []))
                continue
            m["href"] = href
        out.append(m)
    return out


def safe_external(href: str) -> bool:
    return bool(re.fullmatch(r"https://[^\s\"'<>]+", href))


def region_sequence(c: dict[str, Any]) -> tuple[int, str]:
    p = c["props"]
    return int(p.get("plug_display_sequence") or p.get("display_sequence") or 0), c["name"]


def tsx_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
