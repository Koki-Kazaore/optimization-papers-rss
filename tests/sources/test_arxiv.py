"""Tests for optimization_rss.sources.arxiv: _parse_entry, fetch_arxiv_papers."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from optimization_rss.sources.arxiv import _parse_entry, fetch_arxiv_papers

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry_xml(
    title: str = "Convex Optimization Methods",
    abstract: str = "We study convex optimization.",
    authors: list[str] | None = None,
    published: str = "2024-01-14T12:00:00Z",
    arxiv_url: str = "http://arxiv.org/abs/2401.12345",
    pdf_href: str | None = None,
    doi: str | None = None,
) -> str:
    """Build a minimal Atom <entry> XML string."""
    if authors is None:
        authors = ["Alice Smith"]
    author_xml = "".join(f"<author><name>{a}</name></author>" for a in authors)
    pdf_xml = (
        f'<link href="{pdf_href}" type="application/pdf" rel="related"/>'
        if pdf_href
        else ""
    )
    doi_xml = f"<arxiv:doi>{doi}</arxiv:doi>" if doi else ""
    return (
        f'<entry xmlns="{ATOM_NS}" xmlns:arxiv="{ARXIV_NS}">'
        f"<title>{title}</title>"
        f"<summary>{abstract}</summary>"
        f"{author_xml}"
        f"<published>{published}</published>"
        f"<id>{arxiv_url}</id>"
        f"{pdf_xml}"
        f"{doi_xml}"
        f"</entry>"
    )


def _make_atom_feed(entry_xml: str = "") -> str:
    """Wrap one or more <entry> elements in a complete <feed>."""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<feed xmlns="{ATOM_NS}" xmlns:arxiv="{ARXIV_NS}">'
        f"<title>ArXiv Query</title>"
        f"{entry_xml}"
        f"</feed>"
    )


def _recent_published() -> str:
    """ISO timestamp for 1 day ago (always within LOOKBACK_DAYS)."""
    ts = datetime.now(timezone.utc) - timedelta(days=1)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _old_published() -> str:
    """ISO timestamp older than LOOKBACK_DAYS."""
    ts = datetime.now(timezone.utc) - timedelta(days=30)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty_feed() -> bytes:
    return _make_atom_feed("").encode("utf-8")


# ---------------------------------------------------------------------------
# Tests: _parse_entry
# ---------------------------------------------------------------------------

class TestParseEntry:
    def test_full_entry_returns_paper(self):
        xml_str = _make_entry_xml(
            title="  Convex\n Optimization Methods  ",
            abstract="We study convex optimization.",
            authors=["Alice Smith", "Bob Jones"],
            published="2024-01-14T12:00:00Z",
            arxiv_url="http://arxiv.org/abs/2401.12345v2",
            pdf_href="https://arxiv.org/pdf/2401.12345",
            doi="10.1234/test",
        )
        entry = ET.fromstring(xml_str)
        paper = _parse_entry(entry)

        assert paper is not None
        assert "Convex" in paper.title
        assert "\n" not in paper.title
        assert paper.authors == ["Alice Smith", "Bob Jones"]
        assert paper.abstract == "We study convex optimization."
        assert paper.arxiv_id == "2401.12345"  # version stripped
        assert paper.paper_url == "http://arxiv.org/abs/2401.12345v2"
        assert paper.pdf_url == "https://arxiv.org/pdf/2401.12345"
        assert paper.doi == "10.1234/test"
        assert paper.source == "arxiv"
        assert paper.published_at == datetime(2024, 1, 14, 12, 0, 0, tzinfo=timezone.utc)

    def test_versioned_arxiv_id_stripped(self):
        xml_str = _make_entry_xml(
            arxiv_url="http://arxiv.org/abs/2401.12345v3",
        )
        paper = _parse_entry(ET.fromstring(xml_str))
        assert paper.arxiv_id == "2401.12345"

    def test_missing_pdf_gives_none(self):
        xml_str = _make_entry_xml(pdf_href=None)
        paper = _parse_entry(ET.fromstring(xml_str))
        assert paper.pdf_url is None

    def test_missing_doi_gives_none(self):
        xml_str = _make_entry_xml(doi=None)
        paper = _parse_entry(ET.fromstring(xml_str))
        assert paper.doi is None

    def test_title_with_embedded_newlines_is_stripped(self):
        xml_str = _make_entry_xml(
            title="  Optimization\n  Theory\n  for Machine Learning  "
        )
        paper = _parse_entry(ET.fromstring(xml_str))
        assert "\n" not in paper.title
        assert "Optimization" in paper.title
        assert "Theory" in paper.title

    def test_source_is_arxiv(self):
        paper = _parse_entry(ET.fromstring(_make_entry_xml()))
        assert paper.source == "arxiv"

    def test_source_ids_contains_arxiv_key(self):
        xml_str = _make_entry_xml(arxiv_url="http://arxiv.org/abs/2401.12345")
        paper = _parse_entry(ET.fromstring(xml_str))
        assert paper.source_ids.get("arxiv") == "2401.12345"


# ---------------------------------------------------------------------------
# Tests: fetch_arxiv_papers
# ---------------------------------------------------------------------------

class TestFetchArxivPapers:
    """Each test patches requests.get in the arxiv module and time.sleep."""

    def _make_responses(
        self,
        fake_response,
        *,
        mathoc_xml: bytes | None = None,
        csms_xml: bytes | None = None,
        cslg_xml: bytes | None = None,
    ):
        """Build a side_effect list of 3 mock responses (one per ARXIV_CATEGORIES)."""
        def _resp(xml_bytes):
            r = fake_response(200)
            r.content = xml_bytes if xml_bytes is not None else _empty_feed()
            return r

        return [
            _resp(mathoc_xml),
            _resp(csms_xml),
            _resp(cslg_xml),
        ]

    def test_math_oc_paper_returned_regardless_of_keywords(self, fake_response, monkeypatch):
        # Paper has no optimization keywords — should still be returned from math.OC
        entry = _make_entry_xml(
            title="A General Math Paper",
            abstract="Pure mathematics with no optimization content.",
            published=_recent_published(),
            arxiv_url="http://arxiv.org/abs/2401.11111",
        )
        feed_xml = _make_atom_feed(entry).encode("utf-8")
        responses = self._make_responses(fake_response, mathoc_xml=feed_xml)

        with (
            patch("optimization_rss.sources.arxiv.requests.get", side_effect=responses),
            patch("optimization_rss.sources.arxiv.time.sleep"),
        ):
            papers = fetch_arxiv_papers()

        assert any(p.arxiv_id == "2401.11111" for p in papers)

    def test_cs_lg_paper_matching_keywords_is_returned(self, fake_response, monkeypatch):
        entry = _make_entry_xml(
            title="Gradient Descent for Deep Learning",
            abstract="We use gradient descent to train neural networks.",
            published=_recent_published(),
            arxiv_url="http://arxiv.org/abs/2401.22222",
        )
        feed_xml = _make_atom_feed(entry).encode("utf-8")
        responses = self._make_responses(fake_response, cslg_xml=feed_xml)

        with (
            patch("optimization_rss.sources.arxiv.requests.get", side_effect=responses),
            patch("optimization_rss.sources.arxiv.time.sleep"),
        ):
            papers = fetch_arxiv_papers()

        assert any(p.arxiv_id == "2401.22222" for p in papers)

    def test_cs_lg_paper_not_matching_keywords_is_excluded(self, fake_response):
        entry = _make_entry_xml(
            title="Transformer Architectures for NLP",
            abstract="We propose a new attention mechanism for language models.",
            published=_recent_published(),
            arxiv_url="http://arxiv.org/abs/2401.33333",
        )
        feed_xml = _make_atom_feed(entry).encode("utf-8")
        responses = self._make_responses(fake_response, cslg_xml=feed_xml)

        with (
            patch("optimization_rss.sources.arxiv.requests.get", side_effect=responses),
            patch("optimization_rss.sources.arxiv.time.sleep"),
        ):
            papers = fetch_arxiv_papers()

        assert not any(p.arxiv_id == "2401.33333" for p in papers)

    def test_paper_older_than_lookback_is_excluded(self, fake_response):
        entry = _make_entry_xml(
            title="Old Convex Optimization Paper",
            abstract="This paper is very old.",
            published=_old_published(),
            arxiv_url="http://arxiv.org/abs/2301.99999",
        )
        feed_xml = _make_atom_feed(entry).encode("utf-8")
        responses = self._make_responses(fake_response, mathoc_xml=feed_xml)

        with (
            patch("optimization_rss.sources.arxiv.requests.get", side_effect=responses),
            patch("optimization_rss.sources.arxiv.time.sleep"),
        ):
            papers = fetch_arxiv_papers()

        assert not any(p.arxiv_id == "2301.99999" for p in papers)

    def test_request_exception_returns_empty_list(self, fake_response):
        import requests as requests_lib

        with (
            patch(
                "optimization_rss.sources.arxiv.requests.get",
                side_effect=requests_lib.RequestException("timeout"),
            ),
            patch("optimization_rss.sources.arxiv.time.sleep"),
        ):
            papers = fetch_arxiv_papers()

        assert papers == []

    def test_malformed_xml_returns_empty_list(self, fake_response):
        bad_response = fake_response(200)
        bad_response.content = b"<not valid xml <<<"

        with (
            patch(
                "optimization_rss.sources.arxiv.requests.get",
                return_value=bad_response,
            ),
            patch("optimization_rss.sources.arxiv.time.sleep"),
        ):
            papers = fetch_arxiv_papers()

        assert papers == []

    def test_sleep_is_called_between_categories(self, fake_response):
        responses = self._make_responses(fake_response)

        with (
            patch("optimization_rss.sources.arxiv.requests.get", side_effect=responses),
            patch("optimization_rss.sources.arxiv.time.sleep") as mock_sleep,
        ):
            fetch_arxiv_papers()

        # sleep is called once per category after the first (i > 0) => 2 times
        assert mock_sleep.call_count == 2
