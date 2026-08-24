"""Tests for the Sidearm bio-page school enhancement.

The HTML parsing is pure (parsers.parse_bio_schools) and tested offline against
fixtures; the network wrapper (scraper.enhance_sidearm_schools_from_bios) is
tested with a stub session so no requests are made.
"""
from pathlib import Path

from bs4 import BeautifulSoup

from rosters import parsers
from rosters.models import Player
from rosters.scraper import enhance_sidearm_schools_from_bios

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def bio_soup(label):
    return BeautifulSoup((FIXTURES / 'bio' / f'{label}.html').read_bytes(), 'html.parser')


# --- pure extractor ----------------------------------------------------------

def test_parse_bio_schools_reads_dl_dt_dd():
    hs, prev = parsers.parse_bio_schools(bio_soup('sidearm_dl'))
    assert hs == 'Our Lady of Good Counsel'
    assert prev == 'Boston College'


def test_parse_bio_schools_absent_returns_empty():
    soup = BeautifulSoup('<html><body><p>no fields here</p></body></html>', 'html.parser')
    assert parsers.parse_bio_schools(soup) == ('', '')


def test_parse_bio_schools_only_previous_leaves_hs_empty():
    # Site with a single school field labelled "Previous School" (Alabama A&M
    # style): we must not invent a high_school value.
    markup = ('<dl><dt>Previous School:</dt><dd>Somerset Academy Canyons HS</dd></dl>')
    hs, prev = parsers.parse_bio_schools(BeautifulSoup(markup, 'html.parser'))
    assert hs == ''
    assert prev == 'Somerset Academy Canyons HS'


# --- network wrapper (stubbed session) ---------------------------------------

class _StubResp:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status


class _StubSession:
    """Returns the same fixture body for every GET; records call count."""
    def __init__(self, body):
        self.body = body
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        return _StubResp(self.body)


def _player(**kw):
    base = dict(team_id=392, team='Maryland', season='2025',
                url='https://umterps.com/sports/womens-soccer/roster/x/1')
    base.update(kw)
    return Player(**base)


def test_enhance_fills_missing_schools():
    body = (FIXTURES / 'bio' / 'sidearm_dl.html').read_text()
    session = _StubSession(body)
    players = [_player(name='A', high_school='', previous_school='')]
    out = enhance_sidearm_schools_from_bios(players, 'Maryland', session)
    assert out[0].high_school == 'Our Lady of Good Counsel'
    assert out[0].previous_school == 'Boston College'
    assert session.calls == 1


def test_enhance_skips_players_that_already_have_hs():
    body = (FIXTURES / 'bio' / 'sidearm_dl.html').read_text()
    session = _StubSession(body)
    players = [_player(name='A', high_school='Existing HS', previous_school='')]
    out = enhance_sidearm_schools_from_bios(players, 'Maryland', session)
    # already has HS -> no fetch, unchanged
    assert out[0].high_school == 'Existing HS'
    assert session.calls == 0


def test_enhance_noops_when_coverage_already_high():
    body = (FIXTURES / 'bio' / 'sidearm_dl.html').read_text()
    session = _StubSession(body)
    # 9 of 10 already have HS -> below the missing-majority gate, no fetches
    players = [_player(name=str(i), high_school='HS', previous_school='') for i in range(9)]
    players.append(_player(name='last', high_school='', previous_school=''))
    out = enhance_sidearm_schools_from_bios(players, 'Maryland', session)
    assert session.calls == 0
    assert out[-1].high_school == ''
