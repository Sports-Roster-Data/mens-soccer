"""Parser tests run fully offline against captured/synthetic HTML fixtures.

Each parser is loaded from a fresh BeautifulSoup per call because several
parsers mutate the tree (e.g. decompose label spans)."""
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from rosters import parsers

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def soup(parser_name, label):
    return BeautifulSoup((FIXTURES / parser_name / f'{label}.html').read_bytes(), 'html.parser')


def which_layout(html):
    for name, gate, _ in parsers.PARSERS:
        if gate is None or gate(html):
            return name
    return None


# --- real fixture: full best_parse pipeline (regression snapshot) ------------

def test_albany_table_pipeline():
    html = soup('table', 'albany')
    players = parsers.best_parse(html, 14, 'Albany', '2025', 'I',
                                 'https://ualbanysports.com/sports/mens-soccer')
    assert len(players) == 30
    first = players[0].to_dict()
    assert first['name'] == 'Alexander Genz'
    assert first['jersey'] == '0'
    assert first['position'] == 'GK'
    assert first['height'] == '6\'4"'
    assert first['class'] == 'Freshman'
    assert first['url'].endswith('/roster/alexander-genz/10990')


# --- synthetic sidearm: highest-priority parser + gate ordering --------------

def test_sidearm_selected_first():
    html = soup('sidearm', 'synthetic')
    # sidearm must win even though the generic 'table' fallback would also run.
    assert which_layout(html) == 'sidearm'


def test_sidearm_fields():
    html = soup('sidearm', 'synthetic')
    players = parsers.best_parse(html, 1, 'Test', '2025', 'I', 'https://ex.com/sports/mens-soccer')
    assert len(players) == 2
    p0 = players[0].to_dict()
    assert (p0['name'], p0['jersey'], p0['position'], p0['height'], p0['class']) == \
        ('Jane Doe', '7', 'M', '5-9', 'Junior')
    assert p0['hometown'] == 'Boston, MA'
    assert p0['url'] == 'https://ex.com/sports/mens-soccer/roster/jane-doe/1'
    # absolute href preserved
    assert players[1].to_dict()['url'] == 'https://ex.com/roster/sam-roe/2'


# --- synthetic presto (data-label) -------------------------------------------

def test_presto_selected_and_parsed():
    html = soup('presto_table', 'synthetic')
    assert which_layout(html) == 'presto_table'
    players = parsers.best_parse(html, 2, 'P', '2025', 'II', 'https://ex.com/sports/msoc')
    assert len(players) == 1
    p = players[0].to_dict()
    assert p['name'] == 'Al Vez'
    assert p['position'] == 'F'
    assert p['jersey'] == '9'


# --- synthetic wmt_cards (newer WMT roster-card layout) ----------------------

def test_wmt_cards_selected_and_parsed():
    html = soup('wmt_cards', 'synthetic')
    assert which_layout(html) == 'wmt_cards'
    players = parsers.best_parse(html, 28, 'Arizona St.', '2025', 'I',
                                 'https://thesundevils.com/sports/womens-soccer')
    # two player cards; the staff/coach card is skipped
    assert len(players) == 2
    p0 = players[0].to_dict()
    assert p0['name'] == 'Kennedy Zorn'
    assert p0['jersey'] == '1'
    assert p0['position'] == 'GK'
    assert p0['height'] == '5′7″'
    assert p0['class'] == 'Sophomore'
    assert p0['hometown'] == 'Peoria, Ariz.'
    # relative href resolved against the team origin
    assert p0['url'] == 'https://thesundevils.com/sports/soccer/roster/player/kennedy-zorn'
    # absolute href preserved
    assert players[1].to_dict()['url'] == \
        'https://thesundevils.com/sports/soccer/roster/player/jane-doe'


# --- defensive behaviour: broken input never raises --------------------------

@pytest.mark.parametrize('markup', [
    '',
    '<html><body></body></html>',
    '<ul><li class="sidearm-roster-player"></li></ul>',   # item with no name
    '<table><tbody><tr><td data-label="Name"></td></tr></tbody></table>',
])
def test_broken_html_returns_empty_without_error(markup):
    html = BeautifulSoup(markup, 'html.parser')
    result = parsers.best_parse(html, 0, 'X', '2025', '', 'https://ex.com')
    assert result == []


def test_oas_url_builder_pure():
    text = 'stuff https://oas-backend/website-api/player-rosters?foo=1 more'
    url = parsers.build_oas_api_url(text)
    assert 'website-api/player-rosters' in url
    assert 'per_page=200' in url and 'page=1' in url


def test_oas_payload_conversion():
    payload = {'data': [{
        'player': {'full_name': 'Kai Lund', 'slug': 'kai-lund', 'height_feet': 6, 'height_inches': 1},
        'jersey_number_label': '11',
        'player_position': {'abbreviation': 'F'},
        'class_level': {'name': 'Sophomore'},
    }]}
    players = parsers.parse_oas_payload(payload, 1, 'T', '2025', 'I',
                                        'https://ex.com/sports/womens-soccer',
                                        roster_slug='womens-soccer')
    assert len(players) == 1
    p = players[0].to_dict()
    assert p['name'] == 'Kai Lund'
    assert p['jersey'] == '11'
    assert p['position'] == 'F'
    assert p['height'] == '6-1'
    assert p['url'] == 'https://ex.com/sports/womens-soccer/roster/kai-lund'
