from pathlib import Path

from rosters.config import SPORTS, load_teams, team_url_format, team_requires_js

ROOT = Path(__file__).resolve().parent.parent


def test_sports_files_exist():
    for cfg in SPORTS.values():
        assert (ROOT / cfg['teams_file']).exists()


def test_load_men_division_filter():
    teams = load_teams(str(ROOT / 'data/input/teams.csv'), division='I')
    assert len(teams) > 100
    assert all(t['division'] == 'I' for t in teams)
    assert all('ncaa_id' in t for t in teams)


def test_load_women_normalizes_team_id():
    teams = load_teams(str(ROOT / 'data/input/teams_wsoc.csv'))
    assert teams and all(t.get('ncaa_id') for t in teams)


def test_women_division_filter_is_empty(caplog):
    # Women's file has no division data; filtering should yield nothing + warn.
    teams = load_teams(str(ROOT / 'data/input/teams_wsoc.csv'), division='I')
    assert teams == []


def test_url_format_explicit_wins():
    assert team_url_format({'url_format': 'virginia_table', 'url': 'x'}) == 'virginia_table'


def test_url_format_autodetect():
    assert team_url_format({'url': 'https://x.com/sports/msoc/index'}) == 'sport_index'
    assert team_url_format({'url': 'https://x.com/sports/msoc'}) == 'sport_plain'
    assert team_url_format({'url': 'https://x.com/sports/mens-soccer'}) == 'default'


def test_requires_js_truthiness():
    assert team_requires_js({'requires_js': 'true'}) is True
    assert team_requires_js({'requires_js': ''}) is False
    assert team_requires_js({}) is False
