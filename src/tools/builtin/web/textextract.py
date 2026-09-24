from __future__ import annotations

import os
import re
import urllib.parse
from dataclasses import dataclass, field
from html.parser import HTMLParser

# Elements whose content is never readable page text. Void elements
# (img, br, input, meta, link, embed ...) must NOT be listed here because
# they have no end tag and would swallow the rest of the page.
_SKIP_TAGS = {
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "iframe",
    "object",
    "nav",
    "footer",
    "aside",
    "select",
    "dialog",
}

_HEADINGS = {
    "h1": 1,
    "h2": 2,
    "h3": 3,
    "h4": 4,
    "h5": 5,
    "h6": 6,
}

# Blank line before and after.
_PARAGRAPH_TAGS = {
    "p",
    "section",
    "article",
    "main",
    "blockquote",
    "figure",
    "figcaption",
    "ul",
    "ol",
    "dl",
    "table",
    "details",
    "summary",
}

# Single line break.
_LINE_TAGS = {
    "div",
    "li",
    "tr",
    "br",
    "dt",
    "dd",
    "hr",
    "thead",
    "tbody",
    "header",
}

MAX_LINKS = 200


def _safe_text(value: object) -> str:
    return str(value or "").encode("utf-8", errors="replace").decode("utf-8", errors="replace")


@dataclass
class ExtractedPage:
    title: str = ""
    text: str = ""
    links: list[dict[str, str]] = field(default_factory=list)
    method: str = "builtin"


class _Extractor(HTMLParser):
    def __init__(
        self,
        base_url: str,
        main_only: bool = False,
    ) -> None:
        super().__init__(convert_charrefs=True)

        self.base_url = _safe_text(base_url)
        self.main_only = main_only

        self.title = ""
        self.links: list[dict[str, str]] = []
        self.saw_main = False

        self._title_parts: list[str] = []
        self._in_title = False

        self._skip_stack: list[str] = []
        self._main_depth = 0

        self._lines: list[str] = []
        self._current: list[str] = []

        self._pre_depth = 0
        self._pre_buffer: list[str] = []

        self._href: str | None = None
        self._anchor_parts: list[str] = []
        self._seen_links: set[str] = set()

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _emitting(self) -> bool:
        if self._skip_stack:
            return False
        if self.main_only and self._main_depth <= 0:
            return False
        return True

    def _flush(self) -> None:
        line = re.sub(r"[ \t]+", " ", "".join(self._current)).strip()
        self._current = []

        if not line:
            return

        # Drop empty list bullets, table separators and empty headings.
        if line in ("-", "|") or re.fullmatch(r"#{1,6}", line):
            return

        self._lines.append(_safe_text(line))

    def _blank(self) -> None:
        self._flush()
        if self._lines and self._lines[-1] != "":
            self._lines.append("")

    def _emit_pre(self) -> None:
        code = "".join(self._pre_buffer)
        self._pre_buffer = []

        code = code.strip("\n")
        if not code.strip():
            return

        self._lines.append("```")
        self._lines.extend(
            _safe_text(line.rstrip()) for line in code.split("\n")
        )
        self._lines.append("```")
        self._lines.append("")

    def _finish_link(self) -> None:
        href = self._href
        parts = self._anchor_parts

        self._href = None
        self._anchor_parts = []

        if not href or len(self.links) >= MAX_LINKS:
            return

        text = re.sub(r"\s+", " ", "".join(parts)).strip()
        if not text:
            return

        if href.lower().startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            return

        try:
            url = urllib.parse.urljoin(self.base_url, href)
        except ValueError:
            return

        if not url.startswith(("http://", "https://")):
            return

        if url in self._seen_links:
            return

        self._seen_links.add(url)
        self.links.append(
            {
                "text": _safe_text(text[:120]),
                "url": _safe_text(url),
            }
        )

    # ------------------------------------------------------------------
    # HTMLParser callbacks
    # ------------------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag in _SKIP_TAGS:
            self._skip_stack.append(tag)
            return

        if tag == "title" and not self._skip_stack and not self.title:
            self._in_title = True
            self._title_parts = []
            return

        if tag in ("main", "article"):
            self._main_depth += 1
            self.saw_main = True

        if not self._emitting():
            return

        if self._pre_depth and tag != "pre":
            if tag == "br":
                self._pre_buffer.append("\n")
            return

        if tag in _HEADINGS:
            self._blank()
            self._current.append("#" * _HEADINGS[tag] + " ")

        elif tag == "pre":
            if self._pre_depth == 0:
                self._blank()
            self._pre_depth += 1

        elif tag == "li":
            self._flush()
            self._current.append("- ")

        elif tag in ("td", "th"):
            if "".join(self._current).strip():
                self._current.append(" | ")

        elif tag == "a":
            href = dict(attrs).get("href")
            self._href = href.strip() if href else None
            self._anchor_parts = []

        elif tag in _PARAGRAPH_TAGS:
            self._blank()

        elif tag in _LINE_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in _SKIP_TAGS:
            if tag in self._skip_stack:
                while self._skip_stack:
                    if self._skip_stack.pop() == tag:
                        break
            return

        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = _safe_text(
                re.sub(r"\s+", " ", "".join(self._title_parts)).strip()
            )
            return

        if tag in ("main", "article"):
            if self._emitting():
                self._blank()
            if self._main_depth > 0:
                self._main_depth -= 1
            return

        if not self._emitting():
            return

        if self._pre_depth:
            if tag == "pre":
                self._pre_depth -= 1
                if self._pre_depth == 0:
                    self._emit_pre()
            return

        if tag in _HEADINGS:
            self._blank()
        elif tag == "a":
            self._finish_link()
        elif tag in _PARAGRAPH_TAGS:
            self._blank()
        elif tag in _LINE_TAGS:
            self._flush()

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)
            return

        if not self._emitting():
            return

        if self._pre_depth:
            self._pre_buffer.append(data)
            return

        text = re.sub(r"\s+", " ", data)

        if not text.strip() and not self._current:
            return

        text = _safe_text(text)
        self._current.append(text)

        if self._href is not None:
            self._anchor_parts.append(text)

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def result(self) -> str:
        self._flush()

        if self._pre_buffer:
            self._emit_pre()

        text = "\n".join(self._lines)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return _safe_text(text.strip())


def _run(
    html: str,
    base_url: str,
    main_only: bool,
) -> _Extractor:
    parser = _Extractor(base_url, main_only=main_only)

    try:
        parser.feed(html)
        parser.close()
    except Exception:
        # Broken markup: keep whatever was extracted so far.
        pass

    return parser


def _try_trafilatura(
    html: str,
    url: str,
) -> str:
    if os.environ.get("EVANA_WEB_EXTRACTOR", "auto").strip().lower() == "builtin":
        return ""

    try:
        import trafilatura
    except ImportError:
        return ""

    try:
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
    except Exception:
        return ""

    return _safe_text((text or "").strip())


def extract_page(
    html: str,
    url: str,
) -> ExtractedPage:
    """
    Convert HTML to readable text.

    Order of preference:
        1. trafilatura (if installed) for the best main-content extraction,
        2. the content inside <main>/<article> when it is substantial,
        3. all visible text minus scripts, navigation, footers and sidebars.

    Title and links always come from the built-in parser.
    """

    full = _run(_safe_text(html), url, main_only=False)
    full_text = full.result()

    page = ExtractedPage(
        title=full.title,
        text=full_text,
        links=list(full.links),
        method="builtin",
    )

    better = _try_trafilatura(_safe_text(html), _safe_text(url))

    if len(better) >= 200:
        page.text = better
        page.method = "trafilatura"
        return page

    if full.saw_main:
        main_text = _run(_safe_text(html), url, main_only=True).result()
        if len(main_text) >= 400 and len(main_text) * 10 >= len(full_text) * 3:
            page.text = main_text
            page.method = "builtin-main"

    page.title = _safe_text(page.title)
    page.text = _safe_text(page.text)
    return page
