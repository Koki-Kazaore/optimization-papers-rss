"""Tests for optimization_rss.main.main()."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from optimization_rss.main import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_arxiv_paper(paper_factory, arxiv_id: str, title: str = "", abstract: str = ""):
    return paper_factory(
        source="arxiv",
        doi=None,
        arxiv_id=arxiv_id,
        title=title or f"Arxiv Paper {arxiv_id}",
        abstract=abstract or "We study convex optimization.",
    )


def _make_ss_paper(paper_factory, arxiv_id: str, title: str = "", abstract: str = ""):
    return paper_factory(
        source="semantic_scholar",
        doi=None,
        arxiv_id=arxiv_id,
        title=title or f"SS Paper {arxiv_id}",
        abstract=abstract or "We study convex optimization.",
        paper_url=f"https://www.semanticscholar.org/paper/{arxiv_id}",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMain:
    def _patch_all(
        self,
        *,
        state: dict = None,
        arxiv_papers=None,
        ss_papers=None,
    ):
        """Return a context manager dict with all I/O patched."""
        state = state if state is not None else {}
        arxiv_papers = arxiv_papers or []
        ss_papers = ss_papers or []
        return {
            "load_state": patch(
                "optimization_rss.main.load_state", return_value=state
            ),
            "fetch_arxiv": patch(
                "optimization_rss.main.fetch_arxiv_papers", return_value=arxiv_papers
            ),
            "fetch_ss": patch(
                "optimization_rss.main.fetch_semantic_scholar_papers",
                return_value=ss_papers,
            ),
            "save_state": patch("optimization_rss.main.save_state"),
            "generate_feed": patch("optimization_rss.main.generate_feed"),
        }

    def test_happy_path_save_state_and_generate_feed_called_once(self, paper_factory):
        arxiv_paper = _make_arxiv_paper(paper_factory, "2401.11111")
        matching_ss = _make_ss_paper(
            paper_factory,
            "2401.22222",
            abstract="We study convex optimization thoroughly.",
        )
        non_matching_ss = _make_ss_paper(
            paper_factory,
            "2401.33333",
            title="A Bioinformatics Study",
            abstract="We analyze genome sequences.",
        )
        # Duplicate of arxiv_paper (same arxiv_id, no doi)
        duplicate_ss = _make_ss_paper(paper_factory, "2401.11111")

        patches = self._patch_all(
            arxiv_papers=[arxiv_paper],
            ss_papers=[matching_ss, non_matching_ss, duplicate_ss],
        )

        with (
            patches["load_state"],
            patches["fetch_arxiv"],
            patches["fetch_ss"],
            patches["save_state"] as mock_save,
            patches["generate_feed"] as mock_gen,
        ):
            main()

        mock_save.assert_called_once()
        mock_gen.assert_called_once()

    def test_non_matching_ss_paper_excluded_from_feed(self, paper_factory):
        arxiv_paper = _make_arxiv_paper(paper_factory, "2401.11111")
        non_matching_ss = _make_ss_paper(
            paper_factory,
            "2401.33333",
            title="Unrelated Biology Paper",
            abstract="We study DNA replication mechanisms.",
        )

        patches = self._patch_all(
            arxiv_papers=[arxiv_paper],
            ss_papers=[non_matching_ss],
        )

        with (
            patches["load_state"],
            patches["fetch_arxiv"],
            patches["fetch_ss"],
            patches["save_state"],
            patches["generate_feed"] as mock_gen,
        ):
            main()

        called_papers = mock_gen.call_args[0][0]
        arxiv_ids = {p.arxiv_id for p in called_papers}
        assert "2401.33333" not in arxiv_ids

    def test_duplicate_is_deduplicated(self, paper_factory):
        arxiv_paper = _make_arxiv_paper(paper_factory, "2401.11111")
        # Same arxiv_id as arxiv_paper — will be deduplicated
        duplicate_ss = _make_ss_paper(paper_factory, "2401.11111")

        patches = self._patch_all(
            arxiv_papers=[arxiv_paper],
            ss_papers=[duplicate_ss],
        )

        with (
            patches["load_state"],
            patches["fetch_arxiv"],
            patches["fetch_ss"],
            patches["save_state"],
            patches["generate_feed"] as mock_gen,
        ):
            main()

        called_papers = mock_gen.call_args[0][0]
        # Only one paper with arxiv_id "2401.11111" should remain
        dup_count = sum(1 for p in called_papers if p.arxiv_id == "2401.11111")
        assert dup_count == 1

    def test_ss_fetch_exception_pipeline_still_completes(self, paper_factory):
        arxiv_paper = _make_arxiv_paper(paper_factory, "2401.11111")

        with (
            patch("optimization_rss.main.load_state", return_value={}),
            patch("optimization_rss.main.fetch_arxiv_papers", return_value=[arxiv_paper]),
            patch(
                "optimization_rss.main.fetch_semantic_scholar_papers",
                side_effect=Exception("API is down"),
            ),
            patch("optimization_rss.main.save_state") as mock_save,
            patch("optimization_rss.main.generate_feed") as mock_gen,
        ):
            main()

        mock_gen.assert_called_once()
        mock_save.assert_called_once()

    def test_ss_fetch_exception_arxiv_results_still_in_feed(self, paper_factory):
        arxiv_paper = _make_arxiv_paper(paper_factory, "2401.11111")

        with (
            patch("optimization_rss.main.load_state", return_value={}),
            patch("optimization_rss.main.fetch_arxiv_papers", return_value=[arxiv_paper]),
            patch(
                "optimization_rss.main.fetch_semantic_scholar_papers",
                side_effect=Exception("API is down"),
            ),
            patch("optimization_rss.main.save_state"),
            patch("optimization_rss.main.generate_feed") as mock_gen,
        ):
            main()

        called_papers = mock_gen.call_args[0][0]
        assert any(p.arxiv_id == "2401.11111" for p in called_papers)

    def test_empty_state_new_papers_get_first_seen_at(self, paper_factory):
        arxiv_paper = _make_arxiv_paper(paper_factory, "2401.11111")

        with (
            patch("optimization_rss.main.load_state", return_value={}),
            patch("optimization_rss.main.fetch_arxiv_papers", return_value=[arxiv_paper]),
            patch("optimization_rss.main.fetch_semantic_scholar_papers", return_value=[]),
            patch("optimization_rss.main.save_state"),
            patch("optimization_rss.main.generate_feed") as mock_gen,
        ):
            main()

        called_papers = mock_gen.call_args[0][0]
        for p in called_papers:
            assert p.first_seen_at is not None
            assert p.first_seen_at.tzinfo is not None  # timezone-aware
