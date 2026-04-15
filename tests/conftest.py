"""Shared fixtures for all tests."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from optimization_rss.models import Paper


@pytest.fixture
def paper_factory():
    """Return a callable that produces Paper instances with sensible defaults."""

    def make_paper(**kwargs):
        defaults = {
            "title": "A study of convex optimization methods",
            "authors": ["Alice Smith"],
            "abstract": "We study convex optimization in this paper.",
            "published_at": datetime(2024, 1, 14, 12, 0, 0, tzinfo=timezone.utc),
            "first_seen_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "arxiv_id": "2401.12345",
            "doi": None,
            "paper_url": "https://arxiv.org/abs/2401.12345",
            "pdf_url": None,
            "source": "arxiv",
            "source_ids": {},
        }
        defaults.update(kwargs)
        return Paper(**defaults)

    return make_paper


@pytest.fixture
def fixed_dt():
    """A fixed, timezone-aware UTC datetime."""
    return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def parse_rss():
    """Return a helper that parses an RSS file with both ElementTree and feedparser."""
    import xml.etree.ElementTree as ET

    import feedparser

    def _parse(path):
        root = ET.parse(str(path)).getroot()
        feed = feedparser.parse(str(path))
        return root, feed

    return _parse


@pytest.fixture
def fake_response():
    """Return a factory for mock requests.Response objects."""
    from requests.exceptions import HTTPError

    def _make(status_code, text="", json_data=None):
        mock = MagicMock()
        mock.status_code = status_code
        mock.text = text
        # arxiv.py uses response.content (bytes)
        mock.content = text.encode("utf-8") if isinstance(text, str) else text
        mock.json.return_value = json_data if json_data is not None else {}
        if status_code >= 400:
            mock.raise_for_status.side_effect = HTTPError(f"HTTP {status_code}")
        else:
            mock.raise_for_status.return_value = None
        return mock

    return _make


@pytest.fixture(autouse=True, scope="session")
def no_network():
    """Block any real HTTP calls for the entire test session."""
    with patch(
        "requests.sessions.Session.request",
        side_effect=RuntimeError("real network call blocked"),
    ):
        yield
