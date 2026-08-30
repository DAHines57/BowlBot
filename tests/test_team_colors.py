"""Team display colour normalization and readability adjustment."""

from db.team_colors import normalize_color_hex, readable_hex


def test_normalize_accepts_shorthand_and_missing_hash():
    assert normalize_color_hex("abc") == "#AABBCC"
    assert normalize_color_hex("#ff8800") == "#FF8800"
    assert normalize_color_hex("  ") is None
    assert normalize_color_hex("nope") is None
    assert normalize_color_hex(None) is None


def test_bright_colors_pass_through_unchanged():
    assert readable_hex("#FFB86C") == "#FFB86C"
    assert readable_hex("#50FA7B") == "#50FA7B"


def test_dark_colors_are_lightened_for_the_dark_background():
    # Pure navy is unreadable on #12101a, so it blends 60% toward white.
    assert readable_hex("#001133") == "#999FAD"
    assert readable_hex("#000000") == "#999999"


def test_missing_color_stays_missing():
    assert readable_hex(None) is None
    assert readable_hex("") is None
