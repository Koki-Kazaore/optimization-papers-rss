"""Tests for optimization_rss.dedupe: _normalize, canonical_id, deduplicate."""
from datetime import datetime, timezone

import pytest

from optimization_rss.dedupe import _normalize, canonical_id, deduplicate


class TestNormalize:
    def test_lowercases_text(self):
        assert _normalize("HELLO WORLD") == "hello world"

    def test_strips_leading_trailing_whitespace(self):
        assert _normalize("  hello  ") == "hello"

    def test_removes_punctuation(self):
        assert _normalize("hello, world! (test)") == "hello world test"

    def test_collapses_multiple_spaces(self):
        assert _normalize("hello   world") == "hello world"

    def test_handles_empty_string(self):
        assert _normalize("") == ""

    def test_combined_transformations(self):
        assert _normalize("  Hello,  World!  ") == "hello world"


class TestCanonicalId:
    def test_prefers_doi(self, paper_factory):
        paper = paper_factory(doi="10.1234/test.2024", arxiv_id="2401.12345")
        assert canonical_id(paper) == "doi:10.1234/test.2024"

    def test_falls_back_to_arxiv_id(self, paper_factory):
        paper = paper_factory(doi=None, arxiv_id="2401.12345")
        assert canonical_id(paper) == "arxiv:2401.12345"

    def test_strips_version_from_arxiv_id(self, paper_factory):
        paper = paper_factory(doi=None, arxiv_id="2401.12345v2")
        assert canonical_id(paper) == "arxiv:2401.12345"

    def test_strips_version_v3(self, paper_factory):
        paper = paper_factory(doi=None, arxiv_id="2401.12345v3")
        assert canonical_id(paper) == "arxiv:2401.12345"

    def test_falls_back_to_title_author_year(self, paper_factory):
        paper = paper_factory(
            doi=None,
            arxiv_id=None,
            title="Convex Optimization",
            authors=["Alice Smith"],
            published_at=datetime(2024, 1, 14, tzinfo=timezone.utc),
        )
        cid = canonical_id(paper)
        assert cid.startswith("title:")
        assert "2024" in cid

    def test_empty_authors_falls_back_to_unknown(self, paper_factory):
        paper = paper_factory(
            doi=None,
            arxiv_id=None,
            title="A Paper",
            authors=[],
            published_at=datetime(2024, 1, 14, tzinfo=timezone.utc),
        )
        cid = canonical_id(paper)
        assert "|unknown|" in cid

    def test_long_title_truncated_at_80(self, paper_factory):
        long_title = "A" * 100  # 100 chars -> normalized to "a" * 100
        paper = paper_factory(
            doi=None,
            arxiv_id=None,
            title=long_title,
            authors=["Bob Jones"],
            published_at=datetime(2024, 1, 14, tzinfo=timezone.utc),
        )
        cid = canonical_id(paper)
        # title part is between "title:" and "|"
        title_part = cid[len("title:"):cid.index("|")]
        assert len(title_part) <= 80

    def test_long_author_truncated_at_40(self, paper_factory):
        long_author = "A" * 60  # 60 chars -> normalized to "a" * 60
        paper = paper_factory(
            doi=None,
            arxiv_id=None,
            title="Short Title",
            authors=[long_author],
            published_at=datetime(2024, 1, 14, tzinfo=timezone.utc),
        )
        cid = canonical_id(paper)
        # author part is between the first and last "|"
        parts = cid.split("|")
        # cid = "title:<title>|<author>|<year>"
        author_part = parts[1]
        assert len(author_part) <= 40


class TestDeduplicate:
    def test_removes_exact_duplicates(self, paper_factory):
        paper = paper_factory(arxiv_id="2401.11111")
        duplicate = paper_factory(arxiv_id="2401.11111")
        result = deduplicate([paper, duplicate])
        assert len(result) == 1

    def test_keeps_first_occurrence(self, paper_factory):
        paper1 = paper_factory(arxiv_id="2401.11111", title="First")
        paper2 = paper_factory(arxiv_id="2401.11111", title="Second")
        result = deduplicate([paper1, paper2])
        assert result[0].title == "First"

    def test_preserves_order_of_unique_papers(self, paper_factory):
        p1 = paper_factory(arxiv_id="2401.00001")
        p2 = paper_factory(arxiv_id="2401.00002")
        p3 = paper_factory(arxiv_id="2401.00003")
        result = deduplicate([p1, p2, p3])
        assert [p.arxiv_id for p in result] == ["2401.00001", "2401.00002", "2401.00003"]

    def test_returns_all_if_all_unique(self, paper_factory):
        papers = [paper_factory(arxiv_id=f"2401.{i:05d}") for i in range(5)]
        result = deduplicate(papers)
        assert len(result) == 5

    def test_doi_deduplication(self, paper_factory):
        p1 = paper_factory(doi="10.1234/test", arxiv_id=None)
        p2 = paper_factory(doi="10.1234/test", arxiv_id=None)
        result = deduplicate([p1, p2])
        assert len(result) == 1

    def test_empty_list(self):
        assert deduplicate([]) == []
