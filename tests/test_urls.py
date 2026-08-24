from rosters.urls import URLBuilder

build = URLBuilder.build_roster_url


def test_default():
    assert build('https://x.com/sports/mens-soccer', '2025') == \
        'https://x.com/sports/mens-soccer/roster/2025'


def test_full_roster_url_passthrough():
    url = 'https://x.com/sports/msoc/roster/2025'
    assert build(url, '2025', 'default') == url


def test_sport_index_replaces_index():
    assert build('https://x.com/sports/msoc/index', '2025', 'sport_index') == \
        'https://x.com/sports/msoc/roster/2025'


def test_sport_plain_equals_default_shape():
    assert build('https://x.com/sports/msoc', '2025', 'sport_plain') == \
        'https://x.com/sports/msoc/roster/2025'


def test_sport_season_range():
    assert build('https://x.com/sports/msoc/index', '2025', 'sport_season_range') == \
        'https://x.com/sports/msoc/2025-26/roster'


def test_virginia_season_range_from_year():
    assert build('https://virginiasports.com/sports/msoc', '2025', 'virginia_season') == \
        'https://virginiasports.com/sports/msoc/roster/season/2025-26/'


def test_virginia_table_from_year():
    assert build('https://virginiasports.com/sports/msoc', '2025', 'virginia_table') == \
        'https://virginiasports.com/sports/msoc/roster/season/2025-26?view=table'


def test_virginia_table_already_range():
    # A non-integer season is treated as an already-formed range.
    assert build('https://virginiasports.com/sports/msoc', '2025-26', 'virginia_table') == \
        'https://virginiasports.com/sports/msoc/roster/season/2025-26?view=table'


def test_kentucky_season_takes_end_year():
    assert build('https://ukathletics.com/sports/msoc', '2024-25', 'kentucky_season') == \
        'https://ukathletics.com/sports/msoc/roster/season/2025/'


def test_unknown_format_falls_back_to_default():
    assert build('https://x.com/sports/mens-soccer', '2025', 'nonsense') == \
        'https://x.com/sports/mens-soccer/roster/2025'


def test_extract_base_url_keeps_subdomain():
    assert URLBuilder.extract_base_url('https://goheels.com/sports/mens-soccer') == \
        'https://goheels.com'
