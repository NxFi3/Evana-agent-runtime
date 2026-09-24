from __future__ import annotations

import importlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .httpclient import USER_AGENT

TIME_RANGES = ("day", "week", "month", "year")


def _safe_text(value: object) -> str:
    """Return text with any invalid UTF-8 surrogate characters replaced."""
    return str(value or "").encode("utf-8", errors="replace").decode("utf-8", errors="replace")


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    published: str = ""


class SearchBackendError(Exception):
    def __init__(
        self,
        backend: str,
        error_type: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.backend = backend
        self.error_type = error_type
        self.message = _safe_text(message)


class SearchBackend(ABC):
    """
    A web search provider.

    To add a new one (Brave, Tavily, Serper ...): subclass this, implement
    is_available() and search(), and append it in select_backends().
    """

    name: str = ""

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def unavailable_reason(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        num_results: int,
        time_range: str | None,
        region: str | None,
        timeout: float,
    ) -> list[SearchHit]:
        raise NotImplementedError


# ----------------------------------------------------------------------
# SearXNG (self-hosted metasearch, best fit for a local-first agent)
# ----------------------------------------------------------------------


class SearxngBackend(SearchBackend):
    """
    Talks to your own SearXNG instance.

    Setup:
        export EVANA_SEARXNG_URL=http://127.0.0.1:8080
    and enable the JSON output in SearXNG's settings.yml:
        search:
          formats: [html, json]
    """

    name = "searxng"

    def __init__(self) -> None:
        self.base_url = os.environ.get("EVANA_SEARXNG_URL", "").strip().rstrip("/")

    def is_available(self) -> bool:
        return self.base_url.startswith(("http://", "https://"))

    def unavailable_reason(self) -> str:
        return "EVANA_SEARXNG_URL is not set."

    def search(
        self,
        query: str,
        *,
        num_results: int,
        time_range: str | None,
        region: str | None,
        timeout: float,
    ) -> list[SearchHit]:
        params = {
            "q": _safe_text(query),
            "format": "json",
            "pageno": "1",
        }

        if time_range in TIME_RANGES:
            params["time_range"] = time_range

        if region and "-" in region:
            language = region.split("-")[-1].strip().lower()
            if language and language != "wt":
                params["language"] = language

        url = f"{self.base_url}/search?{urllib.parse.urlencode(params)}"

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(2_000_000)
        except urllib.error.HTTPError as exc:
            hint = ""
            if exc.code == 403:
                hint = (
                    " JSON output is probably disabled: add 'json' to "
                    "search.formats in SearXNG settings.yml."
                )
            raise SearchBackendError(
                self.name,
                "http_error",
                f"SearXNG returned HTTP {exc.code}.{hint}",
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SearchBackendError(
                self.name,
                "network_error",
                f"Could not reach SearXNG at {self.base_url}: {exc}",
            ) from exc

        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise SearchBackendError(
                self.name,
                "bad_response",
                "SearXNG did not return valid JSON.",
            ) from exc

        rows = data.get("results") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return []

        hits: list[SearchHit] = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            engines = row.get("engines")
            source = _safe_text(row.get("engine") or "")

            if isinstance(engines, list) and engines:
                source = ", ".join(_safe_text(item) for item in engines[:3])

            hits.append(
                SearchHit(
                    title=_safe_text(row.get("title") or ""),
                    url=_safe_text(row.get("url") or ""),
                    snippet=_safe_text(row.get("content") or ""),
                    source=source,
                    published=_safe_text(row.get("publishedDate") or ""),
                )
            )

        return hits[:num_results]


# ----------------------------------------------------------------------
# DDGS (pip install -U ddgs) - no API key, no server
# ----------------------------------------------------------------------


class DdgsBackend(SearchBackend):
    name = "ddgs"

    _TIMELIMIT = {
        "day": "d",
        "week": "w",
        "month": "m",
        "year": "y",
    }

    @staticmethod
    def _load():
        # "ddgs" is the current package; "duckduckgo_search" is its old name.
        for module_name in ("ddgs", "duckduckgo_search"):
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue

            client = getattr(module, "DDGS", None)
            if client is not None:
                return client

        return None

    def is_available(self) -> bool:
        return self._load() is not None

    def unavailable_reason(self) -> str:
        return "The 'ddgs' package is not installed (pip install -U ddgs)."

    def search(
        self,
        query: str,
        *,
        num_results: int,
        time_range: str | None,
        region: str | None,
        timeout: float,
    ) -> list[SearchHit]:
        client_class = self._load()

        if client_class is None:
            raise SearchBackendError(
                self.name,
                "not_installed",
                self.unavailable_reason(),
            )

        options: dict[str, object] = {
            "safesearch": "moderate",
            "max_results": num_results,
        }

        if region:
            options["region"] = _safe_text(region)

        if time_range in self._TIMELIMIT:
            options["timelimit"] = self._TIMELIMIT[time_range]

        try:
            client = client_class(timeout=int(timeout))
            rows = client.text(_safe_text(query), **options)
        except Exception as exc:
            hint = ""
            if "limit" in str(exc).lower() or "202" in str(exc):
                hint = " (rate limited: wait a bit or use a self-hosted SearXNG)"
            raise SearchBackendError(
                self.name,
                "search_failed",
                f"{type(exc).__name__}: {exc}{hint}",
            ) from exc

        hits: list[SearchHit] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue

            hits.append(
                SearchHit(
                    title=_safe_text(row.get("title") or ""),
                    url=_safe_text(row.get("href") or row.get("url") or ""),
                    snippet=_safe_text(row.get("body") or ""),
                    source="duckduckgo",
                )
            )

        return hits


# ----------------------------------------------------------------------
# Selection
# ----------------------------------------------------------------------


def select_backends() -> list[SearchBackend]:
    """
    Backends in the order they are tried.

    EVANA_SEARCH_BACKEND = auto (default) | searxng | ddgs
    """

    available = {
        "searxng": SearxngBackend(),
        "ddgs": DdgsBackend(),
    }

    choice = os.environ.get("EVANA_SEARCH_BACKEND", "auto").strip().lower()

    if choice in available:
        return [available[choice]]

    return [
        available["searxng"],
        available["ddgs"],
    ]
