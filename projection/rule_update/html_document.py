"""Minimal HTML text and table extraction for official publications."""

from __future__ import annotations

import re
from html.parser import HTMLParser


class OfficialHtmlDocument(HTMLParser):
    _BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "tr", "div", "section"}

    def __init__(self, content: bytes) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._rows: list[tuple[str, ...]] = []
        self._row_cells: list[str] | None = None
        self._cell_parts: list[str] | None = None
        self.feed(content.decode("utf-8", errors="replace"))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row_cells = []
        elif tag in {"td", "th"} and self._row_cells is not None:
            self._cell_parts = []
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"}:
            if self._row_cells is not None and self._cell_parts is not None:
                self._row_cells.append(self._normalize(" ".join(self._cell_parts)))
                self._cell_parts = None
            self._parts.append(" | ")
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")
        if tag == "tr" and self._row_cells is not None:
            self._rows.append(tuple(self._row_cells))
            self._row_cells = None

    def handle_data(self, data: str) -> None:
        self._parts.append(data)
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    @property
    def text(self) -> str:
        lines = []
        for line in "".join(self._parts).splitlines():
            normalized = self._normalize(line).strip(" |")
            if normalized:
                lines.append(normalized)
        return "\n".join(lines)

    @property
    def table_rows(self) -> tuple[tuple[str, ...], ...]:
        return tuple(self._rows)

    def section(self, start: str, end: str | None = None) -> str:
        text = self.text
        start_index = text.casefold().find(start.casefold())
        if start_index < 0:
            return ""
        selected = text[start_index:]
        if end:
            end_index = selected.casefold().find(end.casefold(), len(start))
            if end_index >= 0:
                selected = selected[:end_index]
        return selected

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()
