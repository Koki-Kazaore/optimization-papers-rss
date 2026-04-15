"""Tests for optimization_rss.rss.generate_feed."""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import pytest

from optimization_rss.config import FEED_DESCRIPTION, FEED_LINK, FEED_TITLE
from optimization_rss.rss import MAX_FEED_ITEMS, generate_feed


class TestGenerateFeed:
    def test_creates_output_file(self, paper_factory, tmp_path):
        out = tmp_path / "feed.xml"
        generate_feed([paper_factory()], out)
        assert out.exists()

    def test_output_is_valid_xml(self, paper_factory, tmp_path):
        out = tmp_path / "feed.xml"
        generate_feed([paper_factory()], out)
        # Should not raise
        ET.parse(str(out))

    def test_output_is_valid_rss_parseable_by_feedparser(self, paper_factory, tmp_path, parse_rss):
        out = tmp_path / "feed.xml"
        generate_feed([paper_factory()], out)
        _, feed = parse_rss(out)
        assert feed.bozo is False or feed.bozo == 0

    def test_channel_title_matches_config(self, paper_factory, tmp_path):
        out = tmp_path / "feed.xml"
        generate_feed([paper_factory()], out)
        root = ET.parse(str(out)).getroot()
        assert root.find("channel/title").text == FEED_TITLE

    def test_channel_description_matches_config(self, paper_factory, tmp_path):
        out = tmp_path / "feed.xml"
        generate_feed([paper_factory()], out)
        root = ET.parse(str(out)).getroot()
        assert root.find("channel/description").text == FEED_DESCRIPTION

    def test_channel_link_matches_config(self, paper_factory, tmp_path):
        out = tmp_path / "feed.xml"
        generate_feed([paper_factory()], out)
        xml_text = out.read_text()
        assert FEED_LINK in xml_text

    def test_items_sorted_by_first_seen_at_descending(self, paper_factory, tmp_path, parse_rss):
        base = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        papers = [
            paper_factory(
                arxiv_id=f"2401.{i:05d}",
                title=f"Paper {i}",
                first_seen_at=base - timedelta(hours=i),
            )
            for i in range(3)
        ]
        # Pass in shuffled order to verify generate_feed reorders them
        shuffled = [papers[2], papers[0], papers[1]]
        out = tmp_path / "feed.xml"
        generate_feed(shuffled, out)
        _, feed = parse_rss(out)

        titles = [e.title for e in feed.entries]
        # generate_feed sorts papers by first_seen_at descending (newest first).
        # Paper 0 (base, newest first_seen_at) must appear first in the feed.
        assert titles[0] == "Paper 0"
        assert titles.index("Paper 0") < titles.index("Paper 2")

    def test_item_count_capped_at_500(self, paper_factory, tmp_path, parse_rss):
        papers = [
            paper_factory(
                arxiv_id=f"2401.{i:05d}",
                first_seen_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc) - timedelta(minutes=i),
            )
            for i in range(MAX_FEED_ITEMS + 2)
        ]
        out = tmp_path / "feed.xml"
        generate_feed(papers, out)
        _, feed = parse_rss(out)
        assert len(feed.entries) == MAX_FEED_ITEMS

    def test_item_has_correct_title(self, paper_factory, tmp_path, parse_rss):
        paper = paper_factory(title="My Optimization Paper")
        out = tmp_path / "feed.xml"
        generate_feed([paper], out)
        _, feed = parse_rss(out)
        assert feed.entries[0].title == "My Optimization Paper"

    def test_item_has_correct_link(self, paper_factory, tmp_path, parse_rss):
        paper = paper_factory(paper_url="https://arxiv.org/abs/2401.99999")
        out = tmp_path / "feed.xml"
        generate_feed([paper], out)
        _, feed = parse_rss(out)
        assert feed.entries[0].link == "https://arxiv.org/abs/2401.99999"

    def test_item_has_correct_description(self, paper_factory, tmp_path, parse_rss):
        paper = paper_factory(abstract="This is the abstract text.")
        out = tmp_path / "feed.xml"
        generate_feed([paper], out)
        _, feed = parse_rss(out)
        assert "This is the abstract text." in feed.entries[0].summary

    def test_empty_abstract_uses_fallback(self, paper_factory, tmp_path):
        paper = paper_factory(abstract="")
        out = tmp_path / "feed.xml"
        generate_feed([paper], out)
        root = ET.parse(str(out)).getroot()
        item = root.find("channel/item")
        assert item.find("description").text == "No abstract available."

    def test_multiple_authors_no_error(self, paper_factory, tmp_path, parse_rss):
        # feedgen 1.0 RSS2.0 does not emit <author> without an email address,
        # but generate_feed should not raise and should still produce a valid feed.
        paper = paper_factory(authors=["Alice Smith", "Bob Jones", "Carol Lee"])
        out = tmp_path / "feed.xml"
        generate_feed([paper], out)
        _, feed = parse_rss(out)
        assert len(feed.entries) == 1

    def test_empty_list_produces_empty_feed(self, tmp_path, parse_rss):
        out = tmp_path / "feed.xml"
        generate_feed([], out)
        _, feed = parse_rss(out)
        assert len(feed.entries) == 0

    def test_creates_parent_directories(self, paper_factory, tmp_path):
        out = tmp_path / "subdir" / "nested" / "feed.xml"
        generate_feed([paper_factory()], out)
        assert out.exists()
