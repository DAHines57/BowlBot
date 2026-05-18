"""Tests for frozen vs DB-managed season policy (Phase 6)."""
import pytest

from db import data_ownership as policy


@pytest.fixture(autouse=True)
def clear_cutoff_env(monkeypatch):
    monkeypatch.delenv("LAST_EXCEL_IMPORTED_SEASON", raising=False)


def test_unset_cutoff_all_seasons_excel_importable():
    assert policy.last_excel_imported_season() is None
    assert policy.is_season_db_managed(14) is False
    assert policy.is_season_excel_importable(14) is True


def test_cutoff_marks_higher_seasons_db_managed(monkeypatch):
    monkeypatch.setenv("LAST_EXCEL_IMPORTED_SEASON", "13")
    assert policy.last_excel_imported_season() == 13
    assert policy.is_season_db_managed(13) is False
    assert policy.is_season_db_managed(14) is True
    assert policy.is_season_excel_importable(13) is True
    assert policy.is_season_excel_importable(14) is False


def test_force_overrides_db_managed(monkeypatch):
    monkeypatch.setenv("LAST_EXCEL_IMPORTED_SEASON", "13")
    assert policy.is_season_excel_importable(14, force=True) is True


def test_invalid_cutoff_treated_as_unset(monkeypatch):
    monkeypatch.setenv("LAST_EXCEL_IMPORTED_SEASON", "not-a-number")
    assert policy.last_excel_imported_season() is None
    assert policy.is_season_db_managed(99) is False
