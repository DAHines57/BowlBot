from db.season_admin import suggest_new_season_numbers


def test_suggest_new_season_numbers_only_forward():
    db = [{"number": 12}, {"number": 14}]
    opts = suggest_new_season_numbers(db, ahead=2)
    assert opts == [15, 16]
    assert 13 not in opts
    assert 1 not in opts


def test_suggest_new_season_numbers_from_empty():
    assert suggest_new_season_numbers([], ahead=3) == [1, 2, 3]
