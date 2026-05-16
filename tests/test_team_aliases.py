"""Team name alias rules are season-scoped."""
from stats.facts import canonical_team_name, resolve_opponent_on_roster


def test_bowls_deep_only_merged_in_season_11():
    assert canonical_team_name("Bowls Deep", season_num=11) == "Strike It Deep"
    assert canonical_team_name("Bowls Deep", season_num=10) == "Bowls Deep"
    assert canonical_team_name("Bowls Deep") == "Bowls Deep"


def test_resolve_opponent_alias_only_season_11():
    roster = ["Strike It Deep", "Other Team"]
    assert (
        resolve_opponent_on_roster("Bowls Deep", roster, season_num=11)
        == "Strike It Deep"
    )
    assert resolve_opponent_on_roster("Bowls Deep", roster, season_num=10) is None
