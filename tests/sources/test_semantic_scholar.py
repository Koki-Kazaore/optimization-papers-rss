"""Tests for optimization_rss.sources.semantic_scholar."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

import optimization_rss.sources.semantic_scholar as ss_module
from optimization_rss.sources.semantic_scholar import (
    _build_headers,
    _parse_paper,
    fetch_semantic_scholar_papers,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recent_date() -> str:
    """ISO date string 1 day ago (within LOOKBACK_DAYS)."""
    from datetime import timedelta

    ts = datetime.now(timezone.utc) - timedelta(days=1)
    return ts.strftime("%Y-%m-%d")


def _old_date() -> str:
    """ISO date string 30 days ago (outside LOOKBACK_DAYS)."""
    from datetime import timedelta

    ts = datetime.now(timezone.utc) - timedelta(days=30)
    return ts.strftime("%Y-%m-%d")


def _full_payload(
    *,
    paper_id: str = "abc123",
    title: str = "Convex Optimization Methods",
    abstract: str = "We study convex optimization.",
    authors: list[str] | None = None,
    pub_date: str | None = None,
    year: int | None = 2024,
    doi: str | None = "10.1234/test",
    arxiv_id: str | None = "2401.12345",
    url: str = "https://www.semanticscholar.org/paper/abc123",
    pdf_url: str | None = "https://arxiv.org/pdf/2401.12345",
) -> dict:
    if authors is None:
        authors = [{"name": "Alice Smith"}, {"name": "Bob Jones"}]
    if pub_date is None:
        pub_date = _recent_date()
    external_ids: dict = {}
    if doi:
        external_ids["DOI"] = doi
    if arxiv_id:
        external_ids["ArXiv"] = arxiv_id
    return {
        "paperId": paper_id,
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "publicationDate": pub_date,
        "year": year,
        "externalIds": external_ids,
        "url": url,
        "openAccessPdf": {"url": pdf_url} if pdf_url else None,
    }


def _page_response(items: list[dict], token: str | None = None) -> dict:
    return {"data": items, "token": token}


# ---------------------------------------------------------------------------
# Tests: _build_headers
# ---------------------------------------------------------------------------

class TestBuildHeaders:
    def test_no_api_key_header_when_key_is_empty(self, monkeypatch):
        monkeypatch.setattr(ss_module, "SEMANTIC_SCHOLAR_API_KEY", "")
        headers = _build_headers()
        assert "x-api-key" not in headers

    def test_api_key_header_present_when_key_set(self, monkeypatch):
        monkeypatch.setattr(ss_module, "SEMANTIC_SCHOLAR_API_KEY", "my-secret-key")
        headers = _build_headers()
        assert headers["x-api-key"] == "my-secret-key"

    def test_accept_header_always_present(self, monkeypatch):
        monkeypatch.setattr(ss_module, "SEMANTIC_SCHOLAR_API_KEY", "")
        headers = _build_headers()
        assert headers["Accept"] == "application/json"


# ---------------------------------------------------------------------------
# Tests: _parse_paper
# ---------------------------------------------------------------------------

class TestParsePaper:
    def test_full_payload_returns_paper(self):
        item = _full_payload()
        paper = _parse_paper(item)
        assert paper is not None
        assert paper.title == "Convex Optimization Methods"
        assert paper.abstract == "We study convex optimization."
        assert paper.authors == ["Alice Smith", "Bob Jones"]
        assert paper.doi == "10.1234/test"
        assert paper.arxiv_id == "2401.12345"
        assert paper.pdf_url == "https://arxiv.org/pdf/2401.12345"
        assert paper.source == "semantic_scholar"

    def test_missing_title_returns_none(self):
        item = _full_payload(title="")
        assert _parse_paper(item) is None

    def test_none_title_returns_none(self):
        item = _full_payload()
        item["title"] = None
        assert _parse_paper(item) is None

    def test_invalid_publication_date_falls_back_to_now(self, monkeypatch):
        fixed_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        class FakeDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now

        monkeypatch.setattr(ss_module, "datetime", FakeDatetime)

        item = _full_payload(pub_date="not-a-date")
        paper = _parse_paper(item)
        assert paper is not None
        assert paper.published_at == fixed_now

    def test_year_only_gives_jan_1(self):
        item = _full_payload(pub_date=None, year=2023)
        item["publicationDate"] = None
        paper = _parse_paper(item)
        assert paper is not None
        assert paper.published_at == datetime(2023, 1, 1, tzinfo=timezone.utc)

    def test_missing_url_with_arxiv_id_constructs_url(self):
        item = _full_payload(arxiv_id="2401.99999", url="")
        paper = _parse_paper(item)
        assert paper is not None
        assert paper.paper_url == "https://arxiv.org/abs/2401.99999"

    def test_missing_open_access_pdf_gives_none(self):
        item = _full_payload(pdf_url=None)
        paper = _parse_paper(item)
        assert paper is not None
        assert paper.pdf_url is None

    def test_source_ids_contains_doi_arxiv_and_s2(self):
        item = _full_payload(
            paper_id="s2abc",
            doi="10.1234/test",
            arxiv_id="2401.12345",
        )
        paper = _parse_paper(item)
        assert paper is not None
        assert paper.source_ids.get("doi") == "10.1234/test"
        assert paper.source_ids.get("arxiv") == "2401.12345"
        assert paper.source_ids.get("s2") == "s2abc"

    def test_source_is_semantic_scholar(self):
        paper = _parse_paper(_full_payload())
        assert paper.source == "semantic_scholar"


# ---------------------------------------------------------------------------
# Tests: fetch_semantic_scholar_papers
# ---------------------------------------------------------------------------

class TestFetchSemanticScholarPapers:
    def _mock_get(self, pages_per_query: list[dict]) -> MagicMock:
        """Build a requests.get mock with side_effect from response data dicts."""
        responses = []
        for page_data in pages_per_query:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = page_data
            responses.append(mock_resp)
        mock_get = MagicMock(side_effect=responses)
        return mock_get

    def test_single_page_response_returns_papers(self):
        item = _full_payload(paper_id="p1", pub_date=_recent_date())
        # 5 queries, first one returns 1 paper, rest return empty
        pages = [_page_response([item])] + [_page_response([])] * 4

        with patch("optimization_rss.sources.semantic_scholar.requests.get", side_effect=self._mock_get(pages).side_effect):
            papers = fetch_semantic_scholar_papers()

        assert any(p.source_ids.get("s2") == "p1" for p in papers)

    def test_multi_page_response_follows_token(self):
        item1 = _full_payload(paper_id="p1", pub_date=_recent_date())
        item2 = _full_payload(paper_id="p2", pub_date=_recent_date(), doi=None, arxiv_id="2401.00002")
        # First query: page 1 has token, page 2 has no token; other 4 queries return empty
        pages = [
            _page_response([item1], token="next-page-token"),
            _page_response([item2], token=None),
        ] + [_page_response([])] * 4

        with patch("optimization_rss.sources.semantic_scholar.requests.get", side_effect=self._mock_get(pages).side_effect):
            papers = fetch_semantic_scholar_papers()

        ids = {p.source_ids.get("s2") for p in papers}
        assert "p1" in ids
        assert "p2" in ids

    def test_old_paper_is_excluded(self):
        item = _full_payload(paper_id="old1", pub_date=_old_date())
        pages = [_page_response([item])] + [_page_response([])] * 4

        with patch("optimization_rss.sources.semantic_scholar.requests.get", side_effect=self._mock_get(pages).side_effect):
            papers = fetch_semantic_scholar_papers()

        assert not any(p.source_ids.get("s2") == "old1" for p in papers)

    def test_duplicate_paper_id_included_only_once(self):
        item = _full_payload(paper_id="dup1", pub_date=_recent_date())
        # Same item returned on two pages of the same query
        pages = [
            _page_response([item], token="next"),
            _page_response([item], token=None),
        ] + [_page_response([])] * 4

        with patch("optimization_rss.sources.semantic_scholar.requests.get", side_effect=self._mock_get(pages).side_effect):
            papers = fetch_semantic_scholar_papers()

        dup_count = sum(1 for p in papers if p.source_ids.get("s2") == "dup1")
        assert dup_count == 1

    def test_request_exception_on_first_query_other_queries_still_run(self):
        import requests as requests_lib

        good_item = _full_payload(paper_id="good1", pub_date=_recent_date())

        def side_effect(*args, **kwargs):
            side_effect.call_count = getattr(side_effect, "call_count", 0) + 1
            if side_effect.call_count == 1:
                raise requests_lib.RequestException("network error")
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = _page_response([good_item])
            return mock_resp

        with patch("optimization_rss.sources.semantic_scholar.requests.get", side_effect=side_effect):
            papers = fetch_semantic_scholar_papers()

        # First query failed but the remaining 4 queries still ran
        # and returned good_item each time
        assert len(papers) >= 1

    def test_json_parse_error_that_query_returns_no_papers(self):
        # First query raises ValueError on .json()
        bad_resp = MagicMock()
        bad_resp.raise_for_status.return_value = None
        bad_resp.json.side_effect = ValueError("bad json")

        good_item = _full_payload(paper_id="good2", pub_date=_recent_date())
        good_resp = MagicMock()
        good_resp.raise_for_status.return_value = None
        good_resp.json.return_value = _page_response([good_item])

        # 5 queries: first fails, next 4 succeed
        responses = [bad_resp] + [good_resp] * 4

        with patch(
            "optimization_rss.sources.semantic_scholar.requests.get",
            side_effect=responses,
        ):
            papers = fetch_semantic_scholar_papers()

        # First query returned nothing, but subsequent queries returned papers
        assert any(p.source_ids.get("s2") == "good2" for p in papers)
