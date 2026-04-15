"""Tests for optimization_rss.state: load_state, save_state, assign_first_seen."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import optimization_rss.state as state_module
from optimization_rss.dedupe import canonical_id
from optimization_rss.state import assign_first_seen, load_state, save_state


class TestLoadState:
    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        result = load_state(tmp_path / "nonexistent.json")
        assert result == {}

    def test_returns_empty_dict_for_invalid_json(self, tmp_path):
        bad_file = tmp_path / "state.json"
        bad_file.write_text("not valid json{{{")
        assert load_state(bad_file) == {}

    def test_returns_dict_for_valid_json(self, tmp_path):
        data = {"arxiv:2401.12345": "2024-01-15T12:00:00+00:00"}
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps(data))
        assert load_state(state_file) == data


class TestSaveState:
    def test_creates_parent_directories(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "state.json"
        save_state(nested, {"key": "value"})
        assert nested.exists()

    def test_writes_valid_json(self, tmp_path):
        state_file = tmp_path / "state.json"
        data = {"doi:10.1234/test": "2024-01-15T12:00:00+00:00"}
        save_state(state_file, data)
        loaded = json.loads(state_file.read_text())
        assert loaded == data

    def test_written_json_matches_input(self, tmp_path):
        state_file = tmp_path / "state.json"
        data = {
            "arxiv:2401.00001": "2024-01-10T00:00:00+00:00",
            "arxiv:2401.00002": "2024-01-11T00:00:00+00:00",
        }
        save_state(state_file, data)
        assert load_state(state_file) == data


class TestAssignFirstSeen:
    def _make_fake_datetime(self, fixed_dt):
        """Return a datetime subclass whose .now() always returns fixed_dt."""

        class FakeDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_dt

        return FakeDatetime

    def test_known_paper_gets_stored_timestamp(self, paper_factory, fixed_dt, monkeypatch):
        stored_ts = "2024-01-10T08:00:00+00:00"
        paper = paper_factory(doi=None, arxiv_id="2401.11111")
        cid = canonical_id(paper)
        state = {cid: stored_ts}

        papers, _ = assign_first_seen([paper], state)

        assert papers[0].first_seen_at == datetime.fromisoformat(stored_ts)

    def test_new_paper_gets_current_time(self, paper_factory, fixed_dt, monkeypatch):
        FakeDatetime = self._make_fake_datetime(fixed_dt)
        monkeypatch.setattr(state_module, "datetime", FakeDatetime)

        paper = paper_factory(doi=None, arxiv_id="2401.99999")
        papers, _ = assign_first_seen([paper], {})

        assert papers[0].first_seen_at == fixed_dt

    def test_both_papers_are_returned(self, paper_factory, fixed_dt, monkeypatch):
        FakeDatetime = self._make_fake_datetime(fixed_dt)
        monkeypatch.setattr(state_module, "datetime", FakeDatetime)

        known_ts = "2024-01-10T08:00:00+00:00"
        known_paper = paper_factory(doi=None, arxiv_id="2401.11111")
        new_paper = paper_factory(doi=None, arxiv_id="2401.22222")
        state = {canonical_id(known_paper): known_ts}

        papers, _ = assign_first_seen([known_paper, new_paper], state)

        assert len(papers) == 2

    def test_new_paper_canonical_id_added_to_updated_state(self, paper_factory, fixed_dt, monkeypatch):
        FakeDatetime = self._make_fake_datetime(fixed_dt)
        monkeypatch.setattr(state_module, "datetime", FakeDatetime)

        paper = paper_factory(doi=None, arxiv_id="2401.99999")
        cid = canonical_id(paper)

        _, updated_state = assign_first_seen([paper], {})

        assert cid in updated_state

    def test_original_state_not_mutated(self, paper_factory, fixed_dt, monkeypatch):
        FakeDatetime = self._make_fake_datetime(fixed_dt)
        monkeypatch.setattr(state_module, "datetime", FakeDatetime)

        paper = paper_factory(doi=None, arxiv_id="2401.99999")
        original_state = {}

        assign_first_seen([paper], original_state)

        assert original_state == {}

    def test_two_new_papers_same_canonical_id_share_one_state_entry(
        self, paper_factory, fixed_dt, monkeypatch
    ):
        FakeDatetime = self._make_fake_datetime(fixed_dt)
        monkeypatch.setattr(state_module, "datetime", FakeDatetime)

        # Both papers have the same arxiv_id -> same canonical_id
        paper1 = paper_factory(doi=None, arxiv_id="2401.11111", title="Paper One")
        paper2 = paper_factory(doi=None, arxiv_id="2401.11111", title="Paper Two")

        papers, updated_state = assign_first_seen([paper1, paper2], {})

        assert len(papers) == 2
        cid = canonical_id(paper1)
        assert cid in updated_state
        # Only one entry in state for the shared canonical_id
        assert len([k for k in updated_state if k == cid]) == 1
        # Both papers have the same first_seen_at (fixed_dt)
        assert papers[0].first_seen_at == fixed_dt
        assert papers[1].first_seen_at == fixed_dt
