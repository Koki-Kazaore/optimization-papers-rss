"""Tests for optimization_rss.filters.matches_optimization_keywords."""
from optimization_rss.filters import matches_optimization_keywords


class TestMatchesOptimizationKeywords:
    def test_keyword_in_title_only(self, paper_factory):
        paper = paper_factory(
            title="Convex Optimization for Resource Allocation",
            abstract="This paper presents a novel method.",
        )
        assert matches_optimization_keywords(paper) is True

    def test_keyword_in_abstract_only(self, paper_factory):
        paper = paper_factory(
            title="A New Approach to Decision Making",
            abstract="We apply gradient descent to minimize the loss function.",
        )
        assert matches_optimization_keywords(paper) is True

    def test_keyword_spans_title_and_abstract(self, paper_factory):
        # "linear programming" — "linear" at end of title, "programming" at start of abstract
        # combined: "...linear programming..." => matches
        paper = paper_factory(
            title="Solving problems with linear",
            abstract="programming techniques for scheduling tasks.",
        )
        assert matches_optimization_keywords(paper) is True

    def test_no_keyword_match(self, paper_factory):
        paper = paper_factory(
            title="Deep Learning with Transformers",
            abstract="We propose a self-attention mechanism for natural language processing.",
        )
        assert matches_optimization_keywords(paper) is False

    def test_empty_title_and_abstract(self, paper_factory):
        paper = paper_factory(title="", abstract="")
        assert matches_optimization_keywords(paper) is False

    def test_keyword_in_authors_does_not_trigger_match(self, paper_factory):
        paper = paper_factory(
            title="A Study on Neural Network Architectures",
            abstract="We explore deep learning with residual connections.",
            authors=["Convex Optimization Expert", "Gradient Descent"],
        )
        assert matches_optimization_keywords(paper) is False

    def test_case_insensitive_title(self, paper_factory):
        paper = paper_factory(
            title="INTERIOR POINT METHODS FOR CONIC PROGRAMMING",
            abstract="A brief abstract with no keywords.",
        )
        assert matches_optimization_keywords(paper) is True

    def test_case_insensitive_abstract(self, paper_factory):
        paper = paper_factory(
            title="An Unrelated Title",
            abstract="We use SIMPLEX METHOD to solve the LP relaxation.",
        )
        assert matches_optimization_keywords(paper) is True
